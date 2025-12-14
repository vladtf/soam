"""
Configuration constants and schemas for Spark operations.
"""
from pyspark.sql import types as T

class SparkConfig:
    """Configuration constants for Spark operations."""

    # Temperature thresholds
    TEMP_THRESHOLD = 30.0  # °C - Temperature threshold for alerts

    # Storage paths (relative to bucket) - using medallion architecture
    # Bronze: Raw data from ingestor
    BRONZE_PATH = "bronze"
    
    # Silver: Enriched/processed data
    ENRICHED_PATH = "silver/enriched"
    
    # Gold: Final aggregations and computed metrics
    GOLD_TEMP_AVG_PATH = "gold/temperature_averages"
    GOLD_ALERTS_PATH = "gold/temperature_alerts"

    # Checkpoint paths
    CHECKPOINT_BASE = "_ckpt"
    # Gold layer checkpoints
    GOLD_TEMP_AVG_CHECKPOINT = f"{CHECKPOINT_BASE}/gold_temp_avg"
    GOLD_ALERT_CHECKPOINT = f"{CHECKPOINT_BASE}/gold_alerts"
    # Silver layer checkpoints
    ENRICH_STREAM_CHECKPOINT = f"{CHECKPOINT_BASE}/enrich_stream"

    # Stream processing settings (tuned for high throughput)
    TEMPERATURE_STREAM_TRIGGER = "30 seconds"
    ALERT_STREAM_TRIGGER = "30 seconds"
    # Enrichment stream trigger - more frequent for lower latency
    ENRICH_STREAM_TRIGGER = "30 seconds"
    # Increased files per trigger for higher throughput under load
    MAX_FILES_PER_TRIGGER = 100
    WATERMARK_DELAY = "30 seconds"

    # Average computation window configuration
    AVG_WINDOW = "1 minute"      # compute averages over this window
    AVG_SLIDE = "1 minute"      # update results this often (sliding window)

    # Connection timeouts
    SPARK_MASTER_TIMEOUT = 10  # seconds


class SparkSchemas:
    """Spark schemas for data structures."""

    @staticmethod
    def get_union_schema() -> T.StructType:
        """Get the union schema for flexible sensor data storage.
        
        This schema supports storing arbitrary sensor data as JSON strings
        and normalized data as typed values.
        """
        return T.StructType([
            T.StructField("ingestion_id", T.StringType(), nullable=False),
            T.StructField("timestamp", T.TimestampType(), nullable=False),
            T.StructField("sensor_data", T.MapType(T.StringType(), T.StringType()), nullable=True),
            T.StructField("normalized_data", T.MapType(T.StringType(), T.DoubleType()), nullable=True)
        ])

    @staticmethod
    def get_enriched_union_schema() -> T.StructType:
        """Get the enriched union schema for processed sensor data."""
        return T.StructType([
            T.StructField("ingestion_id", T.StringType(), nullable=False),
            T.StructField("timestamp", T.TimestampType(), nullable=False),
            T.StructField("event_time", T.TimestampType(), nullable=False),
            T.StructField("sensor_data", T.MapType(T.StringType(), T.StringType()), nullable=True),
            T.StructField("normalized_data", T.MapType(T.StringType(), T.DoubleType()), nullable=True),
            # Enrichment fields
            T.StructField("ingest_ts", T.TimestampType(), nullable=True),
            T.StructField("ingest_date", T.DateType(), nullable=True),
            T.StructField("ingest_hour", T.StringType(), nullable=True),
            T.StructField("source", T.StringType(), nullable=True),
            T.StructField("site", T.StringType(), nullable=True)
        ])
