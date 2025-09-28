"""
Device registration filtering for enrichment streams.
"""
import logging
from typing import List, Set, Tuple
from sqlalchemy.orm import sessionmaker
from src.database.database import engine
from src.database.models import Device

logger = logging.getLogger(__name__)


class DeviceFilter:
    """Handles device registration filtering for enrichment processing."""

    def __init__(self) -> None:
        """Initialize the device filter."""
        self.SessionLocal = sessionmaker(bind=engine)

    def get_allowed_ingestion_ids(self) -> Tuple[Set[str], bool]:
        """Get allowed ingestion IDs and wildcard status from registered devices.
        
        Returns:
            Tuple of (allowed_ingestion_ids, has_wildcard)
            - allowed_ingestion_ids: Set of normalized ingestion IDs
            - has_wildcard: True if wildcard registration exists (None ingestion_id)
        """
        session = self.SessionLocal()
        try:
            # Get allowed ingestion IDs
            rows: List = session.query(Device.ingestion_id).filter(Device.enabled == True).all()
            raw_allowed: List[str] = [r[0] for r in rows]
            logger.info("Device filter: registered ingestion_ids: %s", raw_allowed)
            
            # Check for wildcard registration (None ingestion_id means accept all)
            has_wildcard: bool = any(iid is None for iid in raw_allowed)
            
            # Normalize allowed ingestion IDs
            normalized_allowed: Set[str] = {
                str(iid).strip().lower()
                for iid in raw_allowed
                if iid is not None and str(iid).strip().lower() not in ("", "unknown")
            }
            
            logger.info("Device filter: normalized allowed IDs: %s", normalized_allowed)
            logger.info("Device filter: has wildcard registration: %s", has_wildcard)
            
            return normalized_allowed, has_wildcard
            
        finally:
            session.close()

    def should_process_batch(self, allowed_ids: Set[str], has_wildcard: bool) -> bool:
        """Check if batch should be processed based on device registration.
        
        Args:
            allowed_ids: Set of allowed ingestion IDs
            has_wildcard: Whether wildcard registration exists
            
        Returns:
            True if batch should be processed, False otherwise
        """
        if not allowed_ids and not has_wildcard:
            logger.info("Device filter: no allowed ingestion IDs and no wildcard; skipping")
            return False
        return True

    def filter_dataframe(self, batch_df, allowed_ids: Set[str], has_wildcard: bool):
        """Filter dataframe based on device registration.
        
        Args:
            batch_df: Input DataFrame
            allowed_ids: Set of allowed ingestion IDs
            has_wildcard: Whether wildcard registration exists
            
        Returns:
            Filtered DataFrame
        """
        from pyspark.sql import functions as F
        
        # If wildcard registration exists, accept all data
        if has_wildcard:
            logger.info("Device filter: wildcard registration - accepting all data")
            return batch_df
        
        # Apply filter for specific ingestion IDs
        filtered = batch_df.filter(
            F.lower(F.trim(F.col("ingestion_id"))).isin(list(allowed_ids))
        )
        
        return filtered

    def log_filtering_stats(self, batch_df, filtered_df, allowed_ids: Set[str], has_wildcard: bool) -> None:
        """Log filtering statistics for debugging.
        
        Args:
            batch_df: Original DataFrame
            filtered_df: Filtered DataFrame
            allowed_ids: Set of allowed ingestion IDs
            has_wildcard: Whether wildcard registration exists
        """
        try:
            # Debug: Log sample of ingestion_ids in the batch (non-blocking)
            if "ingestion_id" in batch_df.columns:
                sample_ids: List[str] = [r[0] for r in batch_df.select("ingestion_id").distinct().limit(5).collect()]
                logger.info("Device filter: sample ingestion_ids in batch: %s", sample_ids)

            # PERFORMANCE FIX: Use RDD isEmpty() check instead of expensive count() operations
            # This prevents blocking the FastAPI event loop with long-running Spark jobs
            is_batch_empty = batch_df.rdd.isEmpty()
            is_filtered_empty = filtered_df.rdd.isEmpty()
            
            if is_batch_empty:
                logger.info("Device filter: batch is empty")
                return
                
            if is_filtered_empty:
                logger.info("Device filter: all rows filtered out - possible ingestion_id mismatch")
                return
            
            # Only use count() operations if we really need precise numbers AND batch is small
            # For large batches, use sampling to estimate instead of blocking operations
            try:
                # Quick check: if we can get count fast (small batch), use it
                # Otherwise, use estimation to avoid blocking
                sample_batch = batch_df.sample(fraction=0.01, seed=42)
                if not sample_batch.rdd.isEmpty():
                    sample_before = sample_batch.count()
                    estimated_before = min(sample_before * 100, 10000)  # Rough estimate, cap at 10k
                    
                    sample_filtered = filtered_df.sample(fraction=0.01, seed=42)
                    sample_after = sample_filtered.count() if not sample_filtered.rdd.isEmpty() else 0
                    estimated_after = min(sample_after * 100, 10000)  # Rough estimate, cap at 10k
                    
                    logger.info("Device filter: ~%d rows before filter, ~%d rows after filter", 
                              estimated_before, estimated_after)
                else:
                    logger.info("Device filter: processing small batch")
                    
            except Exception as count_error:
                logger.debug("Device filter: could not estimate counts: %s", count_error)
                logger.info("Device filter: batch processed (counts unavailable)")

            # Log warnings based on emptiness checks rather than precise counts
            if not has_wildcard and allowed_ids and not is_batch_empty and is_filtered_empty:
                logger.warning("Device filter: All rows filtered out - ingestion_id mismatch between registered devices and incoming data")
                
        except Exception as e:
            logger.warning("Device filter: could not log filtering stats: %s", e)
