"""
Metadata service that coordinates extraction and storage.
"""
import logging
from typing import Dict, Any, List, Optional

from .extractor import MetadataExtractor
from .storage import MetadataStorage

logger = logging.getLogger(__name__)


class MetadataService:
    """Coordinates metadata extraction and storage."""
    
    def __init__(self, db_path: str = "/data/metadata.db", batch_size: int = 100, batch_timeout: int = 30):
        """
        Initialize the metadata service.
        
        Args:
            db_path: Path to SQLite database
            batch_size: Number of records to batch before processing
            batch_timeout: Maximum time to wait before processing partial batch (seconds)
        """
        self.storage = MetadataStorage(db_path)
        self.extractor = MetadataExtractor(batch_size, batch_timeout)
        
        # Start background processing with storage callback
        self.extractor.start_background_processing(self.storage.store_metadata_batch)
        
        logger.info("Metadata service initialized and background processing started")
    
    def process_data(self, payload: Dict[str, Any]) -> None:
        """
        Process a data payload for metadata extraction.
        
        Args:
            payload: The data payload to analyze
        """
        self.extractor.extract_metadata(payload)
    
    def get_all_datasets(self) -> List[Dict[str, Any]]:
        """Get metadata for all datasets."""
        return self.storage.get_all_metadata()
    
    def get_dataset(self, ingestion_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific dataset."""
        return self.storage.get_metadata_by_ingestion_id(ingestion_id)
    
    def get_schema_evolution(self, ingestion_id: str) -> List[Dict[str, Any]]:
        """Get schema evolution for a specific dataset."""
        return self.storage.get_schema_evolution(ingestion_id)
    
    def get_topics_summary(self) -> List[Dict[str, Any]]:
        """Get summary statistics by topic."""
        return self.storage.get_topics_summary()
    
    def get_current_metadata(self) -> Dict[str, Any]:
        """Get current in-memory metadata state."""
        return self.extractor.get_current_metadata()
    
    def store_quality_metric(self, ingestion_id: str, metric_name: str, metric_value: float) -> None:
        """Store a data quality metric."""
        self.storage.store_data_quality_metric(ingestion_id, metric_name, metric_value)
    
    def get_quality_metrics(self, ingestion_id: str) -> List[Dict[str, Any]]:
        """Get data quality metrics for a dataset."""
        return self.storage.get_data_quality_metrics(ingestion_id)
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> int:
        """Clean up old data."""
        return self.storage.cleanup_old_data(days_to_keep)
    
    def shutdown(self):
        """Shutdown the metadata service."""
        logger.info("Shutting down metadata service...")
        self.extractor.stop_background_processing()
        logger.info("Metadata service shutdown complete")
