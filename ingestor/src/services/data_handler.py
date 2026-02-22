"""
Data message handler for incoming connector data.

Processes standardized DataMessage objects from any connector type,
stores them in MinIO (bronze layer), updates partition buffers, and
extracts metadata.
"""
import json
import logging
import time
from datetime import datetime, timezone

from src.connectors.base import DataMessage
from src.utils.timestamp_utils import ensure_datetime
from src import metrics as ingestor_metrics

logger = logging.getLogger(__name__)


def create_data_handler(minio_client, state, metadata_service):
    """
    Factory that builds the unified data handler closure.

    All connectors emit ``DataMessage`` objects; this handler converts them
    into the payload format expected by MinIO / partition buffers and
    records Prometheus metrics along the way.

    Args:
        minio_client: MinIO storage client for bronze layer writes.
        state: IngestorState holding per-ingestion_id partition buffers.
        metadata_service: Optional MetadataService for schema extraction.

    Returns:
        A ``Callable[[DataMessage], None]`` suitable for passing to connectors.
    """

    def data_handler(message: DataMessage):
        source_type = message.metadata.get("source_type", "unknown")

        try:
            logger.debug(f"📊 Processing message from source: {message.source_id}")

            # ── Metrics: message received ────────────────────────────
            message_size = len(json.dumps(message.data).encode("utf-8"))
            ingestor_metrics.record_message_received(source_type, message.source_id, message_size)

            # ── Timestamp normalisation ──────────────────────────────
            raw_ts = message.timestamp if message.timestamp and message.timestamp != "timestamp" else None
            timestamp = ensure_datetime(raw_ts)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

            ingestion_time = datetime.now(timezone.utc)
            delay = (ingestion_time - timestamp).total_seconds()
            ingestor_metrics.record_timestamp_delay(source_type, delay)

            # ── Build payload for MinIO / buffers ────────────────────
            payload = {
                **message.data,
                "ingestion_id": message.source_id,
                "timestamp": timestamp.isoformat(),
                "source_type": message.metadata.get("source_type"),
                "ingestion_timestamp": ingestion_time.isoformat(),
                **{k: v for k, v in message.metadata.items() if k != "source_type"},
            }

            # Partition buffer (legacy /api/partitions compatibility)
            state.get_partition_buffer(message.source_id).append(payload)
            logger.debug(f"📋 Added to partition buffer: {message.source_id}")

            # Bronze layer storage
            minio_client.add_row(payload)
            logger.debug(f"📥 Data stored to MinIO from {message.source_id}")

            # Metadata extraction
            if metadata_service:
                metadata_service.process_data(payload)
                logger.debug("🔍 Metadata extracted")

            # ── Metrics: success ─────────────────────────────────────
            ingestor_metrics.record_message_processed(source_type, message.source_id)

        except Exception as e:
            logger.error(f"❌ Error processing data message from {message.source_id}: {e}")
            ingestor_metrics.record_message_failed(source_type, message.source_id, type(e).__name__)

    return data_handler
