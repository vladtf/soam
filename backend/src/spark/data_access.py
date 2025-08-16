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
        """Initialize DataAccessManager.
        
        Args:
            session_manager: Spark session manager
            minio_bucket: MinIO bucket name
        """
        self.session_manager = session_manager
        self.minio_bucket = minio_bucket

        # Build paths
        # Gold layer paths (primary)
        self.gold_temp_avg_path = f"s3a://{minio_bucket}/{SparkConfig.GOLD_TEMP_AVG_PATH}"
        self.gold_alerts_path = f"s3a://{minio_bucket}/{SparkConfig.GOLD_ALERTS_PATH}"
        # Silver layer paths
        self.enriched_path = f"s3a://{minio_bucket}/{SparkConfig.ENRICHED_PATH}"
        # Bronze layer paths
        self.bronze_path = f"s3a://{minio_bucket}/{SparkConfig.BRONZE_PATH}"
    
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
                .load(self.gold_temp_avg_path)
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
                logger.info("Gold temperature averages table not found, streaming likely hasn't started yet")
                return self._create_table_not_ready_response("Temperature")
            else:
                raise e

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
                .load(self.gold_alerts_path)
                .filter(F.col("event_time") >= F.current_timestamp() - F.expr(f"INTERVAL {since_minutes} minutes"))
            )
            return {
                "status": "success",
                "data": [row.asDict() for row in df.collect()]
            }
            
        except Exception as e:
            logger.error(f"Failed to get temperature alerts: {e}")
            
            if self._handle_table_not_found_error(e):
                logger.info("Gold alerts table not found, streaming likely hasn't started yet")
                return self._create_table_not_ready_response("Alert")
            
            # Try reconnecting and retry once
            if self.session_manager.reconnect():
                try:
                    df = (
                        self.session_manager.spark.read.format("delta")
                        .load(self.gold_alerts_path)
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

    def get_enrichment_summary_union(self, minutes: int = 10) -> Dict[str, Any]:
        """
        Get enrichment summary from union schema data.
        
        Args:
            minutes: Time window in minutes to summarize
            
        Returns:
            Dict containing enrichment summary information in the expected frontend format
        """
        # Initialize result with the expected structure
        result: Dict[str, Any] = {
            "registered_total": 0,
            "registered_any_partition": False,
            "registered_by_partition": {},
            "enriched": {
                "exists": False,
                "recent_rows": 0,
                "recent_sensors": 0,
                "sample_sensors": [],
                "matched_sensors": 0,
            },
            "gold": {
                "exists": False,
                "recent_rows": 0,
                "recent_sensors": 0,
            },
        }

        # Load device registrations (enabled)
        try:
            from sqlalchemy.orm import sessionmaker
            from src.database.database import engine
            from src.database.models import Device
            SessionLocal = sessionmaker(bind=engine)
            db = SessionLocal()
            try:
                device_rows = db.query(Device.ingestion_id).filter(Device.enabled == True).all()
                result["registered_total"] = len(device_rows)
                result["registered_any_partition"] = any(iid is None for (iid,) in device_rows)
                specific_ids = [iid for (iid,) in device_rows if iid is not None]
                by_partition: dict[str, int] = {}
                for iid in specific_ids:
                    by_partition[str(iid)] = by_partition.get(str(iid), 0) + 1
                result["registered_by_partition"] = by_partition
            finally:
                db.close()
        except Exception as e:
            logger.error("Failed to load devices for enrichment summary: %s", e)

        try:
            spark = self.session_manager.spark
            
            # Calculate time bounds
            current_time = F.current_timestamp()
            time_bound = current_time - F.expr(f"INTERVAL {minutes} MINUTES")
            
            # Try to read enriched union data
            try:
                enriched_df = (
                    spark.read
                    .format("delta")
                    .load(self.enriched_path)
                    .filter(F.col("ingest_ts") >= time_bound)
                )
                
                result["enriched"]["exists"] = True
                
                if not enriched_df.rdd.isEmpty():
                    # Extract sensorId from union schema
                    analysis_df = enriched_df.withColumn(
                        "sensorId",
                        F.coalesce(
                            enriched_df.sensor_data.getItem("sensorId"),
                            enriched_df.sensor_data.getItem("sensorid"), 
                            enriched_df.sensor_data.getItem("sensor_id"),
                            enriched_df.ingestion_id
                        )
                    )
                    
                    # Aggregate metrics
                    summary = analysis_df.agg(
                        F.count("*").alias("total_records"),
                        F.countDistinct("sensorId").alias("unique_sensors")
                    ).collect()[0]
                    
                    # Get sample sensors
                    sample_sensors = (
                        analysis_df
                        .select("sensorId")
                        .distinct()
                        .limit(5)
                        .rdd.map(lambda row: row.sensorId)
                        .collect()
                    )
                    
                    result["enriched"]["recent_rows"] = summary["total_records"]
                    result["enriched"]["recent_sensors"] = summary["unique_sensors"]
                    result["enriched"]["sample_sensors"] = [s for s in sample_sensors if s]
                    result["enriched"]["matched_sensors"] = summary["unique_sensors"]  # For union schema, assume all are matched
                    
            except Exception as e:
                if self._handle_table_not_found_error(e):
                    logger.info("Enriched table not found, streaming likely hasn't started yet")
                else:
                    logger.error(f"Error reading enriched data: {e}")

            # Try to read gold temperature averages
            try:
                gold_df = (
                    spark.read
                    .format("delta")
                    .load(self.gold_temp_avg_path)
                    .filter(F.col("time_start") >= time_bound)
                )
                
                result["gold"]["exists"] = True
                
                if not gold_df.rdd.isEmpty():
                    gold_summary = gold_df.agg(
                        F.count("*").alias("total_records"),
                        F.countDistinct("sensorId").alias("unique_sensors")
                    ).collect()[0]
                    
                    result["gold"]["recent_rows"] = gold_summary["total_records"]
                    result["gold"]["recent_sensors"] = gold_summary["unique_sensors"]
                    
            except Exception as e:
                if self._handle_table_not_found_error(e):
                    logger.info("Gold temperature averages table not found, streaming likely hasn't started yet")
                else:
                    logger.error(f"Error reading gold data: {e}")

            return {
                "status": "success",
                "data": result,
                "message": f"Enrichment summary for last {minutes} minutes"
            }
            
        except Exception as e:
            logger.error(f"Error getting union enrichment summary: {e}")
            return {
                "status": "error", 
                "data": result,
                "message": f"Failed to get enrichment summary: {str(e)}"
            }

    def get_enrichment_summary(self, minutes: int = 10) -> Dict[str, Any]:
        """Summarize enrichment inputs and recent activity to help users verify computation inputs.

        Uses union schema implementation.
        """
        return self.get_enrichment_summary_union(minutes)

