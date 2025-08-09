"""
Spark streaming job management.
"""
import logging
from typing import Optional
from pyspark.sql import functions as F
from pyspark.sql.streaming import StreamingQuery

from .config import SparkConfig, SparkSchemas
from .cleaner import DataCleaner
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
        # New: enriched target path
        self.enriched_path = f"s3a://{minio_bucket}/{SparkConfig.ENRICHED_PATH}"
        
        # Streaming queries
        self.avg_query: Optional[StreamingQuery] = None
        self.alert_query: Optional[StreamingQuery] = None
        # New: enrichment query
        self.enrich_query: Optional[StreamingQuery] = None

        # Stable query names to enforce single instance per stream
        self.ENRICH_QUERY_NAME = "enrich_stream"
        self.AVG_QUERY_NAME = "five_min_avg_stream"
        self.ALERT_QUERY_NAME = "alert_stream"

    def _get_query_by_name(self, name: str) -> Optional[StreamingQuery]:
        """Return active StreamingQuery by name if present."""
        try:
            for q in self.session_manager.spark.streams.active:
                try:
                    if q.name == name:
                        return q
                except Exception:
                    continue
        except Exception:
            return None
        return None
    
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
            self.start_enrichment_stream()
            logger.info("Enrichment stream started successfully")
        except Exception as e:
            logger.error(f"Failed to start enrichment stream: {e}")
        
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
            # Ensure enrichment first, as downstream jobs rely on it
            if self.enrich_query is None or not self.enrich_query.isActive:
                logger.info("Enrichment stream not active, attempting to start...")
                existing = self._get_query_by_name(self.ENRICH_QUERY_NAME)
                if existing and existing.isActive:
                    self.enrich_query = existing
                else:
                    self.start_enrichment_stream()

            # Check temperature stream
            if self.avg_query is None or not self.avg_query.isActive:
                logger.info("Temperature stream not active, attempting to start...")
                existing = self._get_query_by_name(self.AVG_QUERY_NAME)
                if existing and existing.isActive:
                    self.avg_query = existing
                else:
                    self.start_temperature_stream()

            # Check alert stream
            if self.alert_query is None or not self.alert_query.isActive:
                logger.info("Alert stream not active, attempting to start...")
                existing = self._get_query_by_name(self.ALERT_QUERY_NAME)
                if existing and existing.isActive:
                    self.alert_query = existing
                else:
                    self.start_alert_stream()

        except Exception as e:
            logger.error(f"Error ensuring streams are running: {e}")
    
    def start_temperature_stream(self) -> None:
        """Start the temperature averaging stream (5-minute windows) from enriched data."""
        spark = self.session_manager.spark

        # Read streaming data from enriched silver delta
        enriched_stream = (
            spark.readStream
            .format("delta")
            .load(self.enriched_path)
        )

        # Calculate 5-minute averages based on event_time
        five_min_avg = (
            enriched_stream
            .withWatermark("event_time", SparkConfig.WATERMARK_DELAY)
            .groupBy(
                F.window("event_time", "5 minutes").alias("time_window"),
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
            .queryName(self.AVG_QUERY_NAME)
            .trigger(processingTime=SparkConfig.TEMPERATURE_STREAM_TRIGGER)
            .start()
        )

    def start_alert_stream(self) -> None:
        """Start the temperature alert stream from enriched data."""
        spark = self.session_manager.spark

        # Read streaming data from enriched silver delta
        enriched_stream = (
            spark.readStream
            .format("delta")
            .load(self.enriched_path)
        )

        # Filter for temperature alerts and deduplicate
        alerts = (
            enriched_stream
            .filter(F.col("temperature") > SparkConfig.TEMP_THRESHOLD)
            .withColumn("alert_type", F.lit("TEMP_OVER_LIMIT"))
            .withColumn("alert_id", F.concat(F.col("sensorId"), F.lit("_"), F.col("event_time")))
            .withColumn("alert_time", F.current_timestamp())
            .dropDuplicates(["sensorId"])  # keep latest per sensor
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
            .queryName(self.ALERT_QUERY_NAME)
            .trigger(processingTime=SparkConfig.ALERT_STREAM_TRIGGER)
            .start()
        )
    
    def start_enrichment_stream(self) -> None:
        """Start the enrichment stream: read raw sensors, add metadata, write silver/enriched."""
        spark = self.session_manager.spark
        cleaner = DataCleaner()

        # Try to infer schema from existing parquet files (batch read), fallback to known sensor schema
        try:
            static_df = (
                spark.read
                .option("basePath", self.sensors_path)
                .parquet(f"{self.sensors_path}date=*/hour=*")
            )
            inferred_schema = static_df.schema
            logger.info("Inferred raw sensors schema from existing files for streaming read")
        except Exception:
            inferred_schema = SparkSchemas.get_sensor_schema()
            logger.info("Falling back to predefined sensor schema for streaming read")

        # Read raw parquet with schema (required by structured streaming for file sources)
        raw_stream = (
            spark.readStream
            .schema(inferred_schema)
            .option("basePath", self.sensors_path)
            .option("maxFilesPerTrigger", SparkConfig.MAX_FILES_PER_TRIGGER)
            .parquet(f"{self.sensors_path}date=*/hour=*")
        )

        # Normalize/cleanup: lower-case columns and rename known variants
        normalized = cleaner.normalize_sensor_columns(raw_stream)

        # Cast to expected schema types (safe casts) and derive event time
        typed = (
            normalized
            .withColumn("sensorId", F.col("sensorId").cast("string"))
            .withColumn("temperature", F.col("temperature").cast("double"))
            .withColumn("humidity", F.col("humidity").cast("double"))
            .withColumn("timestamp", F.col("timestamp").cast("string"))
            .withColumn("event_time", F.to_timestamp("timestamp"))
        )

        # Example enrichment: add ingest_date, hour, and static metadata fields
        enriched = (
            typed
            .withColumn("ingest_ts", F.current_timestamp())
            .withColumn("ingest_date", F.to_date(F.col("event_time")))
            .withColumn("ingest_hour", F.date_format(F.col("event_time"), "HH"))
            # Add example metadata; replace with real lookups if needed
            .withColumn("source", F.lit("mqtt"))
            .withColumn("site", F.lit("default"))
            .select(
                "sensorId",
                "temperature",
                "humidity",
                "event_time",
                "ingest_ts",
                "ingest_date",
                "ingest_hour",
                "source",
                "site",
            )
        )

        # Avoid duplicate starts if another session/thread already launched it
        existing = self._get_query_by_name(self.ENRICH_QUERY_NAME)
        if existing and existing.isActive:
            self.enrich_query = existing
            return

        # Write enriched records to Delta in silver/enriched
        try:
            self.enrich_query = (
                enriched.writeStream
                .format("delta")
                .option("path", self.enriched_path)
                .option("checkpointLocation", f"s3a://{self.minio_bucket}/{SparkConfig.ENRICH_STREAM_CHECKPOINT}")
                .option("mergeSchema", "true")
                .outputMode("append")
                .queryName(self.ENRICH_QUERY_NAME)
                .trigger(processingTime=SparkConfig.ENRICH_STREAM_TRIGGER)
                .start()
            )
        except Exception as e:
            # If concurrent start detected, bind to the existing one
            if "SparkConcurrentModificationException" in str(e) or "CONCURRENT_QUERY" in str(e):
                logger.warning("Concurrent start detected for enrichment stream; reusing active query")
                existing = self._get_query_by_name(self.ENRICH_QUERY_NAME)
                if existing and existing.isActive:
                    self.enrich_query = existing
                    return
            # Re-raise if it's another kind of error
            raise
    
    def stop_streams(self) -> None:
        """Stop all streaming queries gracefully."""
        streams = [
            ("Enrichment stream", self.enrich_query),
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
        self.enrich_query = None
        self.avg_query = None
        self.alert_query = None
