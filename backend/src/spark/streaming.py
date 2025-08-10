"""
Spark streaming job management.
"""
import logging
from typing import Optional
from pyspark.sql import functions as F
from pyspark.sql.streaming import StreamingQuery

from .config import SparkConfig, SparkSchemas
from .cleaner import DataCleaner
from .session import SparkSessionManager

logger = logging.getLogger(__name__)


class StreamingManager:
    """Manages Spark streaming jobs for temperature data and alerts."""

    def __init__(self, session_manager: SparkSessionManager, minio_bucket: str):
        """Initialize StreamingManager."""
        self.session_manager = session_manager
        self.minio_bucket = minio_bucket

        # Build paths
        self.sensors_path = f"s3a://{minio_bucket}/{SparkConfig.SENSORS_PATH}"
        self.silver_path = f"s3a://{minio_bucket}/{SparkConfig.SILVER_PATH}"
        self.alerts_path = f"s3a://{minio_bucket}/{SparkConfig.ALERT_PATH}"
        # New: enriched target path
        self.enriched_path = f"s3a://{minio_bucket}/{SparkConfig.ENRICHED_PATH}"

        # Streaming queries
        self.avg_query: Optional[StreamingQuery] = None
        self.alert_query: Optional[StreamingQuery] = None
        # New: enrichment query
        self.enrich_query: Optional[StreamingQuery] = None

        # Stable query names to enforce single instance per stream
        self.ENRICH_QUERY_NAME = "enrich_stream"
        self.AVG_QUERY_NAME = "five_min_avg_stream"
        self.ALERT_QUERY_NAME = "alert_stream"

    def _get_query_by_name(self, name: str) -> Optional[StreamingQuery]:
        """Return active StreamingQuery by name if present."""
        try:
            for q in self.session_manager.spark.streams.active:
                try:
                    if q.name == name:
                        return q
                except Exception:
                    continue
        except Exception:
            return None
        return None

    def is_data_directory_ready(self) -> bool:
        """Check if the sensors data directory exists and is accessible."""
        try:
            # Try to access the sensors directory
            self.session_manager.spark.read.option("basePath", self.sensors_path).parquet(self.sensors_path)
            return True
        except Exception as e:
            logger.debug(f"Data directory not ready: {e}")
            return False

    def start_streams_safely(self) -> None:
        """Start streaming jobs with error handling."""
        try:
            self.start_enrichment_stream()
            logger.info("Enrichment stream started successfully")
        except Exception as e:
            logger.error(f"Failed to start enrichment stream: {e}")

        try:
            self.start_temperature_stream()
            logger.info("Temperature streaming started successfully")
        except Exception as e:
            logger.error(f"Failed to start temperature stream: {e}")

        try:
            self.start_alert_stream()
            logger.info("Alert streaming started successfully")
        except Exception as e:
            logger.error(f"Failed to start alert stream: {e}")

    def ensure_streams_running(self) -> None:
        """Ensure streaming jobs are running, start them if not."""
        try:
            # Ensure enrichment first, as downstream jobs rely on it
            if self.enrich_query is None or not self.enrich_query.isActive:
                logger.info("Enrichment stream not active, attempting to start...")
                existing = self._get_query_by_name(self.ENRICH_QUERY_NAME)
                if existing and existing.isActive:
                    self.enrich_query = existing
                else:
                    self.start_enrichment_stream()

            # Check temperature stream
            if self.avg_query is None or not self.avg_query.isActive:
                logger.info("Temperature stream not active, attempting to start...")
                existing = self._get_query_by_name(self.AVG_QUERY_NAME)
                if existing and existing.isActive:
                    self.avg_query = existing
                else:
                    self.start_temperature_stream()

            # Check alert stream
            if self.alert_query is None or not self.alert_query.isActive:
                logger.info("Alert stream not active, attempting to start...")
                existing = self._get_query_by_name(self.ALERT_QUERY_NAME)
                if existing and existing.isActive:
                    self.alert_query = existing
                else:
                    self.start_alert_stream()

        except Exception as e:
            logger.error(f"Error ensuring streams are running: {e}")

    def start_temperature_stream(self) -> None:
        """Start the temperature averaging stream (5-minute windows) from enriched data."""
        spark = self.session_manager.spark

        # Read streaming data from enriched silver delta (skip if not ready)
        try:
            enriched_stream = (
                spark.readStream
                .format("delta")
                .load(self.enriched_path)
            )
        except Exception as e:
            logger.info("Enriched delta not available yet, skipping temperature stream start: %s", e)
            return

        # Ensure target Delta table exists with schema to prevent DELTA_SCHEMA_NOT_SET
        try:
            spark.read.format("delta").load(self.silver_path).limit(0)
        except Exception:
            from pyspark.sql import types as T
            empty_schema = T.StructType([
                T.StructField("sensorId", T.StringType()),
                T.StructField("time_start", T.TimestampType()),
                T.StructField("avg_temp", T.DoubleType()),
            ])
            empty_df = spark.createDataFrame([], empty_schema)
            (
                empty_df.write
                .format("delta")
                .mode("ignore")
                .option("overwriteSchema", "true")
                .save(self.silver_path)
            )

        # Calculate sliding window averages based on event_time; ignore rows without temperature
        five_min_avg = (
            enriched_stream
            .filter((F.col("temperature").isNotNull()) & (~F.isnan(F.col("temperature"))))
            .withWatermark("event_time", SparkConfig.WATERMARK_DELAY)
            .groupBy(
                F.window("event_time", SparkConfig.AVG_WINDOW, SparkConfig.AVG_SLIDE).alias("time_window"),
                "sensorId"
            )
            .agg(F.round(F.avg("temperature"), 2).alias("avg_temp"))
            .selectExpr(
                "sensorId",
                "time_window.start as time_start",
                "avg_temp"
            )
        )

        # Write to Delta table
        self.avg_query = (
            five_min_avg.writeStream
            .format("delta")
            .option("path", self.silver_path)
            .option("checkpointLocation", f"s3a://{self.minio_bucket}/{SparkConfig.FIVE_MIN_AVG_CHECKPOINT}")
            .option("mergeSchema", "true")
            .outputMode("complete")
            .queryName(self.AVG_QUERY_NAME)
            .trigger(processingTime=SparkConfig.TEMPERATURE_STREAM_TRIGGER)
            .start()
        )

    def start_alert_stream(self) -> None:
        """Start the temperature alert stream from enriched data."""
        spark = self.session_manager.spark

        # Read streaming data from enriched silver delta
        try:
            enriched_stream = (
                spark.readStream
                .format("delta")
                .load(self.enriched_path)
            )
        except Exception as e:
            logger.info("Enriched delta not available yet, skipping alert stream start: %s", e)
            return

        # Filter for temperature alerts and deduplicate
        alerts = (
            enriched_stream
            .filter((F.col("temperature").isNotNull()) & (~F.isnan(F.col("temperature"))))
            .filter(F.col("temperature") > SparkConfig.TEMP_THRESHOLD)
            .withColumn("alert_type", F.lit("TEMP_OVER_LIMIT"))
            .withColumn("alert_id", F.concat(F.col("sensorId"), F.lit("_"), F.col("event_time")))
            .withColumn("alert_time", F.current_timestamp())
            .dropDuplicates(["sensorId"])  # keep latest per sensor
            .select("sensorId", "temperature", "event_time", "alert_type")
        )

        # Write to Delta table
        self.alert_query = (
            alerts.writeStream
            .format("delta")
            .option("path", self.alerts_path)
            .option("checkpointLocation", f"s3a://{self.minio_bucket}/{SparkConfig.ALERT_STREAM_CHECKPOINT}")
            .option("mergeSchema", "true")
            .outputMode("append")
            .queryName(self.ALERT_QUERY_NAME)
            .trigger(processingTime=SparkConfig.ALERT_STREAM_TRIGGER)
            .start()
        )

    def start_enrichment_stream(self) -> None:
        """Start the enrichment stream: read raw sensors, add metadata, write silver/enriched."""
        spark = self.session_manager.spark
        cleaner = DataCleaner()

        # Try to infer schema from existing parquet files (batch read), fallback to known sensor schema
        try:
            static_df = (
                spark.read
                .option("basePath", self.sensors_path)
                .parquet(f"{self.sensors_path}ingestion_id=*/date=*/hour=*")
            )
            inferred_schema = static_df.schema
            logger.info(
                "Inferred raw sensors schema from existing files for streaming read at %s",
                f"{self.sensors_path}ingestion_id=*/date=*/hour=*",
            )
        except Exception:
            inferred_schema = SparkSchemas.get_sensor_schema()
            logger.info("Falling back to predefined sensor schema for streaming read")

        # Read raw parquet with schema (required by structured streaming for file sources)
        raw_stream = (
            spark.readStream
            .schema(inferred_schema)
            .option("basePath", self.sensors_path)
            .option("maxFilesPerTrigger", SparkConfig.MAX_FILES_PER_TRIGGER)
            .parquet(f"{self.sensors_path}ingestion_id=*/date=*/hour=*")
        )

        # Normalize/cleanup: lower-case columns and rename known variants
        normalized = cleaner.normalize_sensor_columns(raw_stream)
        # Extra safety: coalesce sensorId from common variants if DB rules didn't map.
        # Only reference columns that actually exist to avoid unresolved column errors.
        sensor_candidates = [c for c in ["sensorId", "sensor_id", "sensor-id", "sensorid"] if c in normalized.columns]
        if sensor_candidates:
            try:
                # If more than one candidate exists or the only one isn't the canonical name, coalesce into sensorId
                if len(sensor_candidates) > 1 or sensor_candidates[0] != "sensorId":
                    normalized = normalized.withColumn("sensorId", F.coalesce(*[F.col(c) for c in sensor_candidates]))
            except Exception:
                # Best-effort; skip if analyzer complains during planning
                pass

        # Cast to expected schema types (safe casts) and derive event time
        # Be robust to multiple timestamp formats: ISO-8601 with T and timezone
        ts_col = F.col("timestamp").cast("string")
        event_time = F.coalesce(
            # Common flexible parser may handle some forms
            F.to_timestamp(ts_col),
            # ISO with timezone and millis
            F.to_timestamp(ts_col, "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"),
            # ISO with microseconds (no TZ)
            F.to_timestamp(ts_col, "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"),
            # ISO without fraction, with TZ
            F.to_timestamp(ts_col, "yyyy-MM-dd'T'HH:mm:ssXXX"),
            # ISO without fraction or TZ
            F.to_timestamp(ts_col, "yyyy-MM-dd'T'HH:mm:ss"),
            # Space-separated variants
            F.to_timestamp(F.regexp_replace(ts_col, 'T', ' '), "yyyy-MM-dd HH:mm:ss.SSSSSS"),
            F.to_timestamp(F.regexp_replace(ts_col, 'T', ' '), "yyyy-MM-dd HH:mm:ss.SSS"),
            F.to_timestamp(F.regexp_replace(ts_col, 'T', ' '), "yyyy-MM-dd HH:mm:ss")
        )
        typed = (
            normalized
            .withColumn("sensorId", F.col("sensorId").cast("string"))
            .withColumn("temperature", F.col("temperature").cast("double"))
            .withColumn("humidity", F.col("humidity").cast("double"))
            .withColumn("timestamp", ts_col)
            .withColumn("event_time", event_time)
        )

        # Example enrichment: add ingest_date, hour, and static metadata fields
        # Ensure ingestion_id column always exists; default to null if missing in raw
        ingestion_col = F.lit(None).cast("string")
        try:
            if "ingestion_id" in typed.columns:
                ingestion_col = F.col("ingestion_id").cast("string")
        except Exception:
            # In rare cases, accessing columns might fail before schema is materialized; keep null default
            pass

        base_cols = (
            typed
            .withColumn("ingest_ts", F.current_timestamp())
            .withColumn("ingest_date", F.to_date(F.col("event_time")))
            .withColumn("ingest_hour", F.date_format(F.col("event_time"), "HH"))
            # Add example metadata; replace with real lookups if needed
            .withColumn("source", F.lit("mqtt"))
            .withColumn("site", F.lit("default"))
            .withColumn("ingestion_id", ingestion_col)
            .select(
                "sensorId",
                "temperature",
                "humidity",
                "event_time",
                "ingest_ts",
                "ingest_date",
                "ingest_hour",
                "source",
                "site",
                "ingestion_id",
            )
        )

        # Ensure target enriched Delta table exists with schema to prevent DELTA_SCHEMA_NOT_SET on readers
        try:
            spark.read.format("delta").load(self.enriched_path).limit(0)
        except Exception:
            from pyspark.sql import types as T
            enriched_schema = T.StructType([
                T.StructField("sensorId", T.StringType()),
                T.StructField("temperature", T.DoubleType()),
                T.StructField("humidity", T.DoubleType()),
                T.StructField("event_time", T.TimestampType()),
                T.StructField("ingest_ts", T.TimestampType()),
                T.StructField("ingest_date", T.DateType()),
                T.StructField("ingest_hour", T.StringType()),
                T.StructField("source", T.StringType()),
                T.StructField("site", T.StringType()),
                T.StructField("ingestion_id", T.StringType()),
            ])
            empty_enriched = spark.createDataFrame([], enriched_schema)
            (
                empty_enriched.write
                .format("delta")
                .mode("ignore")
                .option("overwriteSchema", "true")
                .save(self.enriched_path)
            )

        # Avoid duplicate starts if another session/thread already launched it
        existing = self._get_query_by_name(self.ENRICH_QUERY_NAME)
        if existing and existing.isActive:
            self.enrich_query = existing
            return

        # Filter stream to only registered devices using foreachBatch to load allowed list once per micro-batch
        def write_if_registered(batch_df, batch_id: int):
            try:
                logger.info("Enrichment foreachBatch started: batch_id=%s, cols=%s", batch_id, ",".join(batch_df.columns))
                from sqlalchemy.orm import sessionmaker
                from src.database.database import engine
                from src.database.models import Device
                SessionLocal = sessionmaker(bind=engine)
                session = SessionLocal()
                try:
                    allowed = session.query(Device.sensor_id, Device.ingestion_id).filter(Device.enabled == True).all()
                    allowed_pairs = [(sid, iid) for (sid, iid) in allowed]
                finally:
                    session.close()
                if not allowed_pairs:
                    # Nothing registered; skip writing this batch
                    try:
                        input_count = batch_df.count()
                    except Exception:
                        input_count = -1
                    logger.info("Enrichment foreachBatch: no allowed devices; skipping (input=%s)", input_count)
                    return
                # Filter by (sensorId, ingestion_id) with normalization and null-handling
                from pyspark.sql.functions import lower, trim, when
                # Normalize batch identifiers
                filt_df = batch_df \
                    .withColumn("sensor_norm", lower(trim(F.col("sensorId")))) \
                    .withColumn(
                        "ing_norm",
                        when(lower(trim(F.col("ingestion_id"))).isin("", "unknown"), F.lit(None))
                        .otherwise(lower(trim(F.col("ingestion_id"))))
                    )

                # Normalize allowed pairs
                norm_pairs = [
                    (
                        (sid or "").strip().lower(),
                        (None if (iid is None or str(iid).strip().lower() in ("", "unknown")) else str(iid).strip().lower())
                    )
                    for (sid, iid) in allowed_pairs
                ]
                allowed_ids_any = list({sid for (sid, iid) in norm_pairs if iid is None and sid})
                specific_pairs = [(sid, iid) for (sid, iid) in norm_pairs if iid is not None and sid]

                # Debug: log distinct ids in batch
                try:
                    batch_ids = [r[0] for r in filt_df.select("sensor_norm").distinct().limit(20).collect()]
                    batch_ing = [r[0] for r in filt_df.select("ing_norm").distinct().limit(20).collect()]
                    logger.info("Enrichment foreachBatch: batch sensors=%s; batch ingestions=%s; allowed_any=%s; allowed_pairs=%s",
                                batch_ids, batch_ing, allowed_ids_any, specific_pairs[:10])
                except Exception:
                    pass

                filtered_any = None
                if allowed_ids_any:
                    filtered_any = filt_df.where(F.col("sensor_norm").isin(allowed_ids_any))

                filtered_specific = None
                if specific_pairs:
                    allowed_df = batch_df.sparkSession.createDataFrame(specific_pairs, ["sensor_norm", "ing_norm"]).dropDuplicates()
                    filtered_specific = filt_df.join(allowed_df, on=["sensor_norm", "ing_norm"], how="inner")

                # If ingestion_id is null in batch, allow sensor-only match against specific pairs
                sensor_only = None
                if specific_pairs:
                    specific_ids = list({sid for (sid, _iid) in specific_pairs})
                    sensor_only = filt_df.where((F.col("ing_norm").isNull()) & (F.col("sensor_norm").isin(specific_ids)))

                parts = [p for p in [filtered_any, filtered_specific, sensor_only] if p is not None]
                if parts:
                    filtered = parts[0]
                    for p in parts[1:]:
                        filtered = filtered.unionByName(p)
                    filtered = filtered.dropDuplicates(["sensor_norm", "event_time"])  # dedupe if overlap
                else:
                    try:
                        input_count = batch_df.count()
                    except Exception:
                        input_count = -1
                    logger.info("Enrichment foreachBatch: nothing matched after normalization (input=%s)", input_count)
                    return
                if filtered.rdd.isEmpty():
                    try:
                        input_count = batch_df.count()
                    except Exception:
                        input_count = -1
                    logger.info(
                        "Enrichment foreachBatch: no rows after filtering (input=%s, allowed=%d)",
                        input_count,
                        len(allowed_pairs),
                    )
                    return
                try:
                    kept = filtered.count()
                except Exception:
                    kept = -1
                (
                    filtered.drop("sensor_norm", "ing_norm").write
                    .format("delta")
                    .mode("append")
                    .option("path", self.enriched_path)
                    .option("mergeSchema", "true")
                    .save()
                )
                logger.info("Enrichment foreachBatch: wrote %s rows to enriched", kept)
            except Exception as e:
                logger.error(f"Error in foreachBatch write: {e}")

        try:
            self.enrich_query = (
                base_cols.writeStream
                .foreachBatch(write_if_registered)
                .option("checkpointLocation", f"s3a://{self.minio_bucket}/{SparkConfig.ENRICH_STREAM_CHECKPOINT}")
                .queryName(self.ENRICH_QUERY_NAME)
                .trigger(processingTime=SparkConfig.ENRICH_STREAM_TRIGGER)
                .start()
            )
        except Exception as e:
            # If concurrent start detected, bind to the existing one
            if "SparkConcurrentModificationException" in str(e) or "CONCURRENT_QUERY" in str(e):
                logger.warning("Concurrent start detected for enrichment stream; reusing active query")
                existing = self._get_query_by_name(self.ENRICH_QUERY_NAME)
                if existing and existing.isActive:
                    self.enrich_query = existing
                    return
            # Re-raise if it's another kind of error
            raise

    def stop_streams(self) -> None:
        """Stop all streaming queries gracefully."""
        streams = [
            ("Enrichment stream", self.enrich_query),
            ("Temperature stream", self.avg_query),
            ("Alert stream", self.alert_query)
        ]

        for stream_name, query in streams:
            try:
                if query and query.isActive:
                    query.stop()
                    logger.info(f"{stream_name} stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping {stream_name.lower()}: {e}")

        # Reset queries
        self.enrich_query = None
        self.avg_query = None
        self.alert_query = None
