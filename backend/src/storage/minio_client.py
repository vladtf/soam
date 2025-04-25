import os, time, uuid, threading, io, json, datetime
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from minio import Minio
from minio.error import S3Error


class MinioClient:
    """
    Buffers sensor rows and flushes them to MinIO as Parquet
    every FLUSH_INTERVAL seconds.
    """
    FLUSH_INTERVAL = 10            # seconds ─ tune to get 5-20 MB files
    BUCKET         = os.getenv("MINIO_BUCKET_NAME", "mybucket")

    def __init__(self):
        self.client = Minio(
            os.getenv("MINIO_ENDPOINT", "minio:9000"),
            os.getenv("MINIO_ACCESS_KEY", "minio"),
            os.getenv("MINIO_SECRET_KEY", "minio123"),
            secure=False,
        )
        if not self.client.bucket_exists(self.BUCKET):
            self.client.make_bucket(self.BUCKET)

        self._batch: list[dict] = []
        self._lock  = threading.Lock()
        self._timer = threading.Timer(self.FLUSH_INTERVAL, self._flush_batch)
        self._timer.daemon = True
        self._timer.start()

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def add_row(self, payload: dict) -> None:
        """
        Call this from your MQTT callback.
        The method is lock-safe and returns immediately.
        """
        with self._lock:
            self._batch.append(payload)

    # legacy signature you already used (kept for compatibility)
    def upload_data(self, object_name: str, data: dict):
        self.add_row(json.loads(data.decode()))

    # ------------------------------------------------------------------ #
    # internal helpers
    # ------------------------------------------------------------------ #
    def _flush_batch(self):
        with self._lock:
            rows = self._batch
            self._batch = []               # start a fresh list
        if not rows:
            self._restart_timer()
            return

        df = pd.DataFrame(rows)

        # partition path: sensors/date=2025-04-25/hour=15/part-uuid.parquet
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
                self.BUCKET,
                object_key,
                data=buf,
                length=buf.getbuffer().nbytes,
                content_type="application/octet-stream",
            )
            print(f"MinIO ▶ wrote {len(rows)} rows → {object_key}")
        except S3Error as e:
            print("MinIO upload error:", e)

        self._restart_timer()

    def _restart_timer(self):
        self._timer = threading.Timer(self.FLUSH_INTERVAL, self._flush_batch)
        self._timer.daemon = True
        self._timer.start()

    # ------------------------------------------------------------------ #
    # graceful shutdown (call at program exit)
    # ------------------------------------------------------------------ #
    def close(self):
        self._timer.cancel()
        self._flush_batch()
