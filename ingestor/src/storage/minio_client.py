import os
import time
import uuid
import threading
import io
import json
from datetime import datetime, timezone
import sys
import logging
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


class MinioClient:
    """
    Buffers sensor rows and flushes them to MinIO as Parquet when **either**
    • FLUSH_INTERVAL seconds have passed       (timer-based)   OR
    • the in-memory buffer grows past MAX_BYTES (size-based).

    Rows are now grouped by ingestion_id to ensure proper partitioning.

    Call `add_row(payload_dict)` from your MQTT callback and
    `close()` once at program exit.
    """

    FLUSH_INTERVAL = 10          # seconds – tune for file cadence
    MAX_BYTES = 5 * 1024**2  # 5 MiB  – tune for file size

    BRONZE_PATH = "bronze"

    # ------------------------------------------------------------------ #
    # constructor
    # ------------------------------------------------------------------ #
    def __init__(self, bucket: str, endpoint: str = None, access_key: str = None, secret_key: str = None):
        # Use provided config or fall back to environment variables
        minio_endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "minio:9000")
        # Remove http:// or https:// prefix if present
        if minio_endpoint.startswith("http://"):
            minio_endpoint = minio_endpoint[7:]
        elif minio_endpoint.startswith("https://"):
            minio_endpoint = minio_endpoint[8:]

        logger.info("MinIO ▶ Initializing with endpoint: %s, bucket: %s", minio_endpoint, bucket)

        self.client = Minio(
            minio_endpoint,
            access_key or os.getenv("MINIO_ACCESS_KEY", "minio"),
            secret_key or os.getenv("MINIO_SECRET_KEY", "minio123"),
            secure=False,
        )
        self.bucket = bucket
        if not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)
            logger.info("MinIO ▶ Created bucket: %s", bucket)
        else:
            logger.info("MinIO ▶ Using existing bucket: %s", bucket)

        # buffer & accounting - now organized by ingestion_id
        self._batch_by_ingestion_id = {}  # dict[ingestion_id] -> list[dict]
        self._bytes_by_ingestion_id = {}  # dict[ingestion_id] -> int
        self._lock = threading.Lock()

        # kick off the periodic flush
        self._start_timer()

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def add_row(self, payload: dict) -> None:
        """Thread-safe; flushes when any ingestion_id buffer hits MAX_BYTES."""
        row_size = len(json.dumps(payload).encode())
        ingestion_id = payload.get("ingestion_id", "unknown")
        rows_to_upload = None

        with self._lock:
            # Initialize ingestion_id buffer and size if needed
            if ingestion_id not in self._batch_by_ingestion_id:
                self._batch_by_ingestion_id[ingestion_id] = []
                self._bytes_by_ingestion_id[ingestion_id] = 0
            
            self._batch_by_ingestion_id[ingestion_id].append(payload)
            self._bytes_by_ingestion_id[ingestion_id] += row_size

            if self._bytes_by_ingestion_id[ingestion_id] >= self.MAX_BYTES:
                rows_to_upload = self._detach_batch_for_ingestion_id(ingestion_id)

        # flush outside the lock
        if rows_to_upload:
            self._upload_rows(rows_to_upload)

    # legacy signature (kept for compatibility)
    def upload_data(self, object_name: str, data: bytes):
        self.add_row(json.loads(data.decode()))

    # ------------------------------------------------------------------ #
    # internal helpers
    # ------------------------------------------------------------------ #
    def _detach_all_batches(self) -> list[dict]:
        """Assumes caller holds the lock. Returns all current batches and clears them."""
        all_rows = []
        for ingestion_id, rows in self._batch_by_ingestion_id.items():
            all_rows.extend(rows)
        self._batch_by_ingestion_id = {}
        self._bytes_by_ingestion_id = {}
        return all_rows

    def _detach_batch_for_ingestion_id(self, ingestion_id: str) -> list[dict]:
        """Assumes caller holds the lock. Detaches and returns the batch for a specific ingestion_id."""
        rows = self._batch_by_ingestion_id.get(ingestion_id, [])
        if ingestion_id in self._batch_by_ingestion_id:
            del self._batch_by_ingestion_id[ingestion_id]
        if ingestion_id in self._bytes_by_ingestion_id:
            del self._bytes_by_ingestion_id[ingestion_id]
        return rows

    def _start_timer(self):
        self._timer = threading.Timer(self.FLUSH_INTERVAL, self._timer_flush)
        self._timer.daemon = True
        self._timer.start()

    def _timer_flush(self):
        # triggered by the background timer
        with self._lock:
            ingestion_batches = {}
            for ingestion_id in list(self._batch_by_ingestion_id.keys()):
                rows = self._detach_batch_for_ingestion_id(ingestion_id)
                if rows:
                    ingestion_batches[ingestion_id] = rows
        # Upload each ingestion_id's rows separately to preserve partitioning
        for ingestion_id, rows in ingestion_batches.items():
            self._upload_rows(rows)
        self._start_timer()  # arm the next tick

    def _get_buf_size_message(self, buf_size: int) -> str:
        """Get a human-readable message about the buffer size."""
        if buf_size < 1024:
            return f"{buf_size} bytes"
        elif buf_size < 1024**2:
            return f"{buf_size / 1024:.2f} KiB"
        else:
            return f"{buf_size / 1024**2:.2f} MiB"

    # ---- the heavy lift --------------------------------------------------- #
    def _upload_rows(self, rows: list[dict]) -> None:
        if not rows:
            logger.debug("MinIO ▶ No rows to upload")
            return

        logger.debug("MinIO ▶ Preparing to upload %d rows", len(rows))
        logger.debug("MinIO ▶ Sample row: %s", rows[0] if rows else None)

        # Group rows by ingestion_id to ensure proper partitioning
        rows_by_ingestion_id = {}
        for row in rows:
            ingestion_id = row.get("ingestion_id", "unknown")
            if ingestion_id not in rows_by_ingestion_id:
                rows_by_ingestion_id[ingestion_id] = []
            rows_by_ingestion_id[ingestion_id].append(row)

        logger.info("MinIO ▶ Uploading %d distinct ingestion_ids: %s", 
                   len(rows_by_ingestion_id), list(rows_by_ingestion_id.keys()))

        # Process each ingestion_id group separately
        for ingestion_id, group_rows in rows_by_ingestion_id.items():
            logger.debug("MinIO ▶ Processing %d rows for ingestion_id: %s", len(group_rows), ingestion_id)
            self._upload_ingestion_group(group_rows, ingestion_id)

    def _upload_ingestion_group(self, rows: list[dict], ingestion_id: str) -> None:
        """Upload a group of rows that all have the same ingestion_id to bronze layer.
        
        Writes to bronze/ingestion_id=<id>/date=YYYY-MM-DD/hour=HH/part-uuid.parquet
        Following medallion architecture: bronze (raw) -> silver (processed) -> gold (aggregated)
        """
        df = pd.DataFrame(rows)

        # Get current partition values
        now = datetime.now(timezone.utc)
        date = now.strftime("%Y-%m-%d")
        hour = now.hour

        # Try to get more accurate timestamp from the data
        try:
            ts = pd.to_datetime(df["timestamp"].iloc[0], utc=True)
            date = ts.strftime("%Y-%m-%d")
            hour = ts.strftime("%H")
        except Exception as e:
            logger.warning("MinIO ▶ Error parsing timestamp for ingestion_id %s: %s", ingestion_id, e)
            # Use current time as fallback
            now = datetime.now(timezone.utc)
            date = now.strftime("%Y-%m-%d")
            hour = now.strftime("%H")

        key_prefix = f"{self.BRONZE_PATH}/ingestion_id={ingestion_id}/date={date}/hour={hour}/"
        object_key = key_prefix + f"part-{uuid.uuid4().hex}.parquet"

        # Normalize numeric types: convert all int columns to float64 (double)
        # This ensures consistent schema across files from different sources
        # Spark can then read all files without type conflicts (INT64 vs DOUBLE)
        for col in df.columns:
            if pd.api.types.is_integer_dtype(df[col]):
                df[col] = df[col].astype('float64')
                logger.debug("MinIO ▶ Converted column '%s' from int to float64", col)

        # write to an in-memory Parquet buffer
        buf = io.BytesIO()
        table: pa.Table = pa.Table.from_pandas(df)
        pq.write_table(table, buf, compression="snappy")
        buf.seek(0)

        try:
            self.client.put_object(
                self.bucket,
                object_key,
                data=buf,
                length=buf.getbuffer().nbytes,
                content_type="application/octet-stream",
            )
            logger.info("MinIO ▶ wrote %d rows • %s → %s", len(rows), self._get_buf_size_message(buf.getbuffer().nbytes), object_key)
        except S3Error as e:
            logger.error("MinIO upload error for ingestion_id %s: %s", ingestion_id, e)

    # ------------------------------------------------------------------ #
    # graceful shutdown
    # ------------------------------------------------------------------ #
    def close(self):
        self._timer.cancel()        # stop the periodic trigger
        with self._lock:
            all_rows = []
            for ingestion_id in list(self._batch_by_ingestion_id.keys()):
                rows = self._detach_batch_for_ingestion_id(ingestion_id)
                if rows:
                    all_rows.extend(rows)
        if all_rows:
            self._upload_rows(all_rows)
