"""
Metadata extraction service for ingested data.
Extracts schema information, data statistics, and other metadata.
"""
import json
import logging
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import threading
import time
from queue import Queue, Empty
import re

logger = logging.getLogger(__name__)

UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)


@dataclass
class SchemaField:
    """Represents a field in the data schema."""
    name: str
    type: str
    nullable: bool = True
    sample_values: List[str] = None
    
    def __post_init__(self):
        if self.sample_values is None:
            self.sample_values = []


@dataclass
class DatasetMetadata:
    """Represents metadata for a dataset."""
    ingestion_id: str
    topic: str
    schema_fields: List[SchemaField]
    record_count: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    unique_sensor_ids: Set[str] = None
    data_size_bytes: int = 0
    
    def __post_init__(self):
        if self.unique_sensor_ids is None:
            self.unique_sensor_ids = set()


class MetadataExtractor:
    """Extracts and processes metadata from ingested data."""
    
    def __init__(self, batch_size: int = 100, batch_timeout: int = 30):
        """
        Initialize the metadata extractor.
        
        Args:
            batch_size: Number of records to batch before processing
            batch_timeout: Maximum time to wait before processing partial batch (seconds)
        """
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.metadata_queue = Queue()
        self.current_metadata = {}  # ingestion_id -> DatasetMetadata
        self.lock = threading.Lock()
        
        # Background processing
        self.processing_thread = None
        self.stop_event = threading.Event()
        
    def start_background_processing(self, storage_callback):
        """Start background thread for metadata processing."""
        if self.processing_thread and self.processing_thread.is_alive():
            logger.warning("Metadata processing thread already running")
            return
            
        self.stop_event.clear()
        self.processing_thread = threading.Thread(
            target=self._background_processor,
            args=(storage_callback,),
            daemon=True
        )
        self.processing_thread.start()
        logger.info("Started metadata background processing thread")
        
    def stop_background_processing(self):
        """Stop background processing thread."""
        if self.processing_thread:
            self.stop_event.set()
            self.processing_thread.join(timeout=5)
            logger.info("Stopped metadata background processing thread")
    
    def extract_metadata(self, payload: Dict[str, Any]) -> None:
        """
        Extract metadata from a single data payload.
        
        Args:
            payload: The data payload to analyze
        """
        try:
            ingestion_id = payload.get("ingestion_id", "unknown")
            topic = payload.get("topic", "unknown")
            
            # Add to processing queue
            metadata_item = {
                "ingestion_id": ingestion_id,
                "topic": topic,
                "payload": payload,
                "timestamp": datetime.now(timezone.utc)
            }
            
            self.metadata_queue.put(metadata_item)
            
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
    
    def _background_processor(self, storage_callback):
        """Background thread that processes metadata in batches."""
        batch = []
        last_batch_time = time.time()
        
        while not self.stop_event.is_set():
            try:
                # Try to get an item with timeout
                try:
                    item = self.metadata_queue.get(timeout=1)
                    batch.append(item)
                except Empty:
                    # Check if we should process partial batch due to timeout
                    if batch and (time.time() - last_batch_time) >= self.batch_timeout:
                        self._process_batch(batch, storage_callback)
                        batch = []
                        last_batch_time = time.time()
                    continue
                
                # Process batch if it's full
                if len(batch) >= self.batch_size:
                    self._process_batch(batch, storage_callback)
                    batch = []
                    last_batch_time = time.time()
                    
            except Exception as e:
                logger.error(f"Error in metadata background processor: {e}")
                
        # Process remaining items on shutdown
        if batch:
            self._process_batch(batch, storage_callback)
            
    def _process_batch(self, batch: List[Dict[str, Any]], storage_callback):
        """Process a batch of metadata items."""
        if not batch:
            return
            
        try:
            with self.lock:
                for item in batch:
                    self._update_metadata(item)
                
                # Prepare metadata for storage
                metadata_updates = []
                for metadata in self.current_metadata.values():
                    metadata_dict = self._serialize_metadata(metadata)
                    metadata_updates.append(metadata_dict)
                
            # Call storage callback outside of lock
            if metadata_updates and storage_callback:
                try:
                    storage_callback(metadata_updates)
                    logger.debug(f"Processed metadata batch of {len(batch)} items")
                except Exception as e:
                    logger.error(f"Error in storage callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error processing metadata batch: {e}")
    
    def _update_metadata(self, item: Dict[str, Any]) -> None:
        """Update metadata for a single item."""
        ingestion_id = item["ingestion_id"]
        topic = item["topic"]
        payload = item["payload"]
        timestamp = item["timestamp"]
        
        # Get or create metadata
        if ingestion_id not in self.current_metadata:
            self.current_metadata[ingestion_id] = DatasetMetadata(
                ingestion_id=ingestion_id,
                topic=topic,
                schema_fields=[],
                first_seen=timestamp
            )
        
        metadata = self.current_metadata[ingestion_id]
        
        # Update basic stats
        metadata.record_count += 1
        metadata.last_seen = timestamp
        metadata.data_size_bytes += len(json.dumps(payload))
        
        # Extract sensor ID if present
        sensor_id = payload.get("sensor_id") or payload.get("sensorId")
        if sensor_id:
            metadata.unique_sensor_ids.add(str(sensor_id))
        
        # Update schema
        self._update_schema(metadata, payload)
    
    def _update_schema(self, metadata: DatasetMetadata, payload: Dict[str, Any]) -> None:
        """Update schema information based on payload."""
        existing_fields = {field.name: field for field in metadata.schema_fields}
        
        for key, value in payload.items():
            field_type = self._infer_type(value)
            
            if key in existing_fields:
                field = existing_fields[key]
                # Update type if it's more specific or different
                if field.type != field_type and field_type != "null":
                    field.type = self._merge_types(field.type, field_type)
                
                # Add sample values (limit to 5)
                if len(field.sample_values) < 5 and str(value) not in field.sample_values:
                    field.sample_values.append(str(value))
            else:
                # New field
                new_field = SchemaField(
                    name=key,
                    type=field_type,
                    sample_values=[str(value)] if value is not None else []
                )
                metadata.schema_fields.append(new_field)
                existing_fields[key] = new_field
    
    def _infer_type(self, value: Any) -> str:
        """Infer the type of a value.
        
        Note: All numeric types (int/float) are reported as 'double' because
        the MinIO client converts all integers to float64 before writing to Parquet.
        This ensures schema consistency when Spark reads the data.
        """
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "boolean"
        elif isinstance(value, (int, float)):
            # All numerics are stored as double in Parquet for schema consistency
            return "double"
        elif isinstance(value, str):
            # All string values are stored as strings in Parquet, even if they look like timestamps.
            # We don't infer 'timestamp' type because ISO timestamp strings are stored as BINARY (string)
            # in Parquet, and Spark can't convert BINARY to timestamp.
            # UUID detection is kept for informational purposes only.
            if self._is_uuid(value):
                return "uuid"
            else:
                return "string"
        elif isinstance(value, (list, tuple)):
            return "array"
        elif isinstance(value, dict):
            return "object"
        else:
            return "unknown"
    
    def _is_timestamp(self, value: str) -> bool:
        """Check if string looks like a timestamp."""
        timestamp_patterns = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ"
        ]
        
        for pattern in timestamp_patterns:
            try:
                datetime.strptime(value, pattern)
                return True
            except ValueError:
                continue
        return False
    
    def _is_uuid(self, value: str) -> bool:
        """Check if string looks like a UUID."""
        return bool(UUID_PATTERN.match(value))
    
    def _merge_types(self, type1: str, type2: str) -> str:
        """Merge two types to find the most compatible common type."""
        if type1 == type2:
            return type1
        
        # Type promotion hierarchy
        type_hierarchy = {
            "null": 0,
            "boolean": 1,
            "integer": 2,
            "double": 3,
            "string": 4,
            "timestamp": 4,
            "uuid": 4,
            "array": 5,
            "object": 6,
            "unknown": 7
        }
        
        # Return the more general type
        level1 = type_hierarchy.get(type1, 7)
        level2 = type_hierarchy.get(type2, 7)
        
        if level1 >= level2:
            return type1
        else:
            return type2
    
    def _serialize_metadata(self, metadata: DatasetMetadata) -> Dict[str, Any]:
        """Serialize metadata to dictionary for storage."""
        return {
            "ingestion_id": metadata.ingestion_id,
            "topic": metadata.topic,
            "record_count": metadata.record_count,
            "first_seen": metadata.first_seen.isoformat() if metadata.first_seen else None,
            "last_seen": metadata.last_seen.isoformat() if metadata.last_seen else None,
            "unique_sensor_count": len(metadata.unique_sensor_ids),
            "unique_sensor_ids": list(metadata.unique_sensor_ids),
            "data_size_bytes": metadata.data_size_bytes,
            "schema_fields": [asdict(field) for field in metadata.schema_fields],
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
    
    def get_current_metadata(self) -> Dict[str, Any]:
        """Get current metadata state."""
        with self.lock:
            return {
                ingestion_id: self._serialize_metadata(metadata)
                for ingestion_id, metadata in self.current_metadata.items()
            }
