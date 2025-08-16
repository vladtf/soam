"""
Configuration constants and schemas for Spark operations.
"""
from pyspark.sql import types as T


class SparkConfig:
    """Configuration constants for Spark operations."""

    # Temperature thresholds
    TEMP_THRESHOLD = 30.0  # °C - Temperature threshold for alerts

    # Storage paths (relative to bucket)
    ALERT_PATH = "silver/temperature_alerts"
    SILVER_PATH = "silver/five_min_avg"
    SENSORS_PATH = "sensors/"
    # New: enriched data written by backend enrichment stream
    ENRICHED_PATH = "silver/enriched"

    # Checkpoint paths
    CHECKPOINT_BASE = "_ckpt"
    FIVE_MIN_AVG_CHECKPOINT = f"{CHECKPOINT_BASE}/five_min_avg"
    ALERT_STREAM_CHECKPOINT = f"{CHECKPOINT_BASE}/alert_stream"
    # New: enrichment checkpoint
    ENRICH_STREAM_CHECKPOINT = f"{CHECKPOINT_BASE}/enrich_stream"

    # Stream processing settings (tuned for faster feedback)
    TEMPERATURE_STREAM_TRIGGER = "1 minute"
    ALERT_STREAM_TRIGGER = "1 minute"
    # New: enrichment stream trigger
    ENRICH_STREAM_TRIGGER = "1 minute"
    MAX_FILES_PER_TRIGGER = 20
    WATERMARK_DELAY = "30 seconds"

    # Average computation window configuration
    AVG_WINDOW = "1 minute"      # compute averages over this window
    AVG_SLIDE = "1 minute"      # update results this often (sliding window)

    # Connection timeouts
    SPARK_MASTER_TIMEOUT = 10  # seconds


class SparkSchemas:
    """Spark schemas for data structures."""

    @staticmethod
    def get_sensor_schema() -> T.StructType:
        """Get the schema for sensor data (legacy format)."""
        return T.StructType([
            T.StructField("sensorId", T.StringType()),
            T.StructField("temperature", T.DoubleType()),
            # New: include humidity when available from ingestor
            T.StructField("humidity", T.DoubleType()),
            T.StructField("timestamp", T.StringType())
        ])

    @staticmethod
    def get_comprehensive_raw_schema() -> T.StructType:
        """Get a comprehensive raw sensor schema that includes all possible sensor fields.
        
        This prevents schema inference issues when different sensor types have different fields.
        All fields are nullable to allow for missing columns in specific sensor types.
        """
        return T.StructType([
            # Core fields (always present)
            T.StructField("ingestion_id", T.StringType(), nullable=False),
            T.StructField("timestamp", T.StringType(), nullable=True),  # String initially, converted later
            T.StructField("sensor_id", T.StringType(), nullable=True),
            T.StructField("topic", T.StringType(), nullable=True),
            T.StructField("date", T.DateType(), nullable=True),
            T.StructField("hour", T.LongType(), nullable=True),  # Changed from IntegerType to LongType
            
            # Temperature sensor fields
            T.StructField("temperature", T.DoubleType(), nullable=True),
            T.StructField("humidity", T.DoubleType(), nullable=True),
            
            # Air quality sensor fields
            T.StructField("location", T.StringType(), nullable=True),
            T.StructField("carbon_monoxide_ppm", T.DoubleType(), nullable=True),
            T.StructField("nitrogen_dioxide_ppm", T.DoubleType(), nullable=True),
            T.StructField("particulate_matter_2_5_ug_m3", T.DoubleType(), nullable=True),
            
            # Traffic sensor fields
            T.StructField("vehicle_count", T.LongType(), nullable=True),  # Changed from IntegerType to LongType
            T.StructField("avg_speed_kmh", T.DoubleType(), nullable=True),
            T.StructField("congestion_level", T.StringType(), nullable=True),
            
            # Smart bin sensor fields
            T.StructField("fill_level_percent", T.DoubleType(), nullable=True),
            T.StructField("weight_kg", T.DoubleType(), nullable=True),
            T.StructField("last_emptied", T.StringType(), nullable=True),
            
            # Generic fields for future sensors
            T.StructField("value", T.DoubleType(), nullable=True),
            T.StructField("unit", T.StringType(), nullable=True),
            T.StructField("status", T.StringType(), nullable=True),
        ])

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
