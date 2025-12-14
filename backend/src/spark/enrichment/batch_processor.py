"""
Batch processing logic for enrichment streams.
"""
import logging
import time
from typing import Set, Tuple
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from .device_filter import DeviceFilter
from .value_transformer import ValueTransformationProcessor
from src import metrics as backend_metrics
from src.utils.step_profiler import profile_step


logger = logging.getLogger(__name__)

MODULE = "batch_processor"


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

    def process_batch(self, batch_df: DataFrame, batch_id: int) -> None:
        """Process a batch of enrichment data.
        
        Optimized to minimize Spark actions (each action = expensive job with shuffle).
        
        Args:
            batch_df: Input DataFrame
            batch_id: Batch identifier
        """
        batch_start_time = time.time()
        
        try:
            logger.info("Union enrichment batch started: batch_id=%s", batch_id)

            # Step 1: Get device filtering information (DB query)
            allowed_ids, has_wildcard = self._get_allowed_ids()
            
            # Step 2: Check if we should process this batch
            if not self._should_process(allowed_ids, has_wildcard):
                return

            # Step 3: Filter the dataframe (lazy - builds execution plan)
            filtered_df = self._filter_dataframe(batch_df, allowed_ids, has_wildcard)

            # Step 4: Apply value transformations (lazy - builds execution plan)
            filtered_df = self._apply_transformations(filtered_df)

            # Step 5: Write to Delta (SPARK ACTION - main write operation)
            self._write_to_delta(filtered_df)

            logger.info("Union enrichment: wrote data to enriched")
            
            # Record metrics for successful batch processing
            batch_time = time.time() - batch_start_time
            backend_metrics.record_spark_batch("enrichment", batch_time, success=True)
            
            # Record batch processing time as sensor-to-enrichment latency estimate
            # This represents the time from batch trigger to write completion
            backend_metrics.record_sensor_to_enrichment_latency(batch_time)

        except Exception as e:
            logger.error(f"Error in union enrichment foreachBatch: {e}")
            # Record failed batch
            batch_time = time.time() - batch_start_time
            backend_metrics.record_spark_batch("enrichment", batch_time, success=False)

    @profile_step(MODULE, "1_get_allowed_ids")
    def _get_allowed_ids(self) -> Tuple[Set[str], bool]:
        """Get device filtering information from database."""
        return self.device_filter.get_allowed_ingestion_ids()

    @profile_step(MODULE, "2_should_process")
    def _should_process(self, allowed_ids: Set[str], has_wildcard: bool) -> bool:
        """Check if we should process this batch."""
        return self.device_filter.should_process_batch(allowed_ids, has_wildcard)

    @profile_step(MODULE, "3_filter_dataframe")
    def _filter_dataframe(self, batch_df: DataFrame, allowed_ids: Set[str], has_wildcard: bool) -> DataFrame:
        """Filter the dataframe based on allowed device IDs."""
        return self.device_filter.filter_dataframe(batch_df, allowed_ids, has_wildcard)

    @profile_step(MODULE, "4_apply_transformations")
    def _apply_transformations(self, filtered_df: DataFrame) -> DataFrame:
        """Apply value transformations to the dataframe."""
        try:
            transformed_df = self.value_transformer.apply_transformations(filtered_df)
            logger.info("✅ Applied value transformations to batch")
            return transformed_df
        except Exception as e:
            logger.error("❌ Error applying value transformations: %s", e)
            logger.warning("⚠️ Continuing with original data due to transformation error")
            return filtered_df

    @profile_step(MODULE, "5_write_delta")
    def _write_to_delta(self, filtered_df: DataFrame) -> None:
        """Write filtered dataframe to Delta storage.
        
        Args:
            filtered_df: Filtered DataFrame to write
        """
        # Add enrichment_timestamp to track when data was processed by Spark
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
            .partitionBy("ingestion_id")
            .save()
        )
