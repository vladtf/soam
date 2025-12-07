"""
Prometheus metrics for SOAM ingestor service.
Provides throughput, latency, and operational metrics with proper labeling for auto-scaling.
"""
import os
import logging
from prometheus_client import Counter, Histogram, Gauge, Info

logger = logging.getLogger(__name__)

# Get pod name from environment (set by Kubernetes)
POD_NAME = os.getenv("POD_NAME", os.getenv("HOSTNAME", "unknown"))
NAMESPACE = os.getenv("POD_NAMESPACE", "default")

# ============================================================================
# THROUGHPUT METRICS - For measuring data ingestion rate across scaled pods
# ============================================================================

# Messages received counter with source type label
MESSAGES_RECEIVED = Counter(
    "ingestor_messages_received_total",
    "Total number of messages received by the ingestor",
    ["pod", "source_type", "ingestion_id"]
)

# Messages processed (successfully stored to MinIO)
MESSAGES_PROCESSED = Counter(
    "ingestor_messages_processed_total",
    "Total number of messages successfully processed and stored",
    ["pod", "source_type", "ingestion_id"]
)

# Messages failed counter
MESSAGES_FAILED = Counter(
    "ingestor_messages_failed_total",
    "Total number of messages that failed processing",
    ["pod", "source_type", "ingestion_id", "error_type"]
)

# Bytes received counter
BYTES_RECEIVED = Counter(
    "ingestor_bytes_received_total",
    "Total bytes of data received",
    ["pod", "source_type"]
)

# Bytes written to MinIO
BYTES_WRITTEN = Counter(
    "ingestor_bytes_written_total",
    "Total bytes written to MinIO storage",
    ["pod", "layer"]  # layer: bronze
)

# ============================================================================
# LATENCY METRICS - For end-to-end pipeline latency tracking
# ============================================================================

# Ingestion timestamp - used for calculating end-to-end latency
# This records when data was received by ingestor (vs when sensor generated it)
INGESTION_TIMESTAMP_DELAY = Histogram(
    "ingestor_timestamp_delay_seconds",
    "Delay between sensor timestamp and ingestion timestamp",
    ["pod", "source_type"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 300.0)
)

# ============================================================================
# OPERATIONAL METRICS - For monitoring ingestor health
# ============================================================================

# Active data sources gauge
ACTIVE_DATA_SOURCES = Gauge(
    "ingestor_active_data_sources",
    "Number of currently active data sources",
    ["pod", "source_type"]
)

# Buffer size gauge (messages in memory awaiting flush)
BUFFER_SIZE = Gauge(
    "ingestor_buffer_size_messages",
    "Number of messages in buffer awaiting flush",
    ["pod", "ingestion_id"]
)

# Buffer bytes gauge
BUFFER_BYTES = Gauge(
    "ingestor_buffer_size_bytes",
    "Size of buffer in bytes",
    ["pod", "ingestion_id"]
)

# Files written counter
FILES_WRITTEN = Counter(
    "ingestor_files_written_total",
    "Total number of parquet files written to MinIO",
    ["pod", "layer"]
)

# Ingestor info metric
INGESTOR_INFO = Info(
    "ingestor",
    "Information about the ingestor instance"
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def init_metrics():
    """Initialize metrics with pod information."""
    INGESTOR_INFO.info({
        "pod_name": POD_NAME,
        "namespace": NAMESPACE,
        "version": "1.0.0"
    })
    logger.info(f"📊 Metrics initialized for pod: {POD_NAME}")


def record_message_received(source_type: str, ingestion_id: str, size_bytes: int):
    """Record a received message."""
    MESSAGES_RECEIVED.labels(pod=POD_NAME, source_type=source_type, ingestion_id=ingestion_id).inc()
    BYTES_RECEIVED.labels(pod=POD_NAME, source_type=source_type).inc(size_bytes)


def record_message_processed(source_type: str, ingestion_id: str):
    """Record a successfully processed message."""
    MESSAGES_PROCESSED.labels(pod=POD_NAME, source_type=source_type, ingestion_id=ingestion_id).inc()


def record_message_failed(source_type: str, ingestion_id: str, error_type: str):
    """Record a failed message."""
    MESSAGES_FAILED.labels(
        pod=POD_NAME, 
        source_type=source_type, 
        ingestion_id=ingestion_id, 
        error_type=error_type
    ).inc()


def record_timestamp_delay(source_type: str, delay_seconds: float):
    """Record delay between sensor timestamp and ingestion time."""
    if delay_seconds >= 0:  # Only record positive delays (avoid clock skew issues)
        INGESTION_TIMESTAMP_DELAY.labels(pod=POD_NAME, source_type=source_type).observe(delay_seconds)


def record_minio_flush(bytes_written: int, num_files: int = 1):
    """Record a MinIO flush operation."""
    BYTES_WRITTEN.labels(pod=POD_NAME, layer="bronze").inc(bytes_written)
    FILES_WRITTEN.labels(pod=POD_NAME, layer="bronze").inc(num_files)


def update_buffer_size(ingestion_id: str, message_count: int, byte_count: int):
    """Update buffer size gauges."""
    BUFFER_SIZE.labels(pod=POD_NAME, ingestion_id=ingestion_id).set(message_count)
    BUFFER_BYTES.labels(pod=POD_NAME, ingestion_id=ingestion_id).set(byte_count)


def update_active_sources(source_type: str, count: int):
    """Update active data sources gauge."""
    ACTIVE_DATA_SOURCES.labels(pod=POD_NAME, source_type=source_type).set(count)
