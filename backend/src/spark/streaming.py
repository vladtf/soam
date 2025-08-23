"""
Spark streaming job management.
"""
import logging
from typing import Optional
from pyspark.sql import functions as F
from pyspark.sql.streaming import StreamingQuery

from .config import SparkConfig, SparkSchemas
from .enrichment.cleaner import DataCleaner
from .session import SparkSessionManager
from .enrichment import EnrichmentManager
from src.utils.settings_manager import settings_manager

logger = logging.getLogger(__name__)


def get_temperature_threshold() -> float:
    """Get the temperature threshold from database settings or fallback to default."""
    return settings_manager.get_temperature_threshold(SparkConfig.TEMP_THRESHOLD)


class StreamingManager:
    """Manages Spark streaming jobs for temperature data and alerts."""

    def __init__(self, session_manager: SparkSessionManager, minio_bucket: str):
        """Initialize StreamingManager.

        Args:
            session_manager: Spark session manager
            minio_bucket: MinIO bucket name
        """
        self.session_manager = session_manager
        self.minio_bucket = minio_bucket

        # Build paths
        self.bronze_path = f"s3a://{minio_bucket}/{SparkConfig.BRONZE_PATH}/"
        # Silver layer paths
        self.enriched_path = f"s3a://{minio_bucket}/{SparkConfig.ENRICHED_PATH}/"
        # Gold layer paths
        self.gold_temp_avg_path = f"s3a://{minio_bucket}/{SparkConfig.GOLD_TEMP_AVG_PATH}/"
        self.gold_alerts_path = f"s3a://{minio_bucket}/{SparkConfig.GOLD_ALERTS_PATH}/"

        # Initialize enrichment manager
        self.enrichment_manager = EnrichmentManager(
            self.session_manager.spark,
            minio_bucket,
            self.bronze_path,
            self.enriched_path
        )

        # Streaming queries
        self.avg_query: Optional[StreamingQuery] = None
        self.alert_query: Optional[StreamingQuery] = None

        # Query names (union schema is now default)
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
        """Check if the bronze data directory exists and is accessible."""
        try:
            # Try to access the bronze directory - even if empty, this will work
            self.session_manager.spark.read.option("basePath", self.bronze_path).option("recursiveFileLookup", "true").option("pathGlobFilter", "*.parquet").parquet(self.bronze_path)
            return True
        except Exception as e:
            # Check if it's just an empty directory (which is fine)
            if "Path does not exist" in str(e) or "Unable to infer schema" in str(e):
                logger.info(f"Bronze directory empty or doesn't exist yet - this is normal for initial startup: {e}")
                return False
            else:
                logger.debug(f"Data directory not ready: {e}")
                return False

    def start_streams_safely(self) -> None:
        """Start streaming jobs with error handling."""
        try:
            self.enrichment_manager.start_enrichment_stream()
            logger.info("Union enrichment stream started successfully")
        except Exception as e:
            logger.error(f"Failed to start enrichment stream: {e}")

        try:
            self.start_temperature_stream()
            logger.info("Union temperature streaming started successfully")
        except Exception as e:
            logger.error(f"Failed to start temperature stream: {e}")

        try:
            self.start_alert_stream()
            logger.info("Union alert streaming started successfully")
        except Exception as e:
            logger.error(f"Failed to start alert stream: {e}")

    def ensure_streams_running(self) -> None:
        """Ensure streaming jobs are running, start them if not."""
        try:
            # Ensure enrichment first, as downstream jobs rely on it
            self.enrichment_manager.ensure_enrichment_running()

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
        """Start the temperature averaging stream from union schema enriched data."""
        spark = self.session_manager.spark

        # Read streaming data from enriched union delta
        try:
            enriched_stream = (
                spark.readStream
                .format("delta")
                .load(self.enriched_path)
            )
        except Exception as e:
            logger.info("Enriched union delta not available yet, skipping temperature stream start: %s", e)
            return

        # Extract temperature from union schema and filter valid values
        from .enrichment.union_schema import UnionSchemaTransformer

        temp_stream = UnionSchemaTransformer.extract_column_from_union(
            enriched_stream, "temperature", prefer_normalized=True
        )

        # Extract sensorId from sensor_data map
        temp_stream = temp_stream.withColumn(
            "sensorId",
            F.coalesce(
                temp_stream.sensor_data.getItem("sensorId"),
                temp_stream.sensor_data.getItem("sensorid"),
                temp_stream.sensor_data.getItem("sensor_id"),
                temp_stream.ingestion_id  # fallback to ingestion_id
            )
        )

        # Filter valid temperature readings
        valid_temp_stream = (
            temp_stream
            .filter((F.col("temperature").isNotNull()) & (~F.isnan(F.col("temperature"))))
            .withWatermark("event_time", SparkConfig.WATERMARK_DELAY)
        )

        # Calculate sliding window averages
        five_min_avg = (
            valid_temp_stream
            .groupBy(
                F.window("event_time", SparkConfig.AVG_WINDOW, SparkConfig.AVG_SLIDE).alias("time_window"),
                "sensorId"
            )
            .agg(F.round(F.avg("temperature"), 2).alias("avg_temp"))
            .selectExpr(
                "sensorId",
                "time_window.start as time_start",
                "avg_temp"
            )
        )

        # Ensure target Delta table exists in gold layer
        try:
            spark.read.format("delta").load(self.gold_temp_avg_path).limit(0)
        except Exception:
            from pyspark.sql import types as T
            empty_schema = T.StructType([
                T.StructField("sensorId", T.StringType()),
                T.StructField("time_start", T.TimestampType()),
                T.StructField("avg_temp", T.DoubleType()),
            ])
            empty_df = spark.createDataFrame([], empty_schema)
            (
                empty_df.write
                .format("delta")
                .mode("ignore")
                .option("overwriteSchema", "true")
                .save(self.gold_temp_avg_path)
            )

        # Write to Delta table in gold layer
        self.avg_query = (
            five_min_avg.writeStream
            .format("delta")
            .option("path", self.gold_temp_avg_path)
            .option("checkpointLocation", f"s3a://{self.minio_bucket}/{SparkConfig.GOLD_TEMP_AVG_CHECKPOINT}_union")
            .option("mergeSchema", "true")
            .outputMode("complete")
            .queryName(self.AVG_QUERY_NAME)
            .trigger(processingTime=SparkConfig.TEMPERATURE_STREAM_TRIGGER)
            .start()
        )

    def start_alert_stream(self) -> None:
        """Start the temperature alert stream from union schema enriched data."""
        spark = self.session_manager.spark

        # Read streaming data from enriched union delta
        try:
            enriched_stream = (
                spark.readStream
                .format("delta")
                .load(self.enriched_path)
            )
        except Exception as e:
            logger.info("Enriched union delta not available yet, skipping alert stream start: %s", e)
            return

        # Extract temperature and sensorId from union schema
        from .enrichment.union_schema import UnionSchemaTransformer

        alert_stream = UnionSchemaTransformer.extract_column_from_union(
            enriched_stream, "temperature", prefer_normalized=True
        )

        alert_stream = alert_stream.withColumn(
            "sensorId",
            F.coalesce(
                alert_stream.sensor_data.getItem("sensorId"),
                alert_stream.sensor_data.getItem("sensorid"),
                alert_stream.sensor_data.getItem("sensor_id"),
                alert_stream.ingestion_id
            )
        )

        # Filter for temperature alerts
        temp_threshold = get_temperature_threshold()
        logger.info(f"Using temperature threshold: {temp_threshold}°C")
        
        alerts = (
            alert_stream
            .filter((F.col("temperature").isNotNull()) & (~F.isnan(F.col("temperature"))))
            .filter(F.col("temperature") > temp_threshold)
            .withColumn("alert_type", F.lit("TEMP_OVER_LIMIT"))
            .withColumn("alert_id", F.concat(F.col("sensorId"), F.lit("_"), F.col("event_time")))
            .withColumn("alert_time", F.current_timestamp())
            .dropDuplicates(["sensorId"])
            .select("sensorId", "temperature", "event_time", "alert_type")
        )

        # Write to Delta table in gold layer
        self.alert_query = (
            alerts.writeStream
            .format("delta")
            .option("path", self.gold_alerts_path)
            .option("checkpointLocation", f"s3a://{self.minio_bucket}/{SparkConfig.GOLD_ALERT_CHECKPOINT}_union")
            .option("mergeSchema", "true")
            .outputMode("append")
            .queryName(self.ALERT_QUERY_NAME)
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

        # Stop enrichment stream
        self.enrichment_manager.stop_enrichment_stream()

        # Reset queries
        self.avg_query = None
        self.alert_query = None
