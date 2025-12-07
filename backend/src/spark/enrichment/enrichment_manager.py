"""
Main enrichment manager for Spark streaming enrichment processes.
"""
import logging
import time
import threading
from typing import Optional, List
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.streaming import StreamingQuery
from pyspark.sql.types import StructType, StructField
from pyspark.sql.types import IntegerType, LongType, DoubleType, FloatType, StringType, TimestampType

from .cleaner import DataCleaner
from ..config import SparkConfig, SparkSchemas
from .batch_processor import BatchProcessor
from ...utils.logging import log_execution_time
from ...services.ingestor_schema_client import IngestorSchemaClient

logger = logging.getLogger(__name__)


class EnrichmentManager:
    """Manages Spark enrichment streaming processes."""

    def __init__(self, spark: SparkSession, minio_bucket: str, bronze_path: str, enriched_path: str) -> None:
        """Initialize the enrichment manager.
        
        Args:
            spark: Spark session
            minio_bucket: MinIO bucket name
            bronze_path: Path to bronze layer data
            enriched_path: Path to enriched layer data
        """
        self.spark: SparkSession = spark
        self.minio_bucket: str = minio_bucket
        self.bronze_path: str = bronze_path
        self.enriched_path: str = enriched_path
        self.batch_processor: BatchProcessor = BatchProcessor(enriched_path)
        
        # Query management
        self.ENRICH_QUERY_NAME: str = "sensor_data_enrichment"
        self.enrich_query: Optional[StreamingQuery] = None
        
        # Thread lock to prevent concurrent stream starts
        self._enrich_query_lock = threading.Lock()
        
        # Ingestor schema client for fast schema retrieval
        self.ingestor_client: IngestorSchemaClient = IngestorSchemaClient()

    def _get_query_by_name(self, name: str) -> Optional[StreamingQuery]:
        """Return active StreamingQuery by name if present.
        
        Args:
            name: Query name to search for
            
        Returns:
            StreamingQuery if found and active, None otherwise
        """
        try:
            for q in self.spark.streams.active:
                try:
                    if q.name == name:
                        return q
                except Exception:
                    continue
        except Exception:
            return None
        return None

    def _stop_existing_query(self) -> None:
        """Stop existing enrichment query if active."""
        existing_query = self._get_query_by_name(self.ENRICH_QUERY_NAME)
        if existing_query and existing_query.isActive:
            logger.info(f"Stopping existing enrichment query: {self.ENRICH_QUERY_NAME}")
            existing_query.stop()
            # Wait a moment for cleanup
            time.sleep(2)

    @log_execution_time(operation_name="Streaming Schema Retrieval")
    def _get_streaming_schema(self) -> StructType:
        """Get the schema for streaming reads from ingestor's pre-computed metadata.
        
        Returns:
            Spark schema for reading streaming data
            
        Raises:
            Exception: If no schema is available from ingestor
        """
        logger.info(f"🔍 Fetching schema for streaming from ingestor...")
        
        schema = self._try_ingestor_schema()
        if schema:
            logger.info(f"✅ Using ingestor schema with {len(schema.fields)} fields")
            return schema
        
        raise Exception("No schema available from ingestor. Please ensure data has been ingested and metadata is available.")

    def _try_ingestor_schema(self) -> Optional[StructType]:
        """Try to get schema from ingestor's pre-computed metadata.
        
        Returns:
            Spark StructType from ingestor, or None if unavailable
        """
        try:
            schema = self.ingestor_client.get_merged_spark_schema_sync()
            if schema and self._validate_schema(schema):
                logger.info(f"✅ Ingestor schema validation passed: {len(schema.fields)} fields")
                return schema
            elif schema:
                logger.warning("⚠️ Ingestor schema validation failed")
                return None
            else:
                logger.info("ℹ️ No schema available from ingestor")
                return None
        except Exception as e:
            logger.warning(f"⚠️ Could not fetch schema from ingestor: {e}")
            return None

    def _validate_schema(self, schema: StructType) -> bool:
        """Validate that the schema has required fields."""
        if not schema or not schema.fields:
            logger.warning("❌ Schema validation failed - no schema or fields found")
            return False
            
        schema_field_names: List[str] = [field.name for field in schema.fields]
        
        # Essential field check - only ingestion_id is truly required
        essential_fields: List[str] = ["ingestion_id"]
        has_essential: bool = all(field in schema_field_names for field in essential_fields)
        
        if not has_essential:
            logger.warning(f"❌ Schema validation failed - missing essential fields. Found: {schema_field_names}")
            return False
            
        # Check for minimum reasonable field count (avoid empty schemas)
        if len(schema_field_names) < 2:  # At least ingestion_id + one data field
            logger.warning(f"❌ Schema validation failed - too few fields: {len(schema_field_names)}")
            return False
            
        logger.info(f"✅ Schema validation passed: {len(schema_field_names)} fields, essential fields present")
        return True

    @log_execution_time(operation_name="Bronze Layer Statistics")
    def get_bronze_layer_stats(self) -> dict:
        """Get statistics about bronze layer for monitoring and debugging.
        
        Returns:
            Dictionary with bronze layer statistics
        """
        try:
            pattern = f"{self.bronze_path}ingestion_id=*/date=*/hour=*"
            
            # Read all files to get statistics
            all_files_df = (
                self.spark.read
                .option("basePath", self.bronze_path)
                .parquet(pattern)
            )
            
            # Get basic statistics
            total_records = all_files_df.count()
            unique_ingestion_ids = all_files_df.select("ingestion_id").distinct().count()
            
            # Get file count per ingestion_id
            files_per_ingestion = (
                all_files_df
                .withColumn("input_file", F.input_file_name())
                .select("ingestion_id", "input_file")
                .distinct()
                .groupBy("ingestion_id")
                .count()
                .collect()
            )
            
            stats = {
                "total_records": total_records,
                "unique_ingestion_ids": unique_ingestion_ids,
                "files_per_ingestion": {row.ingestion_id: row.count for row in files_per_ingestion},
                "pattern_used": pattern
            }
            
            logger.info(f"📊 Bronze layer stats: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error getting bronze layer stats: {e}")
            return {
                "error": str(e),
                "total_records": 0,
                "unique_ingestion_ids": 0,
                "files_per_ingestion": {},
                "pattern_used": pattern
            }

    def _create_raw_stream(self, schema: StructType) -> DataFrame:
        """Create raw streaming DataFrame using the provided schema.
        
        Args:
            schema: Schema inferred from existing files (required for streaming)
            
        Returns:
            Raw streaming DataFrame
        """
        stream_path = f"{self.bronze_path}ingestion_id=*/date=*/hour=*"
        logger.debug(f"🔍 Creating raw stream from path: {stream_path}")
        logger.debug(f"🔍 Bronze base path: {self.bronze_path}")
        logger.debug(f"🔍 Using schema with {len(schema.fields)} fields")
        
        # Spark Structured Streaming requires a schema to be specified.
        # We use the schema inferred from existing files.
        # The ingestor now writes all numeric types as float64 (double) for consistency.
        raw_stream: DataFrame = (
            self.spark.readStream
            .schema(schema)
            .option("basePath", self.bronze_path)
            .option("maxFilesPerTrigger", SparkConfig.MAX_FILES_PER_TRIGGER)
            .parquet(stream_path)
        )
        
        logger.info("✅ Raw stream created with inferred schema")
        
        # Add debug logging
        try:
            logger.debug(f"Raw stream columns ({len(raw_stream.columns)}): {raw_stream.columns}")
            schema_details: List[str] = []
            for field in raw_stream.schema.fields:
                schema_details.append(f"{field.name}({field.dataType.simpleString()})")
            logger.info(f"Raw stream schema details: {schema_details}")
        except Exception as e:
            logger.warning(f"Could not log raw stream details: {e}")

        return raw_stream

    def _create_flexible_schema(self, resolved_schema: StructType) -> StructType:
        """Create a flexible schema that can accommodate type variations.
        
        Since data comes from multiple sources (MQTT, REST API) with potentially different
        types for the same fields (int vs double, timestamp vs string), we read all
        potentially problematic fields as StringType for maximum compatibility.
        
        Type conversion is handled later in the normalization/transformation phase.
        
        Args:
            resolved_schema: The schema with resolved type conflicts
            
        Returns:
            Flexible schema that can read files with different types
        """
        flexible_fields = []
        
        for field in resolved_schema.fields:
            # Convert all numeric and timestamp fields to StringType for maximum flexibility
            # This handles: int vs double, timestamp vs string, long vs int, etc.
            if isinstance(field.dataType, (IntegerType, LongType, DoubleType, FloatType, TimestampType)):
                flexible_field = StructField(field.name, StringType(), nullable=True)
                flexible_fields.append(flexible_field)
                logger.debug(f"🔄 Converted field '{field.name}': {field.dataType} -> StringType")
            else:
                # Keep other fields as they are (StringType, ArrayType, MapType, etc.)
                flexible_fields.append(field)
        
        flexible_schema = StructType(flexible_fields)
        logger.info(f"✅ Created flexible schema with {len(flexible_fields)} fields (all numeric/timestamp as String)")
        return flexible_schema

    def _transform_to_union_schema(self, raw_stream: DataFrame, schema: StructType) -> DataFrame:
        """Transform raw stream to union schema with normalization.
        
        Args:
            raw_stream: Raw streaming DataFrame
            schema: The schema used for the raw stream (for optimization)
            
        Returns:
            Union schema DataFrame
        """
        cleaner: DataCleaner = DataCleaner()
        
        # Transform to union schema with normalization
        # Pass schema information to avoid redundant schema inference
        # Use the actual ingestion_id column if present
        ingestion_id_col: Optional[str] = "ingestion_id" if "ingestion_id" in raw_stream.columns else None
        union_stream: DataFrame = cleaner.normalize_to_union_schema(raw_stream, ingestion_id=ingestion_id_col, schema=schema)

        # Add debug logging to see what's in the union stream
        logger.info("Union stream schema after normalization:")
        try:
            logger.info(f"Union stream columns: {union_stream.columns}")
        except Exception as e:
            logger.warning(f"Could not log union stream columns: {e}")

        return union_stream

    def _add_enrichment_metadata(self, union_stream: DataFrame) -> DataFrame:
        """Add enrichment metadata to union stream.
        
        Args:
            union_stream: Union schema DataFrame
            
        Returns:
            Enriched DataFrame with metadata
        """
        return (
            union_stream
            .withColumn("event_time", F.col("timestamp"))
            .withColumn("ingest_ts", F.current_timestamp())
            .withColumn("ingest_date", F.to_date(F.col("timestamp")))
            .withColumn("ingest_hour", F.date_format(F.col("timestamp"), "HH"))
            .withColumn("source", F.lit("mqtt"))
            .withColumn("site", F.lit("default"))
        )

    def _ensure_target_table_exists(self) -> None:
        """Ensure target enriched Delta table exists with union schema and partitioning."""
        try:
            self.spark.read.format("delta").load(self.enriched_path).limit(0)
        except Exception:
            from .union_schema import create_empty_enriched_union_dataframe
            empty_enriched = create_empty_enriched_union_dataframe(self.spark)
            (
                empty_enriched.write
                .format("delta")
                .mode("ignore")
                .option("overwriteSchema", "true")
                .partitionBy("ingestion_id")  # Partition by ingestion_id
                .save(self.enriched_path)
            )

    def start_enrichment_stream(self) -> None:
        """Start enrichment stream with union schema for flexible data storage.

        This implementation provides:
        - Flexible sensor data storage as JSON strings
        - Normalized data as typed values for analytics
        - Ingestion-specific normalization rules
        - Raw data preservation for debugging
        
        Should be called with _enrich_query_lock held to prevent concurrent starts.
        
        Raises:
            Exception: If schema inference fails due to no data or other issues
        """
        # Double-check that query isn't already running
        existing = self._get_query_by_name(self.ENRICH_QUERY_NAME)
        if existing and existing.isActive:
            logger.info(f"Enrichment stream already running, reusing existing query")
            self.enrich_query = existing
            return
        
        # Stop existing query
        self._stop_existing_query()

        try:
            # Get streaming schema - this will fail fast if no data is available
            schema: StructType = self._get_streaming_schema()
            logger.info(f"Successfully inferred schema with {len(schema.fields)} fields")
            
        except Exception as e:
            logger.error(f"Cannot start enrichment stream - schema inference failed: {e}")
            logger.error("Possible solutions:")
            logger.error("1. Check if data ingestion is working and data exists in bronze layer")
            logger.error("2. Verify bronze layer path is correct: %s", self.bronze_path)
            logger.error("3. Check if Spark can access the storage location")
            logger.error("4. Ensure at least one device is sending data")
            raise Exception(f"Enrichment stream startup failed: {e}")
        
        # Create raw stream
        raw_stream = self._create_raw_stream(schema)
        
        # Transform to union schema
        union_stream = self._transform_to_union_schema(raw_stream, schema)
        
        # Add enrichment metadata
        enriched_union = self._add_enrichment_metadata(union_stream)

        # Ensure target enriched Delta table exists
        self._ensure_target_table_exists()

        # Start the streaming query with error handling
        try:
            self.enrich_query = (
                enriched_union.writeStream
                .foreachBatch(self.batch_processor.process_batch)
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

    def ensure_enrichment_running(self) -> None:
        """Ensure enrichment stream is running, start it if not.
        
        Thread-safe: Uses lock to prevent concurrent stream starts.
        """
        with self._enrich_query_lock:
            try:
                if self.enrich_query is None or not self.enrich_query.isActive:
                    logger.info("Enrichment stream not active, attempting to start...")
                    existing = self._get_query_by_name(self.ENRICH_QUERY_NAME)
                    if existing and existing.isActive:
                        self.enrich_query = existing
                        logger.info("Reattached to existing enrichment stream")
                    else:
                        self.start_enrichment_stream()
            except Exception as e:
                logger.error(f"Error ensuring enrichment stream is running: {e}")

    def stop_enrichment_stream(self) -> None:
        """Stop enrichment stream gracefully."""
        try:
            if self.enrich_query and self.enrich_query.isActive:
                logger.info("Gracefully stopping enrichment stream...")
                self.enrich_query.stop()
                
                # Wait for graceful shutdown with timeout
                max_wait_seconds = 30
                waited = 0
                while self.enrich_query.isActive and waited < max_wait_seconds:
                    time.sleep(1)
                    waited += 1
                
                if self.enrich_query.isActive:
                    logger.warning(f"Enrichment stream did not stop gracefully within {max_wait_seconds}s")
                else:
                    logger.info("Enrichment stream stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping enrichment stream: {e}")

        # Reset query
        self.enrich_query = None

    def is_enrichment_active(self) -> bool:
        """Check if enrichment stream is currently active.
        
        Returns:
            True if enrichment stream is active, False otherwise
        """
        return self.enrich_query is not None and self.enrich_query.isActive
