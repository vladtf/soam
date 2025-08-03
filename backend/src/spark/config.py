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
    
    # Checkpoint paths
    CHECKPOINT_BASE = "_ckpt"
    FIVE_MIN_AVG_CHECKPOINT = f"{CHECKPOINT_BASE}/five_min_avg"
    ALERT_STREAM_CHECKPOINT = f"{CHECKPOINT_BASE}/alert_stream"
    
    # Stream processing settings
    TEMPERATURE_STREAM_TRIGGER = "1 minute"
    ALERT_STREAM_TRIGGER = "30 seconds"
    MAX_FILES_PER_TRIGGER = 20
    WATERMARK_DELAY = "1 minute"
    
    # Connection timeouts
    SPARK_MASTER_TIMEOUT = 10  # seconds


class SparkSchemas:
    """Spark schemas for data structures."""
    
    @staticmethod
    def get_sensor_schema() -> T.StructType:
        """Get the schema for sensor data."""
        return T.StructType([
            T.StructField("sensorId", T.StringType()),
            T.StructField("temperature", T.DoubleType()),
            T.StructField("timestamp", T.StringType())
        ])
