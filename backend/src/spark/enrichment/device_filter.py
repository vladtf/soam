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

    def __init__(self):
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
            rows = session.query(Device.ingestion_id).filter(Device.enabled == True).all()
            raw_allowed = [r[0] for r in rows]
            logger.info("Device filter: registered ingestion_ids: %s", raw_allowed)
            
            # Check for wildcard registration (None ingestion_id means accept all)
            has_wildcard = any(iid is None for iid in raw_allowed)
            
            # Normalize allowed ingestion IDs
            normalized_allowed = {
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

    def log_filtering_stats(self, batch_df, filtered_df, allowed_ids: Set[str], has_wildcard: bool):
        """Log filtering statistics for debugging.
        
        Args:
            batch_df: Original DataFrame
            filtered_df: Filtered DataFrame
            allowed_ids: Set of allowed ingestion IDs
            has_wildcard: Whether wildcard registration exists
        """
        # Debug: Log sample of ingestion_ids in the batch
        if "ingestion_id" in batch_df.columns:
            sample_ids = [r[0] for r in batch_df.select("ingestion_id").distinct().limit(5).collect()]
            logger.info("Device filter: sample ingestion_ids in batch: %s", sample_ids)

        # Additional debug: count before and after filtering
        total_before = batch_df.count()
        total_after = filtered_df.count()
        logger.info("Device filter: %d rows before filter, %d rows after filter", total_before, total_after)

        # If we expected filtering but nothing was filtered out, there might be a data mismatch
        if not has_wildcard and allowed_ids and total_before > 0 and total_after == total_before:
            logger.warning("Device filter: Expected filtering but no rows were filtered out - possible ingestion_id mismatch")
        elif not has_wildcard and allowed_ids and total_after == 0:
            logger.warning("Device filter: All rows filtered out - ingestion_id mismatch between registered devices and incoming data")
