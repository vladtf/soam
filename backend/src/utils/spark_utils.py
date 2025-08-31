"""
Spark utilities for consistent session management and configuration.
"""
import os
from typing import Optional, Dict, Any
from pyspark.sql import SparkSession
from pyspark.conf import SparkConf

from src.utils.logging import get_logger

logger = get_logger(__name__)


def get_spark_config(app_name: str, additional_config: Optional[Dict[str, str]] = None) -> SparkConf:
    """
    Get standardized Spark configuration.
    
    Args:
        app_name: Name of the Spark application
        additional_config: Optional additional configuration parameters
        
    Returns:
        Configured SparkConf object
    """
    conf = SparkConf()
    
    # Base configuration
    base_config = {
        "spark.app.name": app_name,
        "spark.sql.warehouse.dir": "/tmp/spark-warehouse",
        "spark.sql.adaptive.enabled": "true",
        "spark.sql.adaptive.coalescePartitions.enabled": "true",
        "spark.sql.streaming.checkpointLocation": "/tmp/spark-checkpoints",
        "spark.hadoop.fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",
        "spark.hadoop.fs.s3a.endpoint": os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
        "spark.hadoop.fs.s3a.access.key": os.getenv("MINIO_ACCESS_KEY", "minio"),
        "spark.hadoop.fs.s3a.secret.key": os.getenv("MINIO_SECRET_KEY", "minio123"),
        "spark.hadoop.fs.s3a.path.style.access": "true",
        "spark.hadoop.fs.s3a.connection.ssl.enabled": "false"
    }
    
    # Add additional config if provided
    if additional_config:
        base_config.update(additional_config)
    
    # Set all configuration
    for key, value in base_config.items():
        conf.set(key, value)
    
    return conf


def create_spark_session(app_name: str, additional_config: Optional[Dict[str, str]] = None) -> SparkSession:
    """
    Create a Spark session with standardized configuration.
    
    Args:
        app_name: Name of the Spark application
        additional_config: Optional additional configuration parameters
        
    Returns:
        Configured SparkSession
    """
    try:
        conf = get_spark_config(app_name, additional_config)
        
        spark = SparkSession.builder \
            .config(conf=conf) \
            .getOrCreate()
        
        logger.info(f"✅ Spark session created successfully for {app_name}")
        return spark
    
    except Exception as e:
        logger.error(f"❌ Failed to create Spark session for {app_name}: {str(e)}")
        raise


def stop_spark_session(spark: SparkSession, app_name: str) -> None:
    """
    Safely stop a Spark session.
    
    Args:
        spark: SparkSession to stop
        app_name: Application name for logging
    """
    try:
        if spark:
            spark.stop()
            logger.info(f"✅ Spark session stopped successfully for {app_name}")
    except Exception as e:
        logger.warning(f"⚠️ Error stopping Spark session for {app_name}: {str(e)}")


def check_spark_connectivity(spark: SparkSession) -> bool:
    """
    Check if Spark session is healthy and connected.
    
    Args:
        spark: SparkSession to check
        
    Returns:
        True if healthy, False otherwise
    """
    try:
        # Try a simple operation
        spark.range(1).count()
        return True
    except Exception as e:
        logger.warning(f"⚠️ Spark connectivity check failed: {str(e)}")
        return False


def log_spark_info(spark: SparkSession, operation: str) -> None:
    """
    Log Spark session information.
    
    Args:
        spark: SparkSession to log info for
        operation: Operation name for context
    """
    try:
        app_id = spark.sparkContext.applicationId
        app_name = spark.sparkContext.appName
        master = spark.sparkContext.master
        
        logger.info(f"🔍 Spark {operation} - App: {app_name}, ID: {app_id}, Master: {master}")
    except Exception as e:
        logger.warning(f"⚠️ Could not log Spark info for {operation}: {str(e)}")


def get_streaming_config(checkpoint_location: Optional[str] = None) -> Dict[str, str]:
    """
    Get configuration specific to Spark Streaming.
    
    Args:
        checkpoint_location: Custom checkpoint location
        
    Returns:
        Streaming-specific configuration
    """
    base_checkpoint = checkpoint_location or "/tmp/spark-checkpoints"
    
    return {
        "spark.sql.streaming.checkpointLocation": base_checkpoint,
        "spark.sql.streaming.forceDeleteTempCheckpointLocation": "true",
        "spark.sql.streaming.stateStore.maintenanceInterval": "60s",
        "spark.sql.streaming.statefulOperator.checkCorrectness.enabled": "false"
    }


def create_streaming_spark_session(app_name: str, checkpoint_location: Optional[str] = None) -> SparkSession:
    """
    Create a Spark session optimized for streaming applications.
    
    Args:
        app_name: Name of the streaming application
        checkpoint_location: Custom checkpoint location
        
    Returns:
        Configured SparkSession for streaming
    """
    streaming_config = get_streaming_config(checkpoint_location)
    return create_spark_session(app_name, streaming_config)
