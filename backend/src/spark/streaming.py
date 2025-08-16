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
        """Initialize StreamingManager.

        Args:
            session_manager: Spark session manager
            minio_bucket: MinIO bucket name
        """
        self.session_manager = session_manager
        self.minio_bucket = minio_bucket

        # Build paths
        self.bronze_path = f"s3a://{minio_bucket}/{SparkConfig.BRONZE_PATH}/"
        # Silver layer paths
        self.enriched_path = f"s3a://{minio_bucket}/{SparkConfig.ENRICHED_PATH}/"
        # Gold layer paths
        self.gold_temp_avg_path = f"s3a://{minio_bucket}/{SparkConfig.GOLD_TEMP_AVG_PATH}/"
        self.gold_alerts_path = f"s3a://{minio_bucket}/{SparkConfig.GOLD_ALERTS_PATH}/"

        # Streaming queries
        self.avg_query: Optional[StreamingQuery] = None
        self.alert_query: Optional[StreamingQuery] = None
        # New: enrichment query
        self.enrich_query: Optional[StreamingQuery] = None

        # Query names (union schema is now default)
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
        """Check if the bronze data directory exists and is accessible."""
        try:
            # Try to access the bronze directory - even if empty, this will work
            self.session_manager.spark.read.option("basePath", self.bronze_path).option("recursiveFileLookup", "true").option("pathGlobFilter", "*.parquet").parquet(self.bronze_path)
            return True
        except Exception as e:
            # Check if it's just an empty directory (which is fine)
            if "Path does not exist" in str(e) or "Unable to infer schema" in str(e):
                logger.info(f"Bronze directory empty or doesn't exist yet - this is normal for initial startup: {e}")
                return False
            else:
                logger.debug(f"Data directory not ready: {e}")
                return False

    def start_streams_safely(self) -> None:
        """Start streaming jobs with error handling."""
        try:
            self.start_enrichment_stream()
            logger.info("Union enrichment stream started successfully")
        except Exception as e:
            logger.error(f"Failed to start enrichment stream: {e}")

        try:
            self.start_temperature_stream()
            logger.info("Union temperature streaming started successfully")
        except Exception as e:
            logger.error(f"Failed to start temperature stream: {e}")

        try:
            self.start_alert_stream()
            logger.info("Union alert streaming started successfully")
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
        """Start the temperature averaging stream from union schema enriched data."""
        spark = self.session_manager.spark

        # Read streaming data from enriched union delta
        try:
            enriched_stream = (
                spark.readStream
                .format("delta")
                .load(self.enriched_path)
            )
        except Exception as e:
            logger.info("Enriched union delta not available yet, skipping temperature stream start: %s", e)
            return

        # Extract temperature from union schema and filter valid values
        from .union_schema import UnionSchemaTransformer

        temp_stream = UnionSchemaTransformer.extract_column_from_union(
            enriched_stream, "temperature", prefer_normalized=True
        )

        # Extract sensorId from sensor_data map
        temp_stream = temp_stream.withColumn(
            "sensorId",
            F.coalesce(
                temp_stream.sensor_data.getItem("sensorId"),
                temp_stream.sensor_data.getItem("sensorid"),
                temp_stream.sensor_data.getItem("sensor_id"),
                temp_stream.ingestion_id  # fallback to ingestion_id
            )
        )

        # Filter valid temperature readings
        valid_temp_stream = (
            temp_stream
            .filter((F.col("temperature").isNotNull()) & (~F.isnan(F.col("temperature"))))
            .withWatermark("event_time", SparkConfig.WATERMARK_DELAY)
        )

        # Calculate sliding window averages
        five_min_avg = (
            valid_temp_stream
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

        # Ensure target Delta table exists in gold layer
        try:
            spark.read.format("delta").load(self.gold_temp_avg_path).limit(0)
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
                .save(self.gold_temp_avg_path)
            )

        # Write to Delta table in gold layer
        self.avg_query = (
            five_min_avg.writeStream
            .format("delta")
            .option("path", self.gold_temp_avg_path)
            .option("checkpointLocation", f"s3a://{self.minio_bucket}/{SparkConfig.GOLD_TEMP_AVG_CHECKPOINT}_union")
            .option("mergeSchema", "true")
            .outputMode("complete")
            .queryName(self.AVG_QUERY_NAME)
            .trigger(processingTime=SparkConfig.TEMPERATURE_STREAM_TRIGGER)
            .start()
        )

    def start_alert_stream(self) -> None:
        """Start the temperature alert stream from union schema enriched data."""
        spark = self.session_manager.spark

        # Read streaming data from enriched union delta
        try:
            enriched_stream = (
                spark.readStream
                .format("delta")
                .load(self.enriched_path)
            )
        except Exception as e:
            logger.info("Enriched union delta not available yet, skipping alert stream start: %s", e)
            return

        # Extract temperature and sensorId from union schema
        from .union_schema import UnionSchemaTransformer

        alert_stream = UnionSchemaTransformer.extract_column_from_union(
            enriched_stream, "temperature", prefer_normalized=True
        )

        alert_stream = alert_stream.withColumn(
            "sensorId",
            F.coalesce(
                alert_stream.sensor_data.getItem("sensorId"),
                alert_stream.sensor_data.getItem("sensorid"),
                alert_stream.sensor_data.getItem("sensor_id"),
                alert_stream.ingestion_id
            )
        )

        # Filter for temperature alerts
        alerts = (
            alert_stream
            .filter((F.col("temperature").isNotNull()) & (~F.isnan(F.col("temperature"))))
            .filter(F.col("temperature") > SparkConfig.TEMP_THRESHOLD)
            .withColumn("alert_type", F.lit("TEMP_OVER_LIMIT"))
            .withColumn("alert_id", F.concat(F.col("sensorId"), F.lit("_"), F.col("event_time")))
            .withColumn("alert_time", F.current_timestamp())
            .dropDuplicates(["sensorId"])
            .select("sensorId", "temperature", "event_time", "alert_type")
        )

        # Write to Delta table in gold layer
        self.alert_query = (
            alerts.writeStream
            .format("delta")
            .option("path", self.gold_alerts_path)
            .option("checkpointLocation", f"s3a://{self.minio_bucket}/{SparkConfig.GOLD_ALERT_CHECKPOINT}_union")
            .option("mergeSchema", "true")
            .outputMode("append")
            .queryName(self.ALERT_QUERY_NAME)
            .trigger(processingTime=SparkConfig.ALERT_STREAM_TRIGGER)
            .start()
        )

    def start_enrichment_stream(self) -> None:
        """Start enrichment stream with union schema for flexible data storage.

        This implementation provides:
        - Flexible sensor data storage as JSON strings
        - Normalized data as typed values for analytics
        - Ingestion-specific normalization rules
        - Raw data preservation for debugging
        """
        # Check for existing query and stop it if active
        existing_query = self._get_query_by_name(self.ENRICH_QUERY_NAME)
        if existing_query and existing_query.isActive:
            logger.info(f"Stopping existing enrichment query: {self.ENRICH_QUERY_NAME}")
            existing_query.stop()
            # Wait a moment for cleanup
            import time
            time.sleep(2)

        spark = self.session_manager.spark
        cleaner = DataCleaner()

        # Use comprehensive schema instead of inferring from possibly incomplete files
        try:
            # Try to infer schema from existing parquet files first
            static_df = (
                spark.read
                .option("basePath", self.bronze_path)
                .parquet(f"{self.bronze_path}ingestion_id=*/date=*/hour=*")
            )
            inferred_schema = static_df.schema
            logger.info("Inferred raw sensors schema from existing files for union streaming")
            
            # Check if the inferred schema has temperature field
            has_temperature = any(field.name == "temperature" for field in inferred_schema.fields)
            if not has_temperature:
                logger.warning("Inferred schema missing temperature field - using comprehensive schema")
                from .config import SparkSchemas
                inferred_schema = SparkSchemas.get_comprehensive_raw_schema()

        except Exception as e:
            from .config import SparkSchemas
            inferred_schema = SparkSchemas.get_comprehensive_raw_schema()
            logger.info(f"Using comprehensive raw schema for streaming read (reason: {e})")

        # Read raw parquet with schema
        raw_stream = (
            spark.readStream
            .schema(inferred_schema)
            .option("basePath", self.bronze_path)
            .option("maxFilesPerTrigger", SparkConfig.MAX_FILES_PER_TRIGGER)
            .parquet(f"{self.bronze_path}ingestion_id=*/date=*/hour=*")
        )

        # Add debug logging to see what's in the raw stream before any processing
        logger.info("Raw stream schema before any processing:")
        try:
            logger.info(f"Raw stream columns: {raw_stream.columns}")
            # Check specifically for temperature field
            has_temp_field = "temperature" in raw_stream.columns
            logger.info(f"Raw stream has temperature field: {has_temp_field}")
            logger.info(f"Raw stream schema: {raw_stream.schema}")
        except Exception as e:
            logger.warning(f"Could not log raw stream schema: {e}")

        # Transform to union schema with normalization
        union_stream = cleaner.normalize_to_union_schema(raw_stream, ingestion_id=None)

        # Add debug logging to see what's in the union stream
        logger.info("Union stream schema after normalization:")
        try:
            logger.info(f"Union stream columns: {union_stream.columns}")
        except Exception as e:
            logger.warning(f"Could not log union stream columns: {e}")

        # Add enrichment metadata
        enriched_union = (
            union_stream
            .withColumn("event_time", F.col("timestamp"))
            .withColumn("ingest_ts", F.current_timestamp())
            .withColumn("ingest_date", F.to_date(F.col("timestamp")))
            .withColumn("ingest_hour", F.date_format(F.col("timestamp"), "HH"))
            .withColumn("source", F.lit("mqtt"))
            .withColumn("site", F.lit("default"))
        )

        # Ensure target enriched Delta table exists with union schema
        try:
            spark.read.format("delta").load(self.enriched_path).limit(0)
        except Exception:
            from .config import SparkSchemas
            from .union_schema import create_empty_enriched_union_dataframe
            empty_enriched = create_empty_enriched_union_dataframe(spark)
            (
                empty_enriched.write
                .format("delta")
                .mode("ignore")
                .option("overwriteSchema", "true")
                .save(self.enriched_path)
            )

        # Filter and write with device registration check
        def write_union_if_registered(batch_df, batch_id: int):
            try:
                logger.info("Union enrichment batch started: batch_id=%s", batch_id)

                # Debug: Log sample raw data BEFORE any processing
                if not batch_df.rdd.isEmpty():
                    logger.info("=== RAW BATCH DATA SAMPLE ===")
                    raw_sample = batch_df.limit(2).collect()
                    for i, row in enumerate(raw_sample):
                        row_dict = row.asDict()
                        logger.info(f"Raw data sample {i+1}: {row_dict}")
                        # Specifically check temperature field in raw data
                        if 'temperature' in row_dict:
                            logger.info(f"Raw data sample {i+1}: temperature = '{row_dict['temperature']}' (type: {type(row_dict['temperature'])})")
                    logger.info("=== END RAW BATCH DATA SAMPLE ===")

                from sqlalchemy.orm import sessionmaker
                from src.database.database import engine
                from src.database.models import Device
                SessionLocal = sessionmaker(bind=engine)
                session = SessionLocal()

                try:
                    # Get allowed ingestion IDs
                    rows = session.query(Device.ingestion_id).filter(Device.enabled == True).all()
                    allowed_ing = [r[0] for r in rows]
                    logger.info("Union enrichment: registered ingestion_ids: %s", allowed_ing)
                finally:
                    session.close()

                # Check for wildcard registration (None ingestion_id means accept all)
                has_wildcard = any(iid is None for iid in allowed_ing)

                # Filter by allowed ingestion IDs
                norm_allowed = {
                    str(iid).strip().lower()
                    for iid in allowed_ing
                    if iid is not None and str(iid).strip().lower() not in ("", "unknown")
                }

                logger.info("Union enrichment: normalized allowed IDs: %s", norm_allowed)
                logger.info("Union enrichment: has wildcard registration: %s", has_wildcard)

                if not norm_allowed and not has_wildcard:
                    logger.info("Union enrichment: no allowed ingestion IDs and no wildcard; skipping")
                    return

                # If wildcard registration exists, accept all data
                if has_wildcard:
                    filtered = batch_df
                    logger.info("Union enrichment: wildcard registration - accepting all data")
                else:
                    # Apply filter for specific ingestion IDs
                    filtered = batch_df.filter(
                        F.lower(F.trim(F.col("ingestion_id"))).isin(list(norm_allowed))
                    )

                if filtered.rdd.isEmpty():
                    logger.info("Union enrichment: no rows after filtering - skipping write to avoid empty parquet files")
                    return

                # Debug: Log sample of ingestion_ids in the batch
                if "ingestion_id" in batch_df.columns:
                    sample_ids = [r[0] for r in batch_df.select("ingestion_id").distinct().limit(5).collect()]
                    logger.info("Union enrichment: sample ingestion_ids in batch: %s", sample_ids)

                # Additional debug: count before and after filtering
                total_before = batch_df.count()
                total_after = filtered.count()
                logger.info("Union enrichment: %d rows before filter, %d rows after filter", total_before, total_after)

                # Log normalized field information for debugging
                if total_after > 0:
                    try:
                        # Sample normalized data to show what fields and values are being processed
                        sample_rows = filtered.select("ingestion_id", "normalized_data", "sensor_data").limit(3).collect()
                        for i, row in enumerate(sample_rows):
                            ingestion_id = row["ingestion_id"]
                            normalized_data = row["normalized_data"]
                            sensor_data = row["sensor_data"]

                            logger.info("Union enrichment sample %d: ingestion_id=%s", i+1, ingestion_id)

                            # Log normalized fields and values
                            if normalized_data:
                                # normalized_data is already a dict, not a Row object
                                norm_fields = [f"{k}={v}" for k, v in normalized_data.items() if v is not None]
                                logger.info("Union enrichment sample %d: normalized fields: %s", i+1, norm_fields)
                            else:
                                logger.info("Union enrichment sample %d: no normalized data", i+1)

                            # Log sensor data keys for context
                            if sensor_data:
                                # sensor_data is already a dict, not a Row object
                                sensor_keys = list(sensor_data.keys())
                                # Also show some actual sensor data values
                                sensor_sample = {k: v for k, v in sensor_data.items() if k in ['sensorId', 'temperature', 'humidity', 'timestamp']}
                                logger.info("Union enrichment sample %d: sensor_data keys: %s", i+1, sensor_keys)
                                logger.info("Union enrichment sample %d: sensor_data sample: %s", i+1, sensor_sample)
                            else:
                                logger.info("Union enrichment sample %d: no sensor data", i+1)

                    except Exception as e:
                        logger.warning(f"Union enrichment: Could not log sample normalized data: {e}")

                # If we expected filtering but nothing was filtered out, there might be a data mismatch
                if not has_wildcard and norm_allowed and total_before > 0 and total_after == total_before:
                    logger.warning("Union enrichment: Expected filtering but no rows were filtered out - possible ingestion_id mismatch")
                elif not has_wildcard and norm_allowed and total_after == 0:
                    logger.warning("Union enrichment: All rows filtered out - ingestion_id mismatch between registered devices and incoming data")

                # Write to Delta
                (
                    filtered.write
                    .format("delta")
                    .mode("append")
                    .option("path", self.enriched_path)
                    .option("mergeSchema", "true")
                    .save()
                )

                kept = filtered.count()
                logger.info("Union enrichment: wrote %d rows to enriched", kept)

            except Exception as e:
                logger.error(f"Error in union enrichment foreachBatch: {e}")

        # Start the streaming query with error handling
        try:
            self.enrich_query = (
                enriched_union.writeStream
                .foreachBatch(write_union_if_registered)
                .option("checkpointLocation", f"s3a://{self.minio_bucket}/{SparkConfig.ENRICH_STREAM_CHECKPOINT}")
                .queryName(self.ENRICH_QUERY_NAME)
                .trigger(processingTime=SparkConfig.ENRICH_STREAM_TRIGGER)
                .start()
            )
            logger.info(f"Started enrichment stream with query name: {self.ENRICH_QUERY_NAME}")
        except Exception as e:
            # Handle case where query with same name already exists
            if "already active" in str(e) or "Cannot start query with name" in str(e):
                logger.warning(f"Query {self.ENRICH_QUERY_NAME} already exists, attempting to reuse existing query")
                existing = self._get_query_by_name(self.ENRICH_QUERY_NAME)
                if existing and existing.isActive:
                    self.enrich_query = existing
                    logger.info(f"Reusing existing enrichment query: {self.ENRICH_QUERY_NAME}")
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
