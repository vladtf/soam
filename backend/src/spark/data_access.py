"""
Data access operations for Spark data.
"""
import logging
import time
from typing import Dict, Any, List
from pyspark.sql import functions as F

from .config import SparkConfig
from .session import SparkSessionManager
from src import metrics as backend_metrics

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

        self.gold_temp_avg_path = f"s3a://{minio_bucket}/{SparkConfig.GOLD_TEMP_AVG_PATH}"
        self.gold_alerts_path = f"s3a://{minio_bucket}/{SparkConfig.GOLD_ALERTS_PATH}"
        self.enriched_path = f"s3a://{minio_bucket}/{SparkConfig.ENRICHED_PATH}"
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
            "data": [],
            "message": f"{data_type} data not available yet. Please wait for data processing to begin."
        }
    
    def get_streaming_average_temperature(self, minutes: int = 30) -> List[Dict[str, Any]]:
        """
        Get streaming average temperature data for the specified time window.
        
        Args:
            minutes: Time window in minutes (default: 30)
            
        Returns:
            List of temperature data records
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
                .orderBy(F.col("time_start").asc())  # Order by time ascending (oldest to newest)
            )
            rows = df.collect()
            result = [row.asDict() for row in rows]
            
            # Calculate sensor-to-gold latency for the most recent records
            self._record_sensor_to_gold_latency(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get streaming average temperature: {e}")
            
            if self._handle_table_not_found_error(e):
                logger.info("Gold temperature averages table not found, streaming likely hasn't started yet")
                return []  # Return empty list instead of wrapped response
            else:
                raise e

    def _record_sensor_to_gold_latency(self, rows: List[Dict[str, Any]]) -> None:
        """Record latency from sensor timestamp (window start) to gold layer availability.
        
        Also records enrichment-to-gold latency if min_enrichment_ts is available.
        
        The gold layer contains aggregated data with time_start representing the 
        window start time. The latency is calculated as current_time - time_start,
        which shows how long it takes for data to become available in gold layer.
        
        Args:
            rows: List of gold layer records containing time_start and optionally min_enrichment_ts
        """
        if not rows:
            return
            
        try:
            now = time.time()
            sensor_latencies = []
            enrichment_latencies = []
            
            recent_rows = rows[-5:] if len(rows) > 5 else rows
            
            for row in recent_rows:
                time_start = row.get("time_start")
                min_enrichment_ts = row.get("min_enrichment_ts")
                
                # Calculate sensor-to-gold latency
                if time_start is not None:
                    # Convert time_start to epoch seconds
                    if hasattr(time_start, 'timestamp'):
                        ts_epoch = time_start.timestamp()
                        latency = now - ts_epoch
                        # Only record reasonable latencies (0 to 1 hour)
                        if 0 <= latency <= 3600:
                            sensor_latencies.append(latency)
                
                if min_enrichment_ts is not None:
                    if hasattr(min_enrichment_ts, 'timestamp'):
                        enrich_epoch = min_enrichment_ts.timestamp()
                        enrich_latency = now - enrich_epoch
                        # Only record reasonable latencies (0 to 1 hour)
                        if 0 <= enrich_latency <= 3600:
                            enrichment_latencies.append(enrich_latency)
            
            for latency in sensor_latencies:
                backend_metrics.record_sensor_to_gold_latency(latency)
            
            for latency in enrichment_latencies:
                backend_metrics.record_enrichment_to_gold_latency(latency)
                
            if sensor_latencies:
                avg_latency = sum(sensor_latencies) / len(sensor_latencies)
                logger.debug(f"📊 Sensor-to-gold latency: avg={avg_latency:.2f}s (sampled {len(sensor_latencies)} windows)")
            
            if enrichment_latencies:
                avg_enrich_latency = sum(enrichment_latencies) / len(enrichment_latencies)
                logger.debug(f"📊 Enrichment-to-gold latency: avg={avg_enrich_latency:.2f}s (sampled {len(enrichment_latencies)} windows)")
                
        except Exception as e:
            logger.debug(f"Could not calculate gold layer latencies: {e}")

    def get_temperature_alerts(self, since_minutes: int = 60) -> List[Dict[str, Any]]:
        """
        Get recent temperature alerts.
        
        Args:
            since_minutes: Time window in minutes (default: 60)
            
        Returns:
            List of temperature alert records
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
                .orderBy(F.col("event_time").asc())  # Order by event time ascending (oldest to newest)
            )
            return [row.asDict() for row in df.collect()]
            
        except Exception as e:
            logger.error(f"Failed to get temperature alerts: {e}")
            
            if self._handle_table_not_found_error(e):
                logger.info("Gold alerts table not found, streaming likely hasn't started yet")
                return []  # Return empty list instead of wrapped response
            
            # Try reconnecting and retry once
            if self.session_manager.reconnect():
                try:
                    df = (
                        self.session_manager.spark.read.format("delta")
                        .load(self.gold_alerts_path)
                        .filter(F.col("event_time") >= F.current_timestamp() - F.expr(f"INTERVAL {since_minutes} minutes"))
                    )
                    return [row.asDict() for row in df.collect()]
                except Exception as retry_e:
                    logger.error(f"Retry also failed: {retry_e}")
                    if self._handle_table_not_found_error(retry_e):
                        return []  # Return empty list instead of wrapped response
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
            
            current_time = F.current_timestamp()
            time_bound = current_time - F.expr(f"INTERVAL {minutes} MINUTES")
            
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
                    from src.utils.spark_utils import extract_sensor_id
                    analysis_df = extract_sensor_id(enriched_df)
                    
                    summary = analysis_df.agg(
                        F.count("*").alias("total_records"),
                        F.countDistinct("sensorId").alias("unique_sensors")
                    ).collect()[0]
                    
                    sample_sensors = (
                        analysis_df
                        .select("sensorId")
                        .distinct()
                        .limit(5)
                        .rdd.map(lambda row: row.sensorId)
                        .collect()
                    )
                    
                    processing_metrics = self._calculate_processing_metrics(analysis_df, minutes)
                    streaming_metrics = self._get_streaming_metrics()
                    normalization_stats = self._get_normalization_stats(minutes)
                    data_quality = self._get_data_quality_metrics(analysis_df)
                    
                    result["enriched"]["recent_rows"] = summary["total_records"]
                    result["enriched"]["recent_sensors"] = summary["unique_sensors"]
                    result["enriched"]["sample_sensors"] = [s for s in sample_sensors if s]
                    result["enriched"]["matched_sensors"] = summary["unique_sensors"]  # For union schema, assume all are matched
                    result["enriched"]["processing_metrics"] = processing_metrics
                    result["enriched"]["streaming_metrics"] = streaming_metrics
                    result["enriched"]["normalization_stats"] = normalization_stats
                    result["enriched"]["data_quality"] = data_quality
                    
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

            return result
            
        except Exception as e:
            logger.error(f"Error getting union enrichment summary: {e}")
            # Return the result with minimal data even on error
            return result

    def get_enrichment_summary(self, minutes: int = 10) -> Dict[str, Any]:
        """Summarize enrichment inputs and recent activity to help users verify computation inputs.

        Uses union schema implementation.
        """
        return self.get_enrichment_summary_union(minutes)

    def _calculate_processing_metrics(self, enriched_df, minutes: int) -> Dict[str, Any]:
        """Calculate detailed processing metrics for the enrichment process."""
        metrics = {
            "records_processed": 0,
            "records_failed": 0,
            "processing_duration_seconds": None,
            "records_per_second": None,
            "error_rate_percent": None,
            "last_processing_time": None
        }
        
        try:
            # Cache the DataFrame to avoid multiple scans
            enriched_df.cache()
            
            # Combine aggregations to minimize scans
            agg_result = enriched_df.agg(
                F.count("*").alias("total_records"),
                F.sum(
                    F.when(
                        F.col("normalized_data").isNull() | (F.size(F.col("normalized_data")) == 0), 1
                    ).otherwise(0)
                ).alias("failed_records"),
                F.min("ingest_ts").alias("earliest_time"),
                F.max("ingest_ts").alias("latest_time")
            ).collect()[0]
            
            total_records = agg_result["total_records"]
            failed_records = agg_result["failed_records"]
            metrics["records_processed"] = total_records
            metrics["records_failed"] = failed_records
            
            # Calculate error rate
            if total_records > 0:
                metrics["error_rate_percent"] = round((failed_records / total_records) * 100, 2)
            
            # Get time range for processing duration calculation
            if total_records > 0 and agg_result["earliest_time"] and agg_result["latest_time"]:
                earliest = agg_result["earliest_time"]
                latest = agg_result["latest_time"]
                
                # Calculate duration in seconds
                duration_seconds = (latest - earliest).total_seconds()
                metrics["processing_duration_seconds"] = round(duration_seconds, 2)
                
                # Calculate processing rate
                if duration_seconds > 0:
                    metrics["records_per_second"] = round(total_records / duration_seconds, 2)
                
                # Format last processing time
                metrics["last_processing_time"] = latest.isoformat()
            
            # Unpersist the DataFrame after use
            enriched_df.unpersist()
                    
        except Exception as e:
            logger.warning(f"Error calculating processing metrics: {e}")
            
        return metrics

    def _get_streaming_metrics(self) -> Dict[str, Any]:
        """Get metrics from active streaming queries."""
        metrics = {
            "query_active": False,
            "query_name": None,
            "last_batch_id": None,
            "input_rows_per_second": None,
            "processing_time_ms": None,
            "batch_duration_ms": None,
            "last_batch_timestamp": None
        }
        
        try:
            # Try to find the enrichment stream query
            spark = self.session_manager.spark
            active_queries = spark.streams.active
            
            for query in active_queries:
                try:
                    if query.name == "enrich_stream":
                        metrics["query_active"] = True
                        metrics["query_name"] = query.name
                        
                        # Get last progress if available
                        if hasattr(query, 'lastProgress') and query.lastProgress:
                            progress = query.lastProgress
                            metrics["last_batch_id"] = progress.get("batchId")
                            
                            # Input metrics
                            input_stats = progress.get("inputRowsPerSecond")
                            if input_stats is not None:
                                metrics["input_rows_per_second"] = round(input_stats, 2)
                            
                            # Processing time metrics
                            processing_time = progress.get("durationMs", {}).get("triggerExecution")
                            if processing_time is not None:
                                metrics["processing_time_ms"] = processing_time
                                
                            batch_duration = progress.get("durationMs", {}).get("getBatch")
                            if batch_duration is not None:
                                metrics["batch_duration_ms"] = batch_duration
                            
                            # Timestamp
                            timestamp = progress.get("timestamp")
                            if timestamp:
                                metrics["last_batch_timestamp"] = timestamp
                        break
                except Exception as e:
                    logger.debug(f"Error getting progress for query {query.name if hasattr(query, 'name') else 'unknown'}: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Error getting streaming metrics: {e}")
            
        return metrics

    def _get_normalization_stats(self, minutes: int) -> Dict[str, Any]:
        """Get statistics about normalization rule usage."""
        stats = {
            "total_rules_applied": 0,
            "active_rules_count": 0,
            "field_mappings_applied": 0,
            "normalization_success_rate": None
        }
        
        try:
            from sqlalchemy.orm import sessionmaker
            from src.database.database import engine
            from src.database.models import NormalizationRule
            SessionLocal = sessionmaker(bind=engine)
            db = SessionLocal()
            
            try:
                # Count active rules
                active_rules = db.query(NormalizationRule).filter(
                    NormalizationRule.enabled == True
                ).all()
                
                stats["active_rules_count"] = len(active_rules)
                
                # Sum up applied counts and calculate averages
                total_applied = sum(getattr(rule, 'applied_count', 0) for rule in active_rules)
                stats["total_rules_applied"] = total_applied
                
                # Count unique field mappings
                unique_mappings = len(set(rule.canonical_key for rule in active_rules))
                stats["field_mappings_applied"] = unique_mappings
                
                # Calculate rough success rate based on recent usage
                recent_usage = sum(
                    getattr(rule, 'applied_count', 0)
                    for rule in active_rules
                    if getattr(rule, "last_applied_at", None)
                )
                
                if total_applied > 0:
                    stats["normalization_success_rate"] = round((recent_usage / total_applied) * 100, 2)
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.warning(f"Error getting normalization stats: {e}")
            
        return stats

    def _get_data_quality_metrics(self, enriched_df) -> Dict[str, Any]:
        """Calculate data quality metrics from enriched DataFrame."""
        quality = {
            "schema_compliance_rate": None,
            "unique_ingestion_ids": 0,
            "ingestion_id_breakdown": {},
            "fields_with_data": [],
            "fields_normalized": []
        }
        
        try:
            # Get ingestion ID breakdown - use sampling for large datasets to avoid blocking
            if "ingestion_id" in enriched_df.columns:
                # Check if dataset is small enough for full count
                if enriched_df.rdd.isEmpty():
                    quality["ingestion_id_breakdown"] = []
                    quality["unique_ingestion_ids"] = 0
                else:
                    try:
                        # Sample data first to check if it's reasonable to count
                        sample_df = enriched_df.sample(fraction=0.1, seed=42)
                        sample_breakdown = sample_df.groupBy("ingestion_id").count().collect()
                        
                        if len(sample_breakdown) < 20:  # Small number of ingestion IDs
                            # Safe to get full breakdown
                            ingestion_breakdown = enriched_df.groupBy("ingestion_id").count().collect()
                            quality["ingestion_id_breakdown"] = [
                                {"ingestion_id": row["ingestion_id"], "count": row["count"]}
                                for row in ingestion_breakdown
                            ]
                            quality["unique_ingestion_ids"] = len(ingestion_breakdown)
                        else:
                            # Too many ingestion IDs, use sample data
                            quality["ingestion_id_breakdown"] = [
                                {"ingestion_id": row["ingestion_id"], "count": row["count"] * 10}  # Rough estimate
                                for row in sample_breakdown[:10]  # Limit to top 10
                            ]
                            quality["unique_ingestion_ids"] = len(sample_breakdown)
                            logger.debug("Using sampled ingestion ID breakdown to avoid blocking")
                    except Exception as breakdown_error:
                        logger.debug("Could not get ingestion breakdown: %s", breakdown_error)
                        quality["ingestion_id_breakdown"] = []
                        quality["unique_ingestion_ids"] = 0
            # Analyze sensor_data and normalized_data fields (fields with actual data)
            fields_with_data = set()
            normalized_fields = set()
            if "sensor_data" in enriched_df.columns and "normalized_data" in enriched_df.columns:
                # Collect both columns together to minimize .collect() calls
                samples = (
                    enriched_df.select("sensor_data", "normalized_data")
                    .limit(10)
                    .collect()
                )
                for record in samples:
                    if record["sensor_data"]:
                        fields_with_data.update(record["sensor_data"].keys())
                    if record["normalized_data"]:
                        normalized_fields.update(record["normalized_data"].keys())
                quality["fields_with_data"] = sorted(list(fields_with_data))
                quality["fields_normalized"] = sorted(list(normalized_fields))
            else:
                if "sensor_data" in enriched_df.columns:
                    sample_records = enriched_df.select("sensor_data").limit(10).collect()
                    for record in sample_records:
                        if record["sensor_data"]:
                            fields_with_data.update(record["sensor_data"].keys())
                    quality["fields_with_data"] = sorted(list(fields_with_data))
                if "normalized_data" in enriched_df.columns:
                    sample_normalized = enriched_df.select("normalized_data").limit(10).collect()
                    for record in sample_normalized:
                        if record["normalized_data"]:
                            normalized_fields.update(record["normalized_data"].keys())
                    quality["fields_normalized"] = sorted(list(normalized_fields))
                # Calculate schema compliance rate
                normalized_fields_count = len(normalized_fields)
                total_fields = len(fields_with_data) if fields_with_data else 0
                if total_fields > 0:
                    quality["schema_compliance_rate"] = round((normalized_fields_count / total_fields) * 100, 2)
                else:
                    quality["schema_compliance_rate"] = None
                
        except Exception as e:
            logger.warning(f"Error calculating data quality metrics: {e}")
            
        return quality

