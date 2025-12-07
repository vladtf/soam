"""
Prometheus metrics for SOAM backend service.
Provides pipeline latency tracking from ingestion to gold layer.
"""
import os
import logging
from prometheus_client import Counter, Histogram, Gauge, Info, Summary

logger = logging.getLogger(__name__)

# Get pod name from environment (set by Kubernetes)
POD_NAME = os.getenv("POD_NAME", os.getenv("HOSTNAME", "unknown"))
NAMESPACE = os.getenv("POD_NAMESPACE", "default")

# ============================================================================
# PIPELINE LATENCY METRICS - End-to-end data flow tracking
# ============================================================================

# Sensor to Enrichment latency: from sensor timestamp to enrichment processing
# This measures the delay from when sensor generated data to when it was enriched
SENSOR_TO_ENRICHMENT_LATENCY = Histogram(
    "pipeline_sensor_to_enrichment_latency_seconds",
    "Latency from sensor timestamp to Spark enrichment (seconds)",
    ["pod"],
    buckets=(1, 2, 5, 10, 20, 30, 60, 120, 300, 600, 1800, 3600)
)

# Sensor to Gold latency: from sensor timestamp to gold layer (average temperature)
# This measures the full pipeline delay from sensor to final aggregated result
SENSOR_TO_GOLD_LATENCY = Histogram(
    "pipeline_sensor_to_gold_latency_seconds",
    "Latency from sensor timestamp to gold layer availability (seconds)",
    ["pod"],
    buckets=(1, 2, 5, 10, 20, 30, 60, 120, 300, 600, 1800, 3600)
)

# Latency by pipeline stage
STAGE_LATENCY = Histogram(
    "pipeline_stage_latency_seconds",
    "Latency for each pipeline stage",
    ["pod", "stage"],  # stages: bronze_write, enrichment, gold_write
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300)
)

# Spark batch processing latency
SPARK_BATCH_LATENCY = Histogram(
    "spark_batch_processing_latency_seconds",
    "Latency for Spark batch processing",
    ["pod", "stream_type"],  # stream_type: enrichment, aggregation
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300)
)

# ============================================================================
# THROUGHPUT METRICS - Backend processing rates
# ============================================================================

# Records processed through enrichment
ENRICHMENT_RECORDS_PROCESSED = Counter(
    "enrichment_records_processed_total",
    "Total records processed through enrichment pipeline",
    ["pod", "ingestion_id"]
)

# Records written to gold layer
GOLD_RECORDS_WRITTEN = Counter(
    "gold_records_written_total",
    "Total records written to gold layer",
    ["pod", "aggregation_type"]
)

# Spark batches processed
SPARK_BATCHES_PROCESSED = Counter(
    "spark_batches_processed_total",
    "Total Spark batches processed",
    ["pod", "stream_type", "status"]  # status: success, failed
)

# ============================================================================
# OPERATIONAL METRICS - Backend health
# ============================================================================

# Active Spark streams
ACTIVE_STREAMS = Gauge(
    "spark_active_streams",
    "Number of active Spark streaming queries",
    ["pod"]
)

# Spark stream status
STREAM_STATUS = Gauge(
    "spark_stream_status",
    "Status of Spark streams (1=running, 0=stopped)",
    ["pod", "stream_name"]
)

# Computation execution metrics
COMPUTATION_EXECUTIONS = Counter(
    "computation_executions_total",
    "Total computation executions",
    ["pod", "status"]  # status: success, failed
)

COMPUTATION_LATENCY = Histogram(
    "computation_execution_latency_seconds",
    "Latency for computation execution",
    ["pod"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60)
)

# Backend info metric
BACKEND_INFO = Info(
    "backend",
    "Information about the backend instance"
)

# ============================================================================
# DATA FRESHNESS METRICS - How recent is the data
# ============================================================================

# Latest data timestamp in each layer
LAYER_DATA_AGE = Gauge(
    "pipeline_layer_data_age_seconds",
    "Age of the most recent data in each layer",
    ["pod", "layer"]  # layer: bronze, enriched, gold
)

# Processing lag - difference between now and oldest unprocessed data
PROCESSING_LAG = Gauge(
    "pipeline_processing_lag_seconds",
    "Lag between current time and oldest unprocessed data",
    ["pod", "stage"]
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def init_metrics():
    """Initialize metrics with pod information."""
    BACKEND_INFO.info({
        "pod_name": POD_NAME,
        "namespace": NAMESPACE,
        "version": "1.0.0"
    })
    logger.info(f"📊 Backend metrics initialized for pod: {POD_NAME}")


def record_sensor_to_enrichment_latency(latency_seconds: float):
    """Record latency from sensor timestamp to enrichment processing."""
    SENSOR_TO_ENRICHMENT_LATENCY.labels(pod=POD_NAME).observe(latency_seconds)


def record_sensor_to_gold_latency(latency_seconds: float):
    """Record latency from sensor timestamp to gold layer availability."""
    SENSOR_TO_GOLD_LATENCY.labels(pod=POD_NAME).observe(latency_seconds)


def record_stage_latency(stage: str, latency_seconds: float):
    """Record latency for a specific pipeline stage."""
    STAGE_LATENCY.labels(pod=POD_NAME, stage=stage).observe(latency_seconds)


def record_spark_batch(stream_type: str, latency_seconds: float, success: bool = True):
    """Record a Spark batch processing event."""
    SPARK_BATCH_LATENCY.labels(pod=POD_NAME, stream_type=stream_type).observe(latency_seconds)
    status = "success" if success else "failed"
    SPARK_BATCHES_PROCESSED.labels(pod=POD_NAME, stream_type=stream_type, status=status).inc()


def record_enrichment_records(ingestion_id: str, count: int):
    """Record records processed through enrichment."""
    ENRICHMENT_RECORDS_PROCESSED.labels(pod=POD_NAME, ingestion_id=ingestion_id).inc(count)


def record_gold_records(aggregation_type: str, count: int):
    """Record records written to gold layer."""
    GOLD_RECORDS_WRITTEN.labels(pod=POD_NAME, aggregation_type=aggregation_type).inc(count)


def update_active_streams(count: int):
    """Update active Spark streams gauge."""
    ACTIVE_STREAMS.labels(pod=POD_NAME).set(count)


def update_stream_status(stream_name: str, is_running: bool):
    """Update stream status."""
    STREAM_STATUS.labels(pod=POD_NAME, stream_name=stream_name).set(1 if is_running else 0)


def record_computation(latency_seconds: float, success: bool = True):
    """Record a computation execution."""
    status = "success" if success else "failed"
    COMPUTATION_EXECUTIONS.labels(pod=POD_NAME, status=status).inc()
    COMPUTATION_LATENCY.labels(pod=POD_NAME).observe(latency_seconds)


def update_layer_data_age(layer: str, age_seconds: float):
    """Update the age of data in a layer."""
    LAYER_DATA_AGE.labels(pod=POD_NAME, layer=layer).set(age_seconds)


def update_processing_lag(stage: str, lag_seconds: float):
    """Update processing lag for a stage."""
    PROCESSING_LAG.labels(pod=POD_NAME, stage=stage).set(lag_seconds)
