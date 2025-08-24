"""
Main enrichment manager for Spark streaming enrichment processes.
"""
import logging
import time
from typing import Optional, List
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.streaming import StreamingQuery
from pyspark.sql.types import StructType

from .cleaner import DataCleaner
from ..config import SparkConfig, SparkSchemas
from .batch_processor import BatchProcessor

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
        self.ENRICH_QUERY_NAME: str = "enrich_stream"
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

    def _get_streaming_schema(self) -> StructType:
        """Get the schema for streaming reads with robust dynamic analysis.
        
        Returns:
            Spark schema for reading streaming data
            
        Raises:
            Exception: If no data is available for schema inference
        """
        logger.info(f"Starting dynamic schema inference from path: {self.bronze_path}")
        
        # Check if any data exists first
        if not self._has_bronze_data():
            raise Exception("No data available in bronze layer for schema inference. Please ensure data ingestion is working.")
        
        # Try multiple strategies for schema inference
        schema = None
        
        # Strategy 1: Try with mergeSchema on all available data
        schema = self._try_merge_schema_inference()
        if schema:
            return schema
            
        # Strategy 2: Try with single partition if merge fails
        schema = self._try_single_partition_inference()
        if schema:
            return schema
            
        # Strategy 3: Try with specific ingestion_id patterns
        schema = self._try_ingestion_specific_inference()
        if schema:
            return schema
            
        # If all strategies fail, this is a real issue that needs to be addressed
        raise Exception("Unable to infer schema from any available data. Check data format and structure in bronze layer.")

    def _has_bronze_data(self) -> bool:
        """Check if bronze layer contains any data."""
        try:
            logger.info(f"Checking for data in bronze layer: {self.bronze_path}")
            
            # Use Spark to check for data existence (works with S3, HDFS, local, etc.)
            try:
                # Try to read any parquet files - this will fail if no data exists
                df_check = self.spark.read.parquet(self.bronze_path)
                # Try to get the schema without reading data
                schema = df_check.schema
                if schema and len(schema.fields) > 0:
                    logger.info(f"Bronze layer data check: found data with {len(schema.fields)} fields")
                    return True
                else:
                    logger.info("Bronze layer data check: no valid schema found")
                    return False
                    
            except Exception as e:
                logger.debug(f"Direct parquet read failed: {e}")
                
                # Try with partition pattern
                try:
                    df_check = self.spark.read.parquet(f"{self.bronze_path}ingestion_id=*/*/*")
                    schema = df_check.schema
                    if schema and len(schema.fields) > 0:
                        logger.info(f"Bronze layer data check: found partitioned data with {len(schema.fields)} fields")
                        return True
                except Exception as e2:
                    logger.debug(f"Partitioned read failed: {e2}")
                    
                    # Try even more specific pattern
                    try:
                        df_check = self.spark.read.option("basePath", self.bronze_path).parquet(
                            f"{self.bronze_path}ingestion_id=*/date=*/hour=*"
                        )
                        schema = df_check.schema
                        if schema and len(schema.fields) > 0:
                            logger.info(f"Bronze layer data check: found hourly partitioned data with {len(schema.fields)} fields")
                            return True
                    except Exception as e3:
                        logger.debug(f"Hourly partitioned read failed: {e3}")
                
                logger.info("Bronze layer data check: no data found with any pattern")
                return False
                
        except Exception as e:
            logger.warning(f"Could not check bronze layer data existence: {e}")
            # If we can't check, assume data might exist and let schema inference handle it
            logger.info("Bronze layer data check: unknown (assuming data exists)")
            return True

    def _try_merge_schema_inference(self) -> Optional[StructType]:
        """Try schema inference with mergeSchema=true."""
        try:
            logger.info("Attempting schema inference with mergeSchema=true")
            static_df = (
                self.spark.read
                .option("basePath", self.bronze_path)
                .option("mergeSchema", "true")
                .parquet(f"{self.bronze_path}ingestion_id=*/date=*/hour=*")
            )
            
            schema = static_df.schema
            schema_field_names = [field.name for field in schema.fields]
            
            logger.info(f"Merge schema inference successful: {len(schema_field_names)} fields found")
            logger.info(f"Schema fields: {schema_field_names}")
            
            # Validate essential fields
            if self._validate_schema(schema):
                return schema
                
        except Exception as e:
            logger.warning(f"Merge schema inference failed: {e}")
        
        return None

    def _try_single_partition_inference(self) -> Optional[StructType]:
        """Try schema inference from a single partition."""
        try:
            logger.info("Attempting schema inference from single partition")
            
            # Try different partition patterns to find any available data
            patterns = [
                f"{self.bronze_path}ingestion_id=*/date=*/hour=*",
                f"{self.bronze_path}ingestion_id=*/*/*",
                f"{self.bronze_path}ingestion_id=*/*",
                f"{self.bronze_path}*/*/*",
                f"{self.bronze_path}*/*"
            ]
            
            for pattern in patterns:
                try:
                    logger.debug(f"Trying single partition pattern: {pattern}")
                    static_df = self.spark.read.parquet(pattern)
                    schema = static_df.schema
                    
                    if self._validate_schema(schema):
                        logger.info(f"Single partition inference successful with pattern: {pattern}")
                        schema_field_names = [field.name for field in schema.fields]
                        logger.info(f"Schema fields: {schema_field_names}")
                        return schema
                        
                except Exception as e:
                    logger.debug(f"Pattern {pattern} failed: {e}")
                    continue
                    
            # Last resort: try reading from base path
            try:
                logger.debug("Trying base path read as last resort")
                static_df = self.spark.read.parquet(self.bronze_path)
                schema = static_df.schema
                
                if self._validate_schema(schema):
                    logger.info("Single partition inference successful (base path method)")
                    return schema
                    
            except Exception as e:
                logger.debug(f"Base path read failed: {e}")
                
        except Exception as e:
            logger.warning(f"Single partition inference failed: {e}")
        
        return None

    def _try_ingestion_specific_inference(self) -> Optional[StructType]:
        """Try to infer schema from specific ingestion patterns."""
        try:
            logger.info("Attempting ingestion-specific schema inference")
            
            # Try different glob patterns that might exist
            patterns = [
                f"{self.bronze_path}ingestion_id=*/*/*",
                f"{self.bronze_path}*/*/*",
                f"{self.bronze_path}*/*",
                f"{self.bronze_path}*"
            ]
            
            for pattern in patterns:
                try:
                    logger.debug(f"Trying pattern: {pattern}")
                    static_df = self.spark.read.parquet(pattern)
                    schema = static_df.schema
                    
                    if self._validate_schema(schema):
                        logger.info(f"Ingestion-specific inference successful with pattern: {pattern}")
                        return schema
                        
                except Exception as e:
                    logger.debug(f"Pattern {pattern} failed: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Ingestion-specific inference failed: {e}")
            
        return None

    def _validate_schema(self, schema: StructType) -> bool:
        """Validate that the inferred schema has required fields."""
        if not schema or not schema.fields:
            return False
            
        schema_field_names: List[str] = [field.name for field in schema.fields]
        
        # Essential field check - only ingestion_id is truly required
        essential_fields: List[str] = ["ingestion_id"]
        has_essential: bool = all(field in schema_field_names for field in essential_fields)
        
        if not has_essential:
            logger.warning(f"Schema validation failed - missing essential fields. Found: {schema_field_names}")
            return False
            
        # Check for minimum reasonable field count (avoid empty schemas)
        if len(schema_field_names) < 2:  # At least ingestion_id + one data field
            logger.warning(f"Schema validation failed - too few fields: {len(schema_field_names)}")
            return False
            
        logger.info(f"Schema validation passed: {len(schema_field_names)} fields, essential fields present")
        return True

    def _create_raw_stream(self, schema: StructType) -> DataFrame:
        """Create raw streaming DataFrame.
        
        Args:
            schema: Schema to use for reading
            
        Returns:
            Raw streaming DataFrame
        """
        # Read raw parquet with schema
        raw_stream: DataFrame = (
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
            schema_details: List[str] = []
            for field in raw_stream.schema.fields:
                schema_details.append(f"{field.name}({field.dataType.simpleString()})")
            logger.info(f"Raw stream schema details: {schema_details}")
        except Exception as e:
            logger.warning(f"Could not log raw stream details: {e}")

        return raw_stream

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
        
        Raises:
            Exception: If schema inference fails due to no data or other issues
        """
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
