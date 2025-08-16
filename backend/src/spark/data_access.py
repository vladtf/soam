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
        self.silver_path = f"s3a://{minio_bucket}/{SparkConfig.SILVER_PATH}"
        self.alerts_path = f"s3a://{minio_bucket}/{SparkConfig.ALERT_PATH}"
        self.bronze_path = f"s3a://{minio_bucket}/{SparkConfig.BRONZE_PATH}"
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
            "silver": {
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

            # Try to read silver data (5-minute averages)
            try:
                silver_df = (
                    spark.read
                    .format("delta")
                    .load(self.silver_path)
                    .filter(F.col("window_start") >= time_bound)
                )
                
                result["silver"]["exists"] = True
                
                if not silver_df.rdd.isEmpty():
                    silver_summary = silver_df.agg(
                        F.count("*").alias("total_records"),
                        F.countDistinct("sensorId").alias("unique_sensors")
                    ).collect()[0]
                    
                    result["silver"]["recent_rows"] = silver_summary["total_records"]
                    result["silver"]["recent_sensors"] = silver_summary["unique_sensors"]
                    
            except Exception as e:
                if self._handle_table_not_found_error(e):
                    logger.info("Silver table not found, streaming likely hasn't started yet")
                else:
                    logger.error(f"Error reading silver data: {e}")

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

    def get_enrichment_summary_legacy(self, minutes: int = 10) -> Dict[str, Any]:
        """Summarize enrichment inputs and recent activity (legacy schema implementation).

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
                device_rows = db.query(Device.ingestion_id).filter(Device.enabled == True).all()  # list of (ingestion_id,)
                registered_total = len(device_rows)
                any_part = any(iid is None for (iid,) in device_rows)
                specific_ids = [iid for (iid,) in device_rows if iid is not None]
                by_partition: dict[str, int] = {}
                for iid in specific_ids:
                    by_partition[str(iid)] = by_partition.get(str(iid), 0) + 1
            finally:
                db.close()
        except Exception as e:
            logger.error("Failed to load devices for enrichment summary: %s", e)
            registered_total = 0
            any_part = 0
            by_partition = {}
            device_rows = []

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

            # Debug: Check what ingestion_id values are actually in the data
            ingestion_ids_in_data = []
            if "ingestion_id" in df.columns:
                ingestion_ids_in_data = [r[0] for r in df.select("ingestion_id").distinct().limit(10).collect()]

            # Matched sensors with registration (simplified: only ingestion_id registrations exist)
            matched = 0
            try:
                registered_ingestion_ids = [iid for (iid,) in device_rows if iid is not None]
                wildcard = any(iid is None for (iid,) in device_rows)
                
                logger.info(f"Enrichment debug - Registered devices: {registered_ingestion_ids}")
                logger.info(f"Enrichment debug - Ingestion IDs in data: {ingestion_ids_in_data}")
                logger.info(f"Enrichment debug - Wildcard registration: {wildcard}")
                
                if wildcard:
                    # At least one wildcard device => all recent sensors count as matched
                    matched = recent_sensors
                elif registered_ingestion_ids and "ingestion_id" in df.columns:
                    matched = (
                        df.select("sensorId", "ingestion_id")
                        .where(F.col("ingestion_id").isin([str(x) for x in registered_ingestion_ids]))
                        .select("sensorId")
                        .distinct()
                        .count()
                    )
            except Exception as e:
                logger.error(f"Error calculating matched sensors: {e}")
                matched = 0

            result["enriched"] = {
                "exists": True,
                "recent_rows": int(recent_rows),
                "recent_sensors": int(recent_sensors),
                "sample_sensors": sample,
                "matched_sensors": int(matched),
                "debug_ingestion_ids_in_data": ingestion_ids_in_data,
                "debug_registered_ingestion_ids": [iid for (iid,) in device_rows if iid is not None],
            }
            
            # Add detailed diagnosis if there's a mismatch (more than registered sensors being processed)
            if recent_sensors > len(device_rows) and len(device_rows) > 0:
                try:
                    from .diagnostics_enhanced import diagnose_enrichment_filtering
                    diagnosis = diagnose_enrichment_filtering(self.session_manager, self.enriched_path)
                    result["enriched"]["detailed_diagnosis"] = diagnosis
                    logger.warning(f"Enrichment filtering issue detected: {recent_sensors} sensors processed vs {len(device_rows)} registered devices")
                except Exception as diag_e:
                    logger.error(f"Failed to run detailed diagnosis: {diag_e}")
                    result["enriched"]["diagnosis_error"] = str(diag_e)
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
