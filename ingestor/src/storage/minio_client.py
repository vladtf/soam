import os, time, uuid, threading, io, json, datetime, sys
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from minio import Minio
from minio.error import S3Error


class MinioClient:
    """
    Buffers sensor rows and flushes them to MinIO as Parquet when **either**
    • FLUSH_INTERVAL seconds have passed       (timer-based)   OR
    • the in-memory buffer grows past MAX_BYTES (size-based).

    Call `add_row(payload_dict)` from your MQTT callback and
    `close()` once at program exit.
    """

    FLUSH_INTERVAL = 10          # seconds – tune for file cadence
    MAX_BYTES      = 5 * 1024**2 # 5 MiB  – tune for file size

    # ------------------------------------------------------------------ #
    # constructor
    # ------------------------------------------------------------------ #
    def __init__(self, bucket: str):
        self.client = Minio(
            os.getenv("MINIO_ENDPOINT", "minio:9000"),  # NOTE: 9000 is the default port
            os.getenv("MINIO_ACCESS_KEY", "minio"),
            os.getenv("MINIO_SECRET_KEY", "minio123"),
            secure=False,
        )
        self.bucket = bucket
        if not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)

        # buffer & accounting
        self._batch: list[dict] = []
        self._current_bytes = 0       # approximate buffer size
        self._lock  = threading.Lock()

        # kick off the periodic flush
        self._start_timer()

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def add_row(self, payload: dict) -> None:
        """Thread-safe; flushes when the buffer hits MAX_BYTES."""
        row_size = len(json.dumps(payload).encode())
        rows_to_upload = None                       # <- always defined

        with self._lock:
            self._batch.append(payload)
            self._current_bytes += row_size

            if self._current_bytes >= self.MAX_BYTES:
                rows_to_upload = self._detach_batch()

        # flush outside the lock
        if rows_to_upload:                          # <- only if we detached
            self._upload_rows(rows_to_upload)

    # legacy signature (kept for compatibility)
    def upload_data(self, object_name: str, data: bytes):
        self.add_row(json.loads(data.decode()))

    # ------------------------------------------------------------------ #
    # internal helpers
    # ------------------------------------------------------------------ #
    def _detach_batch(self) -> list[dict]:
        """Assumes caller holds the lock. Returns the current batch and clears it."""
        rows = self._batch
        self._batch = []
        self._current_bytes = 0
        return rows

    def _start_timer(self):
        self._timer = threading.Timer(self.FLUSH_INTERVAL, self._timer_flush)
        self._timer.daemon = True
        self._timer.start()

    def _timer_flush(self):
        # triggered by the background timer
        with self._lock:
            rows = self._detach_batch()
        if rows:
            self._upload_rows(rows)
        self._start_timer()  # arm the next tick

    # ---- the heavy lift --------------------------------------------------- #
    def _upload_rows(self, rows: list[dict]) -> None:
        df = pd.DataFrame(rows)

        # partition path: sensors/date=YYYY-MM-DD/hour=HH/part-uuid.parquet
        ts   = pd.to_datetime(df["timestamp"].iloc[0], utc=True)
        date = ts.strftime("%Y-%m-%d")
        hour = ts.strftime("%H")
        key_prefix = f"sensors/date={date}/hour={hour}/"
        object_key = key_prefix + f"part-{uuid.uuid4().hex}.parquet"

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
            print(f"MinIO ▶ wrote {len(rows)} rows • {buf.getbuffer().nbytes/1_048_576:.2f} MiB → {object_key}")
        except S3Error as e:
            print("MinIO upload error:", e)

    # ------------------------------------------------------------------ #
    # graceful shutdown
    # ------------------------------------------------------------------ #
    def close(self):
        self._timer.cancel()        # stop the periodic trigger
        with self._lock:
            rows = self._detach_batch()
        if rows:
            self._upload_rows(rows)
