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
        self.enriched_path = f"s3a://{minio_bucket}/{SparkConfig.ENRICHED_PATH}"
    
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

    def get_enrichment_summary(self, minutes: int = 10) -> Dict[str, Any]:
        """Summarize enrichment inputs and recent activity to help users verify computation inputs.

        Returns a dict with counts of registered devices, recent enriched rows and sensors,
        matched sensors vs registration, and stream/table existence hints.
        """
        # Spark session
        if not self.session_manager.is_connected() and not self.session_manager.reconnect():
            raise ConnectionError("Spark session is not available")

        # Load device registrations (enabled)
        try:
            from sqlalchemy.orm import sessionmaker
            from src.database.database import engine
            from src.database.models import Device
            SessionLocal = sessionmaker(bind=engine)
            db = SessionLocal()
            try:
                rows = db.query(Device.sensor_id, Device.ingestion_id).filter(Device.enabled == True).all()
                registered_total = len(rows)
                any_part = len([1 for (_sid, iid) in rows if iid is None])
                specific = [(sid, iid) for (sid, iid) in rows if iid is not None]
                by_partition: dict[str, int] = {}
                for _sid, iid in specific:
                    by_partition[str(iid)] = by_partition.get(str(iid), 0) + 1
            finally:
                db.close()
        except Exception as e:
            logger.error("Failed to load devices for enrichment summary: %s", e)
            registered_total = 0
            any_part = 0
            by_partition = {}
            rows = []

        result: Dict[str, Any] = {
            "registered_total": registered_total,
            "registered_any_partition": any_part,
            "registered_by_partition": by_partition,
            "enriched": {
                "exists": False,
                "recent_rows": 0,
                "recent_sensors": 0,
                "sample_sensors": [],
                "matched_sensors": 0,
            },
            "silver": {
                "exists": False,
                "recent_rows": 0,
                "recent_sensors": 0,
            },
        }

        # Enriched status
        try:
            df = (
                self.session_manager.spark.read.format("delta")
                .load(self.enriched_path)
                .filter(F.col("event_time") >= F.current_timestamp() - F.expr(f"INTERVAL {minutes} MINUTES"))
            )
            recent_rows = df.count()
            sensors_df = df.select("sensorId").distinct()
            recent_sensors = sensors_df.count()
            sample = [r[0] for r in sensors_df.limit(10).collect()]

            # Matched sensors with registration
            try:
                allowed_pairs = rows  # from registration above
                matched = 0
                if allowed_pairs:
                    specific_pairs = [(sid, iid) for (sid, iid) in allowed_pairs if iid is not None]
                    ids_any = list({sid for (sid, iid) in allowed_pairs if iid is None})
                    matched_any = df.select("sensorId").where(F.col("sensorId").isin(ids_any)).distinct() if ids_any else None
                    matched_spec = None
                    if specific_pairs and "ingestion_id" in df.columns:
                        allowed_df = self.session_manager.spark.createDataFrame(specific_pairs, ["sensorId", "ingestion_id"]).dropDuplicates()
                        matched_spec = df.select("sensorId", "ingestion_id").join(allowed_df, ["sensorId", "ingestion_id"], "inner").select("sensorId").distinct()
                    elif specific_pairs:
                        ids_spec = list({sid for (sid, _iid) in specific_pairs})
                        matched_spec = df.select("sensorId").where(F.col("sensorId").isin(ids_spec)).distinct()
                    if matched_any is not None and matched_spec is not None:
                        matched = matched_any.unionByName(matched_spec).distinct().count()
                    elif matched_any is not None:
                        matched = matched_any.count()
                    elif matched_spec is not None:
                        matched = matched_spec.count()
            except Exception:
                matched = 0

            result["enriched"] = {
                "exists": True,
                "recent_rows": int(recent_rows),
                "recent_sensors": int(recent_sensors),
                "sample_sensors": sample,
                "matched_sensors": int(matched),
            }
        except Exception as e:
            logger.info("Enriched table not available yet: %s", e)

        # Silver (averages) status
        try:
            sdf = (
                self.session_manager.spark.read.format("delta")
                .load(self.silver_path)
                .filter(F.col("time_start") >= F.current_timestamp() - F.expr(f"INTERVAL {minutes} MINUTES"))
            )
            result["silver"] = {
                "exists": True,
                "recent_rows": int(sdf.count()),
                "recent_sensors": int(sdf.select("sensorId").distinct().count()),
            }
        except Exception as e:
            logger.info("Silver table not available yet: %s", e)

        return {"status": "success", "data": result}
