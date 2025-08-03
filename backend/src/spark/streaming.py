"""
Spark streaming job management.
"""
import logging
from typing import Optional
from pyspark.sql import functions as F
from pyspark.sql.streaming import StreamingQuery

from .config import SparkConfig, SparkSchemas
from .session import SparkSessionManager

logger = logging.getLogger(__name__)


class StreamingManager:
    """Manages Spark streaming jobs for temperature data and alerts."""
    
    def __init__(self, session_manager: SparkSessionManager, minio_bucket: str):
        """Initialize StreamingManager."""
        self.session_manager = session_manager
        self.minio_bucket = minio_bucket
        
        # Build paths
        self.sensors_path = f"s3a://{minio_bucket}/{SparkConfig.SENSORS_PATH}"
        self.silver_path = f"s3a://{minio_bucket}/{SparkConfig.SILVER_PATH}"
        self.alerts_path = f"s3a://{minio_bucket}/{SparkConfig.ALERT_PATH}"
        
        # Streaming queries
        self.avg_query: Optional[StreamingQuery] = None
        self.alert_query: Optional[StreamingQuery] = None
    
    def is_data_directory_ready(self) -> bool:
        """Check if the sensors data directory exists and is accessible."""
        try:
            # Try to access the sensors directory
            self.session_manager.spark.read.option("basePath", self.sensors_path).parquet(self.sensors_path)
            return True
        except Exception as e:
            logger.debug(f"Data directory not ready: {e}")
            return False
    
    def start_streams_safely(self) -> None:
        """Start streaming jobs with error handling."""
        try:
            self.start_temperature_stream()
            logger.info("Temperature streaming started successfully")
        except Exception as e:
            logger.error(f"Failed to start temperature stream: {e}")

        try:
            self.start_alert_stream()
            logger.info("Alert streaming started successfully")
        except Exception as e:
            logger.error(f"Failed to start alert stream: {e}")
    
    def ensure_streams_running(self) -> None:
        """Ensure streaming jobs are running, start them if not."""
        try:
            # Check temperature stream
            if self.avg_query is None or not self.avg_query.isActive:
                logger.info("Temperature stream not active, attempting to start...")
                self.start_temperature_stream()

            # Check alert stream
            if self.alert_query is None or not self.alert_query.isActive:
                logger.info("Alert stream not active, attempting to start...")
                self.start_alert_stream()

        except Exception as e:
            logger.error(f"Error ensuring streams are running: {e}")
    
    def start_temperature_stream(self) -> None:
        """Start the temperature averaging stream (5-minute windows)."""
        schema = SparkSchemas.get_sensor_schema()
        spark = self.session_manager.spark

        # Read streaming data
        raw_stream = (
            spark.readStream
            .schema(schema)
            .option("basePath", self.sensors_path)
            .option("maxFilesPerTrigger", SparkConfig.MAX_FILES_PER_TRIGGER)
            .parquet(f"{self.sensors_path}date=*/hour=*")
            .withColumn("timestamp", F.to_timestamp("timestamp"))
        )

        # Calculate 5-minute averages
        five_min_avg = (
            raw_stream
            .withWatermark("timestamp", SparkConfig.WATERMARK_DELAY)
            .groupBy(
                F.window("timestamp", "5 minutes").alias("time_window"),
                "sensorId"
            )
            .agg(F.round(F.avg("temperature"), 2).alias("avg_temp"))
            .selectExpr(
                "sensorId",
                "time_window.start as time_start",
                "avg_temp"
            )
        )

        # Write to Delta table
        self.avg_query = (
            five_min_avg.writeStream
            .format("delta")
            .option("path", self.silver_path)
            .option("checkpointLocation", f"s3a://{self.minio_bucket}/{SparkConfig.FIVE_MIN_AVG_CHECKPOINT}")
            .outputMode("complete")
            .trigger(processingTime=SparkConfig.TEMPERATURE_STREAM_TRIGGER)
            .start()
        )

    def start_alert_stream(self) -> None:
        """Start the temperature alert stream."""
        schema = SparkSchemas.get_sensor_schema()
        spark = self.session_manager.spark

        # Read streaming data
        raw_stream = (
            spark.readStream
            .schema(schema)
            .option("basePath", self.sensors_path)
            .option("maxFilesPerTrigger", SparkConfig.MAX_FILES_PER_TRIGGER)
            .parquet(f"{self.sensors_path}date=*/hour=*")
            .withColumn("event_time", F.to_timestamp("timestamp"))
        )

        # Filter for temperature alerts and deduplicate
        alerts = (
            raw_stream
            .filter(F.col("temperature") > SparkConfig.TEMP_THRESHOLD)
            .withColumn("alert_type", F.lit("TEMP_OVER_LIMIT"))
            .withColumn("alert_id", F.concat(F.col("sensorId"), F.lit("_"), F.col("event_time")))
            .withColumn("alert_time", F.current_timestamp())
            .dropDuplicates(["sensorId"])
            .select("sensorId", "temperature", "event_time", "alert_type")
        )

        # Write to Delta table
        self.alert_query = (
            alerts.writeStream
            .format("delta")
            .option("path", self.alerts_path)
            .option("checkpointLocation", f"s3a://{self.minio_bucket}/{SparkConfig.ALERT_STREAM_CHECKPOINT}")
            .option("mergeSchema", "true")
            .outputMode("append")
            .trigger(processingTime=SparkConfig.ALERT_STREAM_TRIGGER)
            .start()
        )
    
    def stop_streams(self) -> None:
        """Stop all streaming queries gracefully."""
        streams = [
            ("Temperature stream", self.avg_query),
            ("Alert stream", self.alert_query)
        ]
        
        for stream_name, query in streams:
            try:
                if query and query.isActive:
                    query.stop()
                    logger.info(f"{stream_name} stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping {stream_name.lower()}: {e}")
        
        # Reset queries
        self.avg_query = None
        self.alert_query = None
