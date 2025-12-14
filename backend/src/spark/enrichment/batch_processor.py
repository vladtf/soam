"""
Batch processing logic for enrichment streams.
"""
import logging
import time
from typing import Optional, Tuple, Set
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from prometheus_client import Gauge
from .device_filter import DeviceFilter
from .value_transformer import ValueTransformationProcessor
from src import metrics as backend_metrics


logger = logging.getLogger(__name__)

# Step duration gauges - show last observed duration for each step
BATCH_STEP_DURATION = Gauge(
    "batch_processor_step_duration_seconds",
    "Duration of each step within process_batch (last observed)",
    ["step"]
)


class BatchProcessor:
    """Handles batch processing for enrichment streams."""

    def __init__(self, enriched_path: str) -> None:
        """Initialize the batch processor.
        
        Args:
            enriched_path: Path to enriched data storage
        """
        self.enriched_path: str = enriched_path
        self.device_filter: DeviceFilter = DeviceFilter()
        self.value_transformer: ValueTransformationProcessor = ValueTransformationProcessor()

    def log_batch_sample(self, batch_df: DataFrame, stage: str = "raw") -> None:
        """Log sample batch data for debugging (non-blocking version).
        
        Args:
            batch_df: Input DataFrame  
            stage: Processing stage ("raw" or "processed")
        """
        if batch_df.rdd.isEmpty():
            logger.debug(f"=== {stage.upper()} BATCH SAMPLE: EMPTY ===")
            return
            
        try:
            logger.debug(f"=== {stage.upper()} BATCH SAMPLE ===")
            
            # Use take() instead of collect() to limit memory usage and blocking time
            sample_rows = batch_df.take(2)  # Non-blocking alternative to limit(2).collect()
            
            for i, row in enumerate(sample_rows):
                row_dict = row.asDict()
                sample_num = i + 1
                
                # Common info for both raw and processed stages
                ingestion_id = row_dict.get("ingestion_id", "unknown")
                field_count = len(row_dict)
                non_null_count = len([v for v in row_dict.values() if v is not None])
                
                logger.debug(f"Sample {sample_num}: ingestion_id={ingestion_id}, fields={field_count}, non-null={non_null_count}")
                
                # Stage-specific logging
                if stage == "processed" and "normalized_data" in row_dict and "sensor_data" in row_dict:
                    # Log normalized and sensor data for processed stage
                    normalized_data = row_dict["normalized_data"]
                    sensor_data = row_dict["sensor_data"]
                    
                    if normalized_data:
                        norm_fields = [f"{k}={v}" for k, v in normalized_data.items() if v is not None][:5]  # Limit to first 5
                        logger.debug(f"Sample {sample_num}: normalized fields: {norm_fields}")
                    
                    if sensor_data:
                        sensor_keys = list(sensor_data.keys())[:5]  # Limit to first 5 keys
                        logger.debug(f"Sample {sample_num}: sensor_data keys: {sensor_keys}")
                else:
                    # For raw stage, just show a few key fields
                    key_fields = {k: v for k, v in row_dict.items() if k in ["timestamp", "ingestion_id"] or not k.startswith("_")}
                    if len(key_fields) > 5:
                        # Show only first 5 non-internal fields
                        key_fields = dict(list(key_fields.items())[:5])
                    logger.debug(f"Sample {sample_num}: key fields: {key_fields}")
            
            logger.debug(f"=== END {stage.upper()} BATCH SAMPLE ===")
                
        except Exception as e:
            logger.warning(f"Could not log {stage} batch sample: {e}")

    def _calculate_end_to_end_latency(self, df: DataFrame) -> None:
        """Calculate and record latency metrics from sensor timestamp to enrichment.
        
        Measures latency from sensor timestamp (when sensor generated data) to 
        when it was processed by the enrichment pipeline.
        
        Args:
            df: DataFrame containing timestamp field
        """
        try:
            if "timestamp" not in df.columns:
                logger.debug("No timestamp column found for latency calculation")
                return
            
            # Get current time for latency calculation
            now = time.time()
            
            # Sample a few rows to calculate latency (avoid full scan)
            sample_rows = df.select("timestamp").take(10)
            
            if not sample_rows:
                return
            
            latencies = []
            
            for row in sample_rows:
                row_dict = row.asDict()
                ts = row_dict.get("timestamp")
                latency = self._parse_timestamp_to_latency(ts, now)
                if latency is not None:
                    latencies.append(latency)
            
            # Record sensor-to-enrichment latency metrics
            for latency in latencies:
                backend_metrics.record_sensor_to_enrichment_latency(latency)
                
            # Log summary
            if latencies:
                avg_latency = sum(latencies) / len(latencies)
                logger.info(f"📊 Sensor-to-enrichment latency: avg={avg_latency:.2f}s (sampled {len(latencies)} records)")
                
        except Exception as e:
            logger.debug(f"Could not calculate latency metrics: {e}")

    def _parse_timestamp_to_latency(self, ts, now: float) -> Optional[float]:
        """Parse a timestamp and calculate latency from it to now.
        
        Args:
            ts: Timestamp value (string, datetime, or numeric)
            now: Current time as epoch seconds
            
        Returns:
            Latency in seconds, or None if parsing fails or latency is unreasonable
        """
        if ts is None:
            return None
            
        try:
            if isinstance(ts, str):
                # Parse ISO format timestamp
                from datetime import datetime
                if "T" in ts:
                    # ISO format: 2024-12-07T10:30:00Z or 2024-12-07T10:30:00.000Z
                    ts_clean = ts.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(ts_clean)
                else:
                    dt = datetime.fromisoformat(ts)
                ts_epoch = dt.timestamp()
            elif hasattr(ts, 'timestamp'):
                # datetime object
                ts_epoch = ts.timestamp()
            elif isinstance(ts, (int, float)):
                # Already epoch timestamp
                ts_epoch = float(ts)
                # Check if it's milliseconds
                if ts_epoch > 1e12:
                    ts_epoch = ts_epoch / 1000
            else:
                return None
            
            latency = now - ts_epoch
            
            # Only return reasonable latencies (0 to 1 hour)
            if 0 <= latency <= 3600:
                return latency
            return None
                
        except Exception:
            return None

    def _estimate_record_count(self, df: DataFrame) -> int:
        """Estimate the number of records in a DataFrame without blocking.
        
        Uses sampling to avoid expensive full scans on large datasets.
        
        Args:
            df: DataFrame to estimate count for
            
        Returns:
            Estimated record count (0 if empty, actual count for small datasets,
            estimated count for large datasets)
        """
        if df.rdd.isEmpty():
            logger.info("Union enrichment: wrote 0 rows to enriched")
            return 0
            
        try:
            # Use a timeout-like approach by checking a small sample first
            sample_df = df.sample(fraction=0.01, seed=42)
            if sample_df.rdd.isEmpty():
                # Very small dataset, safe to count
                count = df.count()
                logger.info("Union enrichment: wrote %d rows to enriched", count)
                return count
            else:
                # Larger dataset, estimate or skip exact count to avoid blocking
                sample_count = sample_df.count()
                if sample_count > 0:
                    estimated_count = sample_count * 100
                    logger.info("Union enrichment: wrote ~%d rows to enriched", estimated_count)
                    return estimated_count
                else:
                    logger.info("Union enrichment: wrote data to enriched (large batch)")
                    return 100  # Minimum estimate for large batch
        except Exception as count_error:
            logger.debug("Could not estimate row count: %s", count_error)
            logger.info("Union enrichment: wrote data to enriched (count unavailable)")
            return 100  # Estimate for metrics

    def process_batch(self, batch_df: DataFrame, batch_id: int) -> None:
        """Process a batch of enrichment data.
        
        Optimized to minimize Spark actions (each action = expensive job with shuffle).
        
        Args:
            batch_df: Input DataFrame
            batch_id: Batch identifier
        """
        batch_start_time = time.time()
        records_processed = 0
        
        try:
            logger.info("Union enrichment batch started: batch_id=%s", batch_id)

            # Step 1: Get device filtering information (DB query)
            step_start = time.perf_counter()
            allowed_ids: Set[str]
            has_wildcard: bool
            allowed_ids, has_wildcard = self.device_filter.get_allowed_ingestion_ids()
            BATCH_STEP_DURATION.labels(step="1_get_allowed_ids").set(time.perf_counter() - step_start)
            
            # Step 2: Check if we should process this batch
            step_start = time.perf_counter()
            if not self.device_filter.should_process_batch(allowed_ids, has_wildcard):
                BATCH_STEP_DURATION.labels(step="2_should_process").set(time.perf_counter() - step_start)
                return
            BATCH_STEP_DURATION.labels(step="2_should_process").set(time.perf_counter() - step_start)

            # Step 3: Filter the dataframe (lazy - builds execution plan)
            step_start = time.perf_counter()
            filtered_df: DataFrame = self.device_filter.filter_dataframe(batch_df, allowed_ids, has_wildcard)
            BATCH_STEP_DURATION.labels(step="3_filter_dataframe").set(time.perf_counter() - step_start)

            # Step 4: Apply value transformations (lazy - builds execution plan)
            step_start = time.perf_counter()
            try:
                transformed_df: DataFrame = self.value_transformer.apply_transformations(filtered_df)
                logger.info("✅ Applied value transformations to batch")
                filtered_df = transformed_df
            except Exception as e:
                logger.error("❌ Error applying value transformations: %s", e)
                logger.warning("⚠️ Continuing with original data due to transformation error")
            BATCH_STEP_DURATION.labels(step="4_apply_transformations").set(time.perf_counter() - step_start)

            # Step 5: Take sample (SPARK ACTION - triggers execution)
            step_start = time.perf_counter()
            sample_rows = filtered_df.select("*").take(11)
            take_duration = time.perf_counter() - step_start
            BATCH_STEP_DURATION.labels(step="5_take_sample").set(take_duration)
            
            if not sample_rows:
                logger.info("Union enrichment: no rows after filtering - skipping write to avoid empty parquet files")
                return

            # Step 6: Log sample (no Spark action - reuse sample_rows)
            step_start = time.perf_counter()
            if logger.isEnabledFor(logging.DEBUG):
                self._log_sample_from_rows(sample_rows[:2], "processed")
            BATCH_STEP_DURATION.labels(step="6_log_sample").set(time.perf_counter() - step_start)

            # Step 7: Write to Delta (SPARK ACTION - main write operation)
            step_start = time.perf_counter()
            self._write_to_delta(filtered_df)
            write_duration = time.perf_counter() - step_start
            BATCH_STEP_DURATION.labels(step="7_write_delta").set(write_duration)

            # Step 8: Calculate latency (no Spark action - reuse sample_rows)
            step_start = time.perf_counter()
            self._calculate_latency_from_rows(sample_rows[:10])
            BATCH_STEP_DURATION.labels(step="8_calculate_latency").set(time.perf_counter() - step_start)

            # Estimate record count based on write success (no additional count/isEmpty)
            # We know it's not empty since sample_rows had data
            records_processed = len(sample_rows) * 10  # Rough estimate
            logger.info("Union enrichment: wrote ~%d+ rows to enriched", records_processed)
            
            # Record metrics for successful batch processing
            batch_time = time.time() - batch_start_time
            backend_metrics.record_spark_batch("enrichment", batch_time, success=True)
            if records_processed > 0:
                backend_metrics.record_enrichment_records("all", records_processed)

        except Exception as e:
            logger.error(f"Error in union enrichment foreachBatch: {e}")
            # Record failed batch
            batch_time = time.time() - batch_start_time
            backend_metrics.record_spark_batch("enrichment", batch_time, success=False)

    def _log_sample_from_rows(self, rows: list, stage: str) -> None:
        """Log sample data from pre-fetched rows (no Spark action).
        
        Args:
            rows: Pre-fetched Row objects
            stage: Processing stage name
        """
        if not rows:
            logger.debug(f"=== {stage.upper()} BATCH SAMPLE: EMPTY ===")
            return
            
        logger.debug(f"=== {stage.upper()} BATCH SAMPLE ===")
        for i, row in enumerate(rows[:2]):
            row_dict = row.asDict()
            ingestion_id = row_dict.get("ingestion_id", "unknown")
            field_count = len(row_dict)
            logger.debug(f"Sample {i+1}: ingestion_id={ingestion_id}, fields={field_count}")
        logger.debug(f"=== END {stage.upper()} BATCH SAMPLE ===")

    def _calculate_latency_from_rows(self, rows: list) -> None:
        """Calculate latency metrics from pre-fetched rows (no Spark action).
        
        Args:
            rows: Pre-fetched Row objects with timestamp field
        """
        if not rows:
            return
            
        now = time.time()
        latencies = []
        
        for row in rows:
            row_dict = row.asDict()
            ts = row_dict.get("timestamp")
            latency = self._parse_timestamp_to_latency(ts, now)
            if latency is not None:
                latencies.append(latency)
        
        for latency in latencies:
            backend_metrics.record_sensor_to_enrichment_latency(latency)
            
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            logger.info(f"📊 Sensor-to-enrichment latency: avg={avg_latency:.2f}s (sampled {len(latencies)} records)")

    def _write_to_delta(self, filtered_df: DataFrame) -> None:
        """Write filtered dataframe to Delta storage.
        
        Args:
            filtered_df: Filtered DataFrame to write
        """
        # Add enrichment_timestamp to track when data was processed by Spark
        # This enables latency calculations: enrichment_timestamp - ingestion_timestamp
        enriched_df = filtered_df.withColumn(
            "enrichment_timestamp",
            F.current_timestamp()
        )
        
        (
            enriched_df.write
            .format("delta")
            .mode("append")
            .option("path", self.enriched_path)
            .option("mergeSchema", "true")
            .partitionBy("ingestion_id")  # Partition by ingestion_id
            .save()
        )
