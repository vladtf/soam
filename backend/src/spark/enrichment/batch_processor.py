"""
Batch processing logic for enrichment streams.
"""
import logging
import time
from typing import Set
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

            # Step 5: Write to Delta (SPARK ACTION - main write operation)
            step_start = time.perf_counter()
            self._write_to_delta(filtered_df)
            write_duration = time.perf_counter() - step_start
            BATCH_STEP_DURATION.labels(step="5_write_delta").set(write_duration)

            logger.info("Union enrichment: wrote data to enriched")
            
            # Record metrics for successful batch processing
            batch_time = time.time() - batch_start_time
            backend_metrics.record_spark_batch("enrichment", batch_time, success=True)

        except Exception as e:
            logger.error(f"Error in union enrichment foreachBatch: {e}")
            # Record failed batch
            batch_time = time.time() - batch_start_time
            backend_metrics.record_spark_batch("enrichment", batch_time, success=False)

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
