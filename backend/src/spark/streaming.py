"""Spark streaming job management."""
import logging
import threading
from typing import Optional
from pyspark.sql import DataFrame, functions as F
from pyspark.sql.streaming import StreamingQuery

from .config import SparkConfig
from .session import SparkSessionManager
from .enrichment import EnrichmentManager
from .query_manager import StreamingQueryManager
from src.utils.settings_manager import settings_manager
from src.utils.step_profiler import profile_step
from src.utils.spark_utils import extract_sensor_id

logger = logging.getLogger(__name__)

MODULE = "streaming_manager"


def get_temperature_threshold() -> float:
    return settings_manager.get_temperature_threshold(SparkConfig.TEMP_THRESHOLD)


class StreamingManager:
    """Manages Spark streaming jobs for temperature data and alerts."""

    def __init__(self, session_manager: SparkSessionManager, minio_bucket: str):
        self.session_manager = session_manager
        self.minio_bucket = minio_bucket

        self.bronze_path = f"s3a://{minio_bucket}/{SparkConfig.BRONZE_PATH}/"
        self.enriched_path = f"s3a://{minio_bucket}/{SparkConfig.ENRICHED_PATH}/"
        self.gold_temp_avg_path = f"s3a://{minio_bucket}/{SparkConfig.GOLD_TEMP_AVG_PATH}/"
        self.gold_alerts_path = f"s3a://{minio_bucket}/{SparkConfig.GOLD_ALERTS_PATH}/"

        self.enrichment_manager = EnrichmentManager(
            self.session_manager.spark, minio_bucket,
            self.bronze_path, self.enriched_path
        )

        self.avg_query: Optional[StreamingQuery] = None
        self.alert_query: Optional[StreamingQuery] = None

        self.AVG_QUERY_NAME = "temperature_5min_averages"
        self.ALERT_QUERY_NAME = "temperature_alert_detector"

        self._avg_query_lock = threading.Lock()
        self._alert_query_lock = threading.Lock()
        self._ensure_streams_lock = threading.Lock()

        self._qm = StreamingQueryManager(self.session_manager.spark)

    # ------------------------------------------------------------------ #
    # Shared helpers
    # ------------------------------------------------------------------ #

    def _read_enriched_stream(self) -> Optional[DataFrame]:
        try:
            return self.session_manager.spark.readStream.format("delta").load(self.enriched_path)
        except Exception as e:
            logger.info("Enriched delta not available yet: %s", e)
            return None

    def _extract_temperature_stream(self, enriched_stream: DataFrame) -> DataFrame:
        from .enrichment.union_schema import UnionSchemaTransformer
        stream = UnionSchemaTransformer.extract_column_from_union(
            enriched_stream, "temperature", prefer_normalized=True
        )
        return extract_sensor_id(stream)

    def _filter_valid_temperature(self, df: DataFrame) -> DataFrame:
        return df.filter(F.col("temperature").isNotNull() & ~F.isnan(F.col("temperature")))

    def _write_gold_stream(
        self, df: DataFrame, query_name: str, output_path: str,
        checkpoint_suffix: str, output_mode: str, trigger: str,
    ) -> StreamingQuery:
        try:
            return (
                df.writeStream
                .format("delta")
                .option("path", output_path)
                .option("checkpointLocation", f"s3a://{self.minio_bucket}/{checkpoint_suffix}")
                .option("mergeSchema", "true")
                .outputMode(output_mode)
                .queryName(query_name)
                .trigger(processingTime=trigger)
                .start()
            )
        except Exception as e:
            if "already active" in str(e) or "Cannot start query with name" in str(e):
                logger.warning("⚠️ Query %s conflict, reattaching", query_name)
                existing = self._qm.get_by_name(query_name)
                if existing and existing.isActive:
                    return existing
            raise

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def is_data_directory_ready(self) -> bool:
        try:
            self.session_manager.spark.read \
                .option("basePath", self.bronze_path) \
                .option("recursiveFileLookup", "true") \
                .option("pathGlobFilter", "*.parquet") \
                .parquet(self.bronze_path)
            return True
        except Exception as e:
            if "Path does not exist" in str(e) or "Unable to infer schema" in str(e):
                logger.info("🔍 Bronze directory not ready yet: %s", e)
            else:
                logger.debug("🔍 Data directory not ready: %s", e)
            return False

    def start_streams_safely(self) -> None:
        self._qm.stop_all()
        for label, fn in [
            ("enrichment", self._start_enrichment_stream),
            ("temperature", self.start_temperature_stream),
            ("alert", self.start_alert_stream),
        ]:
            try:
                fn()
                logger.info("✅ %s stream started", label.capitalize())
            except Exception as e:
                logger.error("❌ Failed to start %s stream: %s", label, e)
                if label == "enrichment":
                    import traceback
                    logger.error("Traceback: %s", traceback.format_exc())

    @profile_step(MODULE, "start_enrichment_stream")
    def _start_enrichment_stream(self) -> None:
        self.enrichment_manager.start_enrichment_stream()

    @profile_step(MODULE, "ensure_enrichment")
    def _ensure_enrichment_running(self) -> None:
        self.enrichment_manager.ensure_enrichment_running()

    def ensure_streams_running(self) -> None:
        with self._ensure_streams_lock:
            try:
                self._ensure_enrichment_running()

                with self._avg_query_lock:
                    if not self.avg_query or not self.avg_query.isActive:
                        self.avg_query = self._qm.start_or_reattach(
                            self.AVG_QUERY_NAME, self.start_temperature_stream
                        )

                with self._alert_query_lock:
                    if not self.alert_query or not self.alert_query.isActive:
                        self.alert_query = self._qm.start_or_reattach(
                            self.ALERT_QUERY_NAME, self.start_alert_stream
                        )
            except Exception as e:
                logger.error("❌ Error ensuring streams are running: %s", e)

    @profile_step(MODULE, "start_temperature_stream")
    def start_temperature_stream(self) -> None:
        enriched_stream = self._read_enriched_stream()
        if enriched_stream is None:
            return

        temp_stream = self._extract_temperature_stream(enriched_stream)

        valid = (
            self._filter_valid_temperature(temp_stream)
            .withWatermark("ingest_ts", SparkConfig.WATERMARK_DELAY)
        )

        five_min_avg = (
            valid
            .groupBy(
                F.window("ingest_ts", SparkConfig.AVG_WINDOW, SparkConfig.AVG_SLIDE).alias("time_window"),
                "sensorId"
            )
            .agg(
                F.round(F.avg("temperature"), 2).alias("avg_temp"),
                F.min("ingest_ts").alias("min_enrichment_ts")
            )
            .selectExpr("sensorId", "time_window.start as time_start", "avg_temp", "min_enrichment_ts")
        )

        self.avg_query = self._write_gold_stream(
            df=five_min_avg, query_name=self.AVG_QUERY_NAME,
            output_path=self.gold_temp_avg_path,
            checkpoint_suffix=f"{SparkConfig.GOLD_TEMP_AVG_CHECKPOINT}_union",
            output_mode="complete", trigger=SparkConfig.TEMPERATURE_STREAM_TRIGGER,
        )

    @profile_step(MODULE, "start_alert_stream")
    def start_alert_stream(self) -> None:
        enriched_stream = self._read_enriched_stream()
        if enriched_stream is None:
            return

        alert_stream = self._extract_temperature_stream(enriched_stream)

        temp_threshold = get_temperature_threshold()
        logger.info("📊 Temperature alert threshold: %s°C", temp_threshold)

        alerts = (
            self._filter_valid_temperature(alert_stream)
            .filter(F.col("temperature") > temp_threshold)
            .withColumn("alert_type", F.lit("TEMP_OVER_LIMIT"))
            .withColumn("alert_id", F.concat(F.col("sensorId"), F.lit("_"), F.col("event_time")))
            .withColumn("alert_time", F.current_timestamp())
            .dropDuplicates(["sensorId"])
            .select("sensorId", "temperature", "event_time", "alert_type")
        )

        self.alert_query = self._write_gold_stream(
            df=alerts, query_name=self.ALERT_QUERY_NAME,
            output_path=self.gold_alerts_path,
            checkpoint_suffix=f"{SparkConfig.GOLD_ALERT_CHECKPOINT}_union",
            output_mode="append", trigger=SparkConfig.ALERT_STREAM_TRIGGER,
        )

    def stop_streams(self) -> None:
        for label, query in [("Temperature", self.avg_query), ("Alert", self.alert_query)]:
            if query and query.isActive:
                self._qm.stop_gracefully(label, timeout_seconds=30)

        try:
            self.enrichment_manager.stop_enrichment_stream()
        except Exception as e:
            logger.error("❌ Error stopping enrichment stream: %s", e)

        self.avg_query = None
        self.alert_query = None
        logger.info("✅ All streaming queries stopped")
