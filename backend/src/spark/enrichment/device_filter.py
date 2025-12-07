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
            logger.debug("Device filter: registered ingestion_ids: %s", raw_allowed)
            
            # Check for wildcard registration (None ingestion_id means accept all)
            has_wildcard: bool = any(iid is None for iid in raw_allowed)
            
            # Normalize allowed ingestion IDs
            normalized_allowed: Set[str] = {
                str(iid).strip().lower()
                for iid in raw_allowed
                if iid is not None and str(iid).strip().lower() not in ("", "unknown")
            }
            
            logger.debug("Device filter: normalized allowed IDs: %s", normalized_allowed)
            logger.debug("Device filter: has wildcard registration: %s", has_wildcard)
            
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
        
        # Discovered ingestion IDs in the batch for logging
        ingestion_ids_in_batch = batch_df.select(F.lower(F.trim(F.col("ingestion_id")))).distinct().take(20)
        logger.debug("Device filter: ingestion_ids in batch: %s", [row[0] for row in ingestion_ids_in_batch])
        
        # Log devices that will be kept/filtered
        ids_in_batch_set = {row[0] for row in ingestion_ids_in_batch}
        ids_to_keep = ids_in_batch_set.intersection(allowed_ids)
        ids_to_filter = ids_in_batch_set.difference(allowed_ids)
        logger.debug("Device filter: keeping ingestion_ids: %s", ids_to_keep)
        logger.debug("Device filter: filtering out ingestion_ids: %s", ids_to_filter)
        
        # Apply filter for specific ingestion IDs
        filtered = batch_df.filter(
            F.lower(F.trim(F.col("ingestion_id"))).isin(list(allowed_ids))
        )
        
        return filtered

    
