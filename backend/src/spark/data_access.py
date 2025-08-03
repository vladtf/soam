"""
Data access operations for Spark data.
"""
import logging
from typing import Dict, Any
from pyspark.sql import functions as F

from .config import SparkConfig
from .session import SparkSessionManager

logger = logging.getLogger(__name__)


class DataAccessManager:
    """Manages data access operations for temperature and alert data."""
    
    def __init__(self, session_manager: SparkSessionManager, minio_bucket: str):
        """Initialize DataAccessManager."""
        self.session_manager = session_manager
        self.minio_bucket = minio_bucket
        
        # Build paths
        self.silver_path = f"s3a://{minio_bucket}/{SparkConfig.SILVER_PATH}"
        self.alerts_path = f"s3a://{minio_bucket}/{SparkConfig.ALERT_PATH}"
        self.sensors_path = f"s3a://{minio_bucket}/{SparkConfig.SENSORS_PATH}"
    
    def _handle_table_not_found_error(self, error: Exception) -> bool:
        """Check if the error indicates a table/path not found."""
        error_str = str(error).lower()
        error_type = str(type(error))
        
        return (
            "path does not exist" in error_str or 
            "not found" in error_str or 
            "analysisexception" in error_type.lower()
        )

    def _create_table_not_ready_response(self, data_type: str) -> Dict[str, Any]:
        """Create a standard response for when tables are not ready."""
        return {
            "status": "success",
            "data": [],
            "message": f"{data_type} data not available yet. Please wait for data processing to begin."
        }
    
    def get_streaming_average_temperature(self, minutes: int = 30) -> Dict[str, Any]:
        """
        Get streaming average temperature data for the specified time window.
        
        Args:
            minutes: Time window in minutes (default: 30)
            
        Returns:
            Dict containing status and temperature data
        """
        if not self.session_manager.is_connected():
            logger.info("Spark connection lost, attempting to reconnect...")
            if not self.session_manager.reconnect():
                raise ConnectionError("Spark session is not available and reconnection failed")

        try:
            df = (
                self.session_manager.spark.read.format("delta")
                .load(self.silver_path)
                .filter(F.col("time_start") >= F.current_timestamp() - F.expr(f"INTERVAL {minutes} MINUTES"))
            )
            rows = df.collect()
            return {
                "status": "success",
                "data": [row.asDict() for row in rows]
            }
            
        except Exception as e:
            logger.error(f"Failed to get streaming average temperature: {e}")
            
            if self._handle_table_not_found_error(e):
                logger.info("Silver table not found, streaming likely hasn't started yet")
                return self._create_table_not_ready_response("Streaming")
            
            # Try reconnecting and retry once
            if self.session_manager.reconnect():
                try:
                    df = (
                        self.session_manager.spark.read.format("delta")
                        .load(self.silver_path)
                        .filter(F.col("time_start") >= F.current_timestamp() - F.expr(f"INTERVAL {minutes} MINUTES"))
                    )
                    rows = df.collect()
                    return {
                        "status": "success", 
                        "data": [row.asDict() for row in rows]
                    }
                except Exception as retry_e:
                    logger.error(f"Retry also failed: {retry_e}")
                    if self._handle_table_not_found_error(retry_e):
                        return self._create_table_not_ready_response("Streaming")
                    raise
            else:
                raise

    def get_temperature_alerts(self, since_minutes: int = 60) -> Dict[str, Any]:
        """
        Get recent temperature alerts.
        
        Args:
            since_minutes: Time window in minutes (default: 60)
            
        Returns:
            Dict containing status and alert data
        """
        if not self.session_manager.is_connected():
            logger.info("Spark connection lost, attempting to reconnect...")
            if not self.session_manager.reconnect():
                raise ConnectionError("Spark session is not available and reconnection failed")

        try:
            df = (
                self.session_manager.spark.read.format("delta")
                .load(self.alerts_path)
                .filter(F.col("event_time") >= F.current_timestamp() - F.expr(f"INTERVAL {since_minutes} minutes"))
            )
            return {
                "status": "success",
                "data": [row.asDict() for row in df.collect()]
            }
            
        except Exception as e:
            logger.error(f"Failed to get temperature alerts: {e}")
            
            if self._handle_table_not_found_error(e):
                logger.info("Alerts table not found, streaming likely hasn't started yet")
                return self._create_table_not_ready_response("Alert")
            
            # Try reconnecting and retry once
            if self.session_manager.reconnect():
                try:
                    df = (
                        self.session_manager.spark.read.format("delta")
                        .load(self.alerts_path)
                        .filter(F.col("event_time") >= F.current_timestamp() - F.expr(f"INTERVAL {since_minutes} minutes"))
                    )
                    return {
                        "status": "success",
                        "data": [row.asDict() for row in df.collect()]
                    }
                except Exception as retry_e:
                    logger.error(f"Retry also failed: {retry_e}")
                    if self._handle_table_not_found_error(retry_e):
                        return self._create_table_not_ready_response("Alert")
                    raise
            else:
                raise
