"""
Dependency injection for the SOAM ingestor FastAPI application.
"""
import os
import logging
from fastapi import Depends
from typing import Annotated
from collections import deque
from prometheus_client import Counter, Histogram

from src.config import ConnectionConfig, MINIO_BUCKET
from src.storage.minio_client import MinioClient
from src.mqtt_client import MQTTClientHandler
from src.metadata.service import MetadataService

logger = logging.getLogger(__name__)

# Initialize metrics once at module level to avoid duplicate registration
MESSAGES_RECEIVED = Counter(
    "mqtt_messages_received_total",
    "Total number of MQTT messages received"
)
MESSAGES_PROCESSED = Counter(
    "mqtt_messages_processed_total",
    "Total number of MQTT messages successfully processed"
)
PROCESSING_LATENCY = Histogram(
    "mqtt_message_processing_latency_seconds",
    "Latency for processing MQTT messages"
)


class IngestorConfig:
    """Ingestor configuration."""

    def __init__(self):
        # MQTT configuration
        self.mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        # Subscribe to all simulator topics by default
        # e.g. smartcity/sensors/temperature, /traffic, /air_quality, /smart_bin
        # Users can override via MQTT_TOPIC env var (supports comma-separated list)
        self.mqtt_topic = os.getenv("MQTT_TOPIC", "smartcity/sensors/#")

        # MinIO configuration
        self.minio_endpoint = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
        self.minio_access_key = os.getenv("MINIO_ACCESS_KEY", "minio")
        self.minio_secret_key = os.getenv("MINIO_SECRET_KEY", "minio123")
        self.minio_bucket = os.getenv("MINIO_BUCKET", "lake")


class IngestorState:
    """Application state management."""

    def __init__(self, config: IngestorConfig):
        # Partitioned buffers per ingestion_id
        self.buffer_max_rows = int(os.getenv("BUFFER_MAX_ROWS", "100"))
        # Map of ingestion_id -> deque
        self.data_buffers = {}
        self.connection_configs = []
        self.active_connection = None
        self.mqtt_handler = None

        # Initialize default connection
        default_config = ConnectionConfig(
            id=1,
            broker=config.mqtt_broker,
            port=config.mqtt_port,
            topic=config.mqtt_topic,
        )
        self.connection_configs.append(default_config)
        self.active_connection = default_config

        # Reference the module-level metrics (no re-initialization)
        self.messages_received = MESSAGES_RECEIVED
        self.messages_processed = MESSAGES_PROCESSED
        self.processing_latency = PROCESSING_LATENCY

    def get_partition_buffer(self, ingestion_id: str) -> deque:
        if ingestion_id not in self.data_buffers:
            self.data_buffers[ingestion_id] = deque(maxlen=self.buffer_max_rows)
        buf = self.data_buffers[ingestion_id]
        # Ensure buffer respects current max rows (if changed)
        if buf.maxlen != self.buffer_max_rows:
            new_buf = deque(buf, maxlen=self.buffer_max_rows)
            self.data_buffers[ingestion_id] = new_buf
            buf = new_buf
        return buf

    def clear_all_buffers(self) -> None:
        for k in list(self.data_buffers.keys()):
            self.data_buffers[k].clear()

    def set_buffer_max_rows(self, max_rows: int) -> None:
        self.buffer_max_rows = max(1, int(max_rows))
        # Rebuild all buffers to respect new maxlen
        for key, buf in list(self.data_buffers.items()):
            if buf.maxlen != self.buffer_max_rows:
                self.data_buffers[key] = deque(buf, maxlen=self.buffer_max_rows)

    def all_data_flat(self, limit_per_partition: int | None = None):
        out = []
        for key, buf in self.data_buffers.items():
            if limit_per_partition is None:
                out.extend(list(buf))
            else:
                # take the most recent items from right side
                out.extend(list(buf)[-limit_per_partition:])
        return out


# Global singleton instances
_config_instance = None
_minio_client_instance = None
_ingestor_state_instance = None
_metadata_service_instance = None


def get_config() -> IngestorConfig:
    """Get ingestor configuration (singleton)."""
    global _config_instance
    if _config_instance is None:
        _config_instance = IngestorConfig()
    return _config_instance


def get_minio_client(config: Annotated[IngestorConfig, Depends(get_config)]) -> MinioClient:
    """Get MinioClient instance (singleton)."""
    global _minio_client_instance
    if _minio_client_instance is None:
        _minio_client_instance = MinioClient(
            bucket=config.minio_bucket,
            endpoint=config.minio_endpoint,
            access_key=config.minio_access_key,
            secret_key=config.minio_secret_key
        )
    return _minio_client_instance


def get_ingestor_state(config: Annotated[IngestorConfig, Depends(get_config)]) -> IngestorState:
    """Get IngestorState instance (singleton)."""
    global _ingestor_state_instance
    if _ingestor_state_instance is None:
        _ingestor_state_instance = IngestorState(config)
    return _ingestor_state_instance


def get_metadata_service() -> MetadataService:
    """Get MetadataService instance (singleton)."""
    global _metadata_service_instance
    if _metadata_service_instance is None:
        _metadata_service_instance = MetadataService()
    return _metadata_service_instance


# Type aliases for dependency injection
ConfigDep = Annotated[IngestorConfig, Depends(get_config)]
MinioClientDep = Annotated[MinioClient, Depends(get_minio_client)]
IngestorStateDep = Annotated[IngestorState, Depends(get_ingestor_state)]
MetadataServiceDep = Annotated[MetadataService, Depends(get_metadata_service)]
