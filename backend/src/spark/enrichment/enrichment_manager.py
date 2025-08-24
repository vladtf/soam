"""
Main enrichment manager for Spark streaming enrichment processes.
"""
import logging
import time
from typing import Optional
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.streaming import StreamingQuery

from .cleaner import DataCleaner
from ..config import SparkConfig, SparkSchemas
from .batch_processor import BatchProcessor

logger = logging.getLogger(__name__)


class EnrichmentManager:
    """Manages Spark enrichment streaming processes."""

    def __init__(self, spark: SparkSession, minio_bucket: str, bronze_path: str, enriched_path: str):
        """Initialize the enrichment manager.
        
        Args:
            spark: Spark session
            minio_bucket: MinIO bucket name
            bronze_path: Path to bronze layer data
            enriched_path: Path to enriched layer data
        """
        self.spark = spark
        self.minio_bucket = minio_bucket
        self.bronze_path = bronze_path
        self.enriched_path = enriched_path
        self.batch_processor = BatchProcessor(enriched_path)
        
        # Query management
        self.ENRICH_QUERY_NAME = "enrich_stream"
        self.enrich_query: Optional[StreamingQuery] = None

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

    def _get_streaming_schema(self) -> any:
        """Get the schema for streaming reads with optimized comprehensive analysis.
        
        Returns:
            Spark schema for reading streaming data
        """
        try:
            # Strategy: Use Spark's built-in schema merging but limit the scope for speed
            # This is much faster than sampling data but still catches schema variations
            
            # First, try to get a representative sample of partitions
            # Instead of reading ALL partitions, read a strategic sample
            try:
                # Read with mergeSchema but limit to recent partitions for speed
                # This captures schema evolution while being fast
                static_df = (
                    self.spark.read
                    .option("basePath", self.bronze_path)
                    .option("mergeSchema", "true")
                    .option("pathGlobFilter", "*/date=*/hour=*")  # Ensure partition pattern
                    .parquet(f"{self.bronze_path}ingestion_id=*/date=*/hour=*")
                )
                
                # Quick schema validation without expensive data sampling
                inferred_schema = static_df.schema
                schema_field_names = [field.name for field in inferred_schema.fields]

                logger.info(f"Fast schema inference: {len(schema_field_names)} fields found. Schema fields: {schema_field_names}")
                
                # Essential field check (quick validation)
                essential_fields = ["ingestion_id", "timestamp"]
                has_essential = all(field in schema_field_names for field in essential_fields)
                
                if has_essential:
                    # Schema looks good, do minimal verification
                    logger.info("Schema validation passed - using inferred schema")
                    return inferred_schema
                else:
                    logger.warning(f"Schema validation failed: has_essential={has_essential}, field_count={len(schema_field_names)}")
                    
            except Exception as e:
                logger.warning(f"Optimized schema inference failed: {e}")
            
            # Fallback: If fast approach fails, use comprehensive schema
            logger.info("Using comprehensive schema as fallback for reliability")
            return SparkSchemas.get_comprehensive_raw_schema()
                
        except Exception as e:
            logger.error(f"Schema inference completely failed: {e}")
            logger.info("Using comprehensive raw schema as final fallback")
            return SparkSchemas.get_comprehensive_raw_schema()

    def _create_raw_stream(self, schema) -> DataFrame:
        """Create raw streaming DataFrame.
        
        Args:
            schema: Schema to use for reading
            
        Returns:
            Raw streaming DataFrame
        """
        # Read raw parquet with schema
        raw_stream = (
            self.spark.readStream
            .schema(schema)
            .option("basePath", self.bronze_path)
            .option("maxFilesPerTrigger", SparkConfig.MAX_FILES_PER_TRIGGER)
            .parquet(f"{self.bronze_path}ingestion_id=*/date=*/hour=*")
        )

        # Add debug logging to see what's in the raw stream before any processing
        logger.info("Raw stream created successfully")
        try:
            logger.info(f"Raw stream columns ({len(raw_stream.columns)}): {raw_stream.columns}")
            
            # Log schema details
            schema_details = []
            for field in raw_stream.schema.fields:
                schema_details.append(f"{field.name}({field.dataType.simpleString()})")
            logger.info(f"Raw stream schema details: {schema_details}")
        except Exception as e:
            logger.warning(f"Could not log raw stream details: {e}")

        return raw_stream

    def _transform_to_union_schema(self, raw_stream: DataFrame) -> DataFrame:
        """Transform raw stream to union schema with normalization.
        
        Args:
            raw_stream: Raw streaming DataFrame
            
        Returns:
            Union schema DataFrame
        """
        cleaner = DataCleaner()
        
        # Transform to union schema with normalization
        union_stream = cleaner.normalize_to_union_schema(raw_stream, ingestion_id=None)

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
        """
        # Stop existing query
        self._stop_existing_query()

        # Get streaming schema
        schema = self._get_streaming_schema()
        
        # Create raw stream
        raw_stream = self._create_raw_stream(schema)
        
        # Transform to union schema
        union_stream = self._transform_to_union_schema(raw_stream)
        
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
        """Ensure enrichment stream is running, start it if not."""
        try:
            if self.enrich_query is None or not self.enrich_query.isActive:
                logger.info("Enrichment stream not active, attempting to start...")
                existing = self._get_query_by_name(self.ENRICH_QUERY_NAME)
                if existing and existing.isActive:
                    self.enrich_query = existing
                else:
                    self.start_enrichment_stream()
        except Exception as e:
            logger.error(f"Error ensuring enrichment stream is running: {e}")

    def stop_enrichment_stream(self) -> None:
        """Stop enrichment stream gracefully."""
        try:
            if self.enrich_query and self.enrich_query.isActive:
                self.enrich_query.stop()
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
