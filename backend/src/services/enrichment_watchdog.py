"""
Background watchdog for the enrichment pipeline.

Runs in a daemon thread and periodically:
1. Ensures the enrichment and gold-layer streams are active.
2. Detects schema evolution (new fields in the ingestor) and
   restarts the enrichment stream so the new columns are included.

Usage:
    watchdog = EnrichmentWatchdog(streaming_manager)
    watchdog.start()   # non-blocking, spawns daemon thread
    ...
    watchdog.stop()    # signals the thread to exit
"""
import threading
import time
from typing import Optional

from src.utils.logging import get_logger
from src.services.ingestor_schema_client import IngestorSchemaClient

logger = get_logger(__name__)


class EnrichmentWatchdog:
    """Daemon thread that keeps enrichment streams healthy and
    reacts to schema changes from the ingestor."""

    def __init__(
        self,
        streaming_manager,
        *,
        poll_interval: float = 30.0,
        schema_check_interval: float = 60.0,
    ) -> None:
        self._streaming = streaming_manager
        self._poll_interval = poll_interval
        self._schema_check_interval = schema_check_interval

        self._ingestor_client = IngestorSchemaClient()
        self._last_schema_check: float = 0.0

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Start the watchdog in a daemon thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("⚠️ Enrichment watchdog already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="enrichment-watchdog", daemon=True,
        )
        self._thread.start()
        logger.info("🚀 Enrichment watchdog started (poll=%ss, schema_check=%ss)",
                     self._poll_interval, self._schema_check_interval)

    def stop(self) -> None:
        """Signal the watchdog to stop and wait for it to finish."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
            logger.info("🛑 Enrichment watchdog stopped")

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #

    def _run(self) -> None:
        # Initial delay — give other services time to boot
        if self._stop_event.wait(timeout=15):
            return

        while not self._stop_event.is_set():
            try:
                self._ensure_streams()
                self._maybe_check_schema_evolution()
            except Exception as e:
                logger.error("❌ Enrichment watchdog error: %s", e)

            self._stop_event.wait(timeout=self._poll_interval)

    # ------------------------------------------------------------------ #
    # Stream health
    # ------------------------------------------------------------------ #

    def _ensure_streams(self) -> None:
        """Ensure all streaming queries (enrichment + gold) are running."""
        try:
            self._streaming.ensure_streams_running()
        except Exception as e:
            logger.warning("⚠️ Could not ensure streams: %s", e)

    # ------------------------------------------------------------------ #
    # Schema evolution
    # ------------------------------------------------------------------ #

    def _maybe_check_schema_evolution(self) -> None:
        """Check if the ingestor has new fields not yet in the stream schema.
        
        With raw_json support, the sensor_data map is built dynamically from
        the JSON payload, so new sensor fields are picked up automatically.
        This check handles the one-time case where raw_json appears as a new
        column (e.g., after the ingestor is upgraded to include it).
        """
        from src.spark.config import SparkConfig
        if SparkConfig.BYPASS_ENRICHMENT:
            return  # Fixed schema in bypass mode — no evolution to detect

        now = time.time()
        if (now - self._last_schema_check) < self._schema_check_interval:
            return
        self._last_schema_check = now

        try:
            self._ingestor_client._schema_cache = None
            schema = self._ingestor_client.get_merged_spark_schema_sync(cache_ttl_seconds=0)
            if not schema:
                return

            ingestor_fields = frozenset(f.name for f in schema.fields)

            enrichment_mgr = self._streaming.enrichment_manager
            stream_fields = enrichment_mgr._active_schema_fields
            if stream_fields is None:
                return

            added = ingestor_fields - stream_fields
            if not added:
                return

            logger.info(
                "🔄 Schema evolution detected — %d new field(s): %s. "
                "Restarting enrichment stream.",
                len(added), sorted(added),
            )
            enrichment_mgr.stop_enrichment_stream()
            enrichment_mgr.ingestor_client._schema_cache = None
            enrichment_mgr.start_enrichment_stream()
            logger.info("✅ Enrichment stream restarted with updated schema")
        except Exception as e:
            logger.warning("⚠️ Schema evolution check failed: %s", e)
