"""
Batch processing logic for enrichment streams.
"""
import logging
from typing import Optional, Tuple, Set
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from .device_filter import DeviceFilter
from .value_transformer import ValueTransformationProcessor

logger = logging.getLogger(__name__)


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

    def process_batch(self, batch_df: DataFrame, batch_id: int) -> None:
        """Process a batch of enrichment data.
        
        Args:
            batch_df: Input DataFrame
            batch_id: Batch identifier
        """
        try:
            logger.info("Union enrichment batch started: batch_id=%s", batch_id)

            # Debug: Log sample raw data BEFORE any processing
            if logger.isEnabledFor(logging.DEBUG):
                self.log_batch_sample(batch_df, "raw")

            # Get device filtering information
            allowed_ids: Set[str]
            has_wildcard: bool
            allowed_ids, has_wildcard = self.device_filter.get_allowed_ingestion_ids()
            
            # Check if we should process this batch
            if not self.device_filter.should_process_batch(allowed_ids, has_wildcard):
                return

            # Filter the dataframe
            filtered_df: DataFrame = self.device_filter.filter_dataframe(batch_df, allowed_ids, has_wildcard)

            if filtered_df.rdd.isEmpty():
                logger.info("Union enrichment: no rows after filtering - skipping write to avoid empty parquet files")
                return

            # Apply value transformations
            try:
                transformed_df: DataFrame = self.value_transformer.apply_transformations(filtered_df)
                logger.info("✅ Applied value transformations to batch")
                
                # Check if transformations resulted in empty DataFrame
                if transformed_df.rdd.isEmpty():
                    logger.info("Union enrichment: no rows after value transformations - skipping write")
                    return
                    
                # Use transformed DataFrame for further processing
                filtered_df = transformed_df
                
            except Exception as e:
                logger.error("❌ Error applying value transformations: %s", e)
                # Continue with original filtered_df on transformation errors
                logger.warning("⚠️ Continuing with original data due to transformation error")

            # Log normalized field information for debugging (use sampling to avoid blocking)
            if logger.isEnabledFor(logging.DEBUG):
                # Use approximate count for better performance
                try:
                    # Sample a small fraction to estimate count without full scan
                    sample_count = filtered_df.sample(fraction=0.01).count()
                    estimated_total = max(sample_count * 100, sample_count) if sample_count > 0 else 0
                    logger.debug(f"Estimated rows after filtering: ~{estimated_total}")
                    
                    # Only log sample if we have data
                    if estimated_total > 0:
                        self.log_batch_sample(filtered_df, "processed")
                except Exception as e:
                    logger.debug(f"Could not estimate filtered count: {e}")

            # Write to Delta with partitioning by ingestion_id
            self._write_to_delta(filtered_df)

            # Log final count (this is after write, so it's necessary)
            try:
                # PERFORMANCE FIX: Use isEmpty() check instead of expensive count() for large datasets
                # Only use count() if we can get it quickly
                if filtered_df.rdd.isEmpty():
                    logger.info("Union enrichment: wrote 0 rows to enriched")
                else:
                    # Try to get count quickly, if it takes too long, just log that data was written
                    try:
                        # Use a timeout-like approach by checking a small sample first
                        sample_df = filtered_df.sample(fraction=0.01, seed=42)
                        if sample_df.rdd.isEmpty():
                            # Very small dataset, safe to count
                            kept: int = filtered_df.count()
                            logger.info("Union enrichment: wrote %d rows to enriched", kept)
                        else:
                            # Larger dataset, estimate or skip exact count to avoid blocking
                            sample_count = sample_df.count()
                            if sample_count > 0:
                                estimated_count = sample_count * 100
                                logger.info("Union enrichment: wrote ~%d rows to enriched", estimated_count)
                            else:
                                logger.info("Union enrichment: wrote data to enriched (large batch)")
                    except Exception as count_error:
                        logger.debug("Could not estimate row count: %s", count_error)
                        logger.info("Union enrichment: wrote data to enriched (count unavailable)")
            except Exception as e:
                logger.warning(f"Could not determine write status: {e}")
                logger.info("Union enrichment: write completed")

        except Exception as e:
            logger.error(f"Error in union enrichment foreachBatch: {e}")

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
