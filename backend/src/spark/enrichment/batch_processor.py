"""
Batch processing logic for enrichment streams.
"""
import logging
from typing import Optional
from pyspark.sql import DataFrame
from .device_filter import DeviceFilter

logger = logging.getLogger(__name__)


class BatchProcessor:
    """Handles batch processing for enrichment streams."""

    def __init__(self, enriched_path: str):
        """Initialize the batch processor.
        
        Args:
            enriched_path: Path to enriched data storage
        """
        self.enriched_path = enriched_path
        self.device_filter = DeviceFilter()

    def log_raw_batch_sample(self, batch_df: DataFrame) -> None:
        """Log sample of raw batch data for debugging.
        
        Args:
            batch_df: Input DataFrame
        """
        if batch_df.rdd.isEmpty():
            return
            
        logger.info("=== RAW BATCH DATA SAMPLE ===")
        raw_sample = batch_df.limit(2).collect()
        for i, row in enumerate(raw_sample):
            row_dict = row.asDict()
            logger.info(f"Raw data sample {i+1}: {row_dict}")
            # Specifically check temperature field in raw data
            if 'temperature' in row_dict:
                logger.info(f"Raw data sample {i+1}: temperature = '{row_dict['temperature']}' (type: {type(row_dict['temperature'])})")
        logger.info("=== END RAW BATCH DATA SAMPLE ===")

    def log_normalized_data_sample(self, filtered_df: DataFrame) -> None:
        """Log sample of normalized data for debugging.
        
        Args:
            filtered_df: Filtered DataFrame
        """
        try:
            # Sample normalized data to show what fields and values are being processed
            sample_rows = filtered_df.select("ingestion_id", "normalized_data", "sensor_data").limit(3).collect()
            for i, row in enumerate(sample_rows):
                ingestion_id = row["ingestion_id"]
                normalized_data = row["normalized_data"]
                sensor_data = row["sensor_data"]

                logger.info("Enrichment sample %d: ingestion_id=%s", i+1, ingestion_id)

                # Log normalized fields and values
                if normalized_data:
                    # normalized_data is already a dict, not a Row object
                    norm_fields = [f"{k}={v}" for k, v in normalized_data.items() if v is not None]
                    logger.info("Enrichment sample %d: normalized fields: %s", i+1, norm_fields)
                else:
                    logger.info("Enrichment sample %d: no normalized data", i+1)

                # Log sensor data keys for context
                if sensor_data:
                    # sensor_data is already a dict, not a Row object
                    sensor_keys = list(sensor_data.keys())
                    # Also show some actual sensor data values
                    sensor_sample = {k: v for k, v in sensor_data.items() if k in ['sensorId', 'temperature', 'humidity', 'timestamp']}
                    logger.info("Enrichment sample %d: sensor_data keys: %s", i+1, sensor_keys)
                    logger.info("Enrichment sample %d: sensor_data sample: %s", i+1, sensor_sample)
                else:
                    logger.info("Enrichment sample %d: no sensor data", i+1)

        except Exception as e:
            logger.warning(f"Could not log sample normalized data: {e}")

    def process_batch(self, batch_df: DataFrame, batch_id: int) -> None:
        """Process a batch of enrichment data.
        
        Args:
            batch_df: Input DataFrame
            batch_id: Batch identifier
        """
        try:
            logger.info("Union enrichment batch started: batch_id=%s", batch_id)

            # Debug: Log sample raw data BEFORE any processing
            self.log_raw_batch_sample(batch_df)

            # Get device filtering information
            allowed_ids, has_wildcard = self.device_filter.get_allowed_ingestion_ids()
            
            # Check if we should process this batch
            if not self.device_filter.should_process_batch(allowed_ids, has_wildcard):
                return

            # Filter the dataframe
            filtered_df = self.device_filter.filter_dataframe(batch_df, allowed_ids, has_wildcard)

            if filtered_df.rdd.isEmpty():
                logger.info("Union enrichment: no rows after filtering - skipping write to avoid empty parquet files")
                return

            # Log filtering statistics
            self.device_filter.log_filtering_stats(batch_df, filtered_df, allowed_ids, has_wildcard)

            # Log normalized field information for debugging
            total_after = filtered_df.count()
            if total_after > 0:
                self.log_normalized_data_sample(filtered_df)

            # Write to Delta with partitioning by ingestion_id
            self._write_to_delta(filtered_df)

            kept = filtered_df.count()
            logger.info("Union enrichment: wrote %d rows to enriched", kept)

        except Exception as e:
            logger.error(f"Error in union enrichment foreachBatch: {e}")

    def _write_to_delta(self, filtered_df: DataFrame) -> None:
        """Write filtered dataframe to Delta storage.
        
        Args:
            filtered_df: Filtered DataFrame to write
        """
        (
            filtered_df.write
            .format("delta")
            .mode("append")
            .option("path", self.enriched_path)
            .option("mergeSchema", "true")
            .partitionBy("ingestion_id")  # Partition by ingestion_id
            .save()
        )
