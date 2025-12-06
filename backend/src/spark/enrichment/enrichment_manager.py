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
from pyspark.sql.types import StructType, StructField, DataType
from pyspark.sql.types import IntegerType, LongType, DoubleType, FloatType, StringType, BooleanType

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

    @log_execution_time(operation_name="Streaming Schema Inference")
    def _get_streaming_schema(self) -> StructType:
        """Get the schema for streaming reads with optimized inference.
        
        Uses a two-tier approach:
        1. First, try to get pre-computed schema from ingestor (fast)
        2. Fall back to Spark schema inference from parquet files (slow)
        
        Returns:
            Spark schema for reading streaming data
            
        Raises:
            Exception: If no data is available for schema inference
        """
        logger.info(f"🔍 Starting schema inference from path: {self.bronze_path}")
        
        # Try 1: Get pre-computed schema from ingestor (fast path)
        logger.info("🚀 Attempting fast schema retrieval from ingestor...")
        ingestor_schema = self._try_ingestor_schema()
        if ingestor_schema:
            logger.info(f"✅ Using ingestor schema with {len(ingestor_schema.fields)} fields")
            return ingestor_schema
        
        logger.info("⚠️ Ingestor schema not available, falling back to Spark inference...")
        
        # Check if any data exists first
        if not self._has_bronze_data():
            raise Exception("No data available in bronze layer for schema inference. Please ensure data ingestion is working.")
        
        # Try 2: Spark schema inference from parquet files (slow path)
        schema = self._try_schema_inference()
        if schema:
            return schema
            
        # If inference fails, this is a real issue that needs to be addressed
        raise Exception("Unable to infer schema from any available data. Check data format and structure in bronze layer.")

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

    @log_execution_time(operation_name="Bronze Data Check")
    def _has_bronze_data(self) -> bool:
        """Check if bronze layer contains any data using the optimized pattern."""
        try:
            logger.info(f"Checking for data in bronze layer: {self.bronze_path}")
            
            # Use only the specific pattern we want for optimization
            pattern = f"{self.bronze_path}ingestion_id=*/date=*/hour=*"
            
            try:
                df_check = self.spark.read.option("basePath", self.bronze_path).parquet(pattern)
                schema = df_check.schema
                if schema and len(schema.fields) > 0:
                    logger.info(f"✅ Bronze layer data check: found hourly partitioned data with {len(schema.fields)} fields")
                    return True
                else:
                    logger.info("❌ Bronze layer data check: no valid schema found")
                    return False
            except Exception as e:
                logger.debug(f"❌ Hourly partitioned read failed: {e}")
                logger.info("❌ Bronze layer data check: no data found with required pattern")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ Could not check bronze layer data existence: {e}")
            # If we can't check, assume data might exist and let schema inference handle it
            logger.info("🔍 Bronze layer data check: unknown (assuming data exists)")
            return True

    @log_execution_time(operation_name="Schema Inference from Latest Files")
    def _try_schema_inference(self) -> Optional[StructType]:
        """Try schema inference using only latest files for each ingestion_id with type conflict resolution."""
        logger.info("🔍 Starting optimized schema inference with type conflict resolution")
        
        # Use only the specific pattern for optimization
        pattern = f"{self.bronze_path}ingestion_id=*/date=*/hour=*"
        
        try:
            logger.debug(f"📂 Using pattern: {pattern}")
            
            # First, get all files with the pattern to find latest for each ingestion_id
            # Use individual file reading to avoid schema merge conflicts during discovery
            all_files_df = self._read_files_without_merge(pattern)
            
            if all_files_df is None:
                logger.warning("⚠️ No files found with the specified pattern")
                return None
            
            # Get file metadata to find latest files per ingestion_id
            files_with_metadata = all_files_df.withColumn("input_file", F.input_file_name())
            
            # Extract partition info from file paths and find latest file per ingestion_id
            files_with_partitions = (
                files_with_metadata
                .select("ingestion_id", "input_file")
                .distinct()
                .withColumn("file_path", F.col("input_file"))
                .withColumn("path_parts", F.split(F.col("file_path"), "/"))
            )
            
            # Get the latest file for each ingestion_id by finding max file path
            latest_files_per_ingestion = (
                files_with_partitions
                .groupBy("ingestion_id")
                .agg(F.max("file_path").alias("latest_file_path"))
                .collect()
            )
            
            if not latest_files_per_ingestion:
                logger.warning("⚠️ No files found with the specified pattern")
                return None
            
            # Read schemas from individual files and merge them manually
            latest_file_paths = [row.latest_file_path for row in latest_files_per_ingestion]
            logger.info(f"✅ Found {len(latest_file_paths)} latest files for schema inference")
            
            # Perform custom schema merging with type conflict resolution
            merged_schema = self._merge_schemas_with_type_resolution(latest_file_paths)
            
            if merged_schema and self._validate_schema(merged_schema):
                schema_field_names = [field.name for field in merged_schema.fields]
                logger.info(f"✅ Schema inference with type resolution successful: {len(schema_field_names)} fields found")
                logger.info(f"📋 Schema fields: {schema_field_names}")
                unique_ingestion_count = len(set(row.ingestion_id for row in latest_files_per_ingestion))
                logger.info(f"🎯 Used {len(latest_file_paths)} latest files from {unique_ingestion_count} ingestion ids")
                return merged_schema
            else:
                logger.warning("⚠️ Schema validation failed")
                return None
                
        except Exception as e:
            logger.error(f"❌ Optimized schema inference failed: {e}")
            logger.debug(f"Pattern used: {pattern}")
            return None

    def _read_files_without_merge(self, pattern: str) -> Optional[DataFrame]:
        """Read files using a simple approach without schema merging to discover available files."""
        try:
            # Try to read with the pattern first to see if any files exist
            return (
                self.spark.read
                .option("basePath", self.bronze_path)
                # Don't use mergeSchema here - we just want to see if files exist
                .parquet(pattern)
            )
        except Exception as e:
            logger.debug(f"Could not read files with pattern {pattern}: {e}")
            return None

    def _merge_schemas_with_type_resolution(self, file_paths: List[str]) -> Optional[StructType]:
        """Merge schemas from multiple files with automatic type conflict resolution.
        
        Args:
            file_paths: List of file paths to read schemas from
            
        Returns:
            Merged schema with type conflicts resolved, or None if failed
        """
        logger.info(f"🔧 Merging schemas from {len(file_paths)} files with type resolution")
        
        schemas = []
        successful_reads = 0
        
        # Read schema from each file individually
        for file_path in file_paths:
            try:
                df = (
                    self.spark.read
                    .option("basePath", self.bronze_path)
                    .parquet(file_path)
                )
                schemas.append(df.schema)
                successful_reads += 1
                logger.debug(f"✅ Read schema from {file_path}: {len(df.schema.fields)} fields")
            except Exception as e:
                logger.warning(f"⚠️ Could not read schema from {file_path}: {e}")
                continue
        
        if not schemas:
            logger.error("❌ Could not read schemas from any files")
            return None
        
        logger.info(f"✅ Successfully read schemas from {successful_reads}/{len(file_paths)} files")
        
        # Start with the first schema and merge others
        merged_schema = schemas[0]
        
        for i, schema in enumerate(schemas[1:], 1):
            try:
                merged_schema = self._merge_two_schemas(merged_schema, schema)
                logger.debug(f"✅ Merged schema {i+1}/{len(schemas)}")
            except Exception as e:
                logger.error(f"❌ Failed to merge schema {i+1}: {e}")
                return None
        
        logger.info(f"✅ Final merged schema has {len(merged_schema.fields)} fields")
        return merged_schema

    def _merge_two_schemas(self, schema1: StructType, schema2: StructType) -> StructType:
        """Merge two schemas with intelligent type resolution for conflicts.
        
        Args:
            schema1: First schema
            schema2: Second schema
            
        Returns:
            Merged schema with type conflicts resolved
        """        
        # Create a map of field names to fields for both schemas
        fields1 = {field.name: field for field in schema1.fields}
        fields2 = {field.name: field for field in schema2.fields}
        
        # Get all unique field names
        all_field_names = set(fields1.keys()) | set(fields2.keys())
        
        merged_fields = []
        type_promotions = 0
        
        for field_name in sorted(all_field_names):  # Sort for consistent ordering
            field1 = fields1.get(field_name)
            field2 = fields2.get(field_name)
            
            if field1 and field2:
                # Both schemas have this field - resolve type conflicts
                if field1.dataType == field2.dataType:
                    # Types match - use either field (they're the same)
                    merged_fields.append(field1)
                else:
                    # Types don't match - resolve conflict
                    resolved_type = self._resolve_type_conflict(
                        field_name, field1.dataType, field2.dataType
                    )
                    if resolved_type != field1.dataType or resolved_type != field2.dataType:
                        type_promotions += 1
                        logger.info(f"🔧 Type promotion for '{field_name}': {field1.dataType} + {field2.dataType} -> {resolved_type}")
                    
                    # Create new field with resolved type (nullable if either is nullable)
                    merged_field = StructField(
                        field_name, 
                        resolved_type, 
                        field1.nullable or field2.nullable
                    )
                    merged_fields.append(merged_field)
            elif field1:
                # Only in first schema
                merged_fields.append(field1)
            elif field2:
                # Only in second schema  
                merged_fields.append(field2)
        
        if type_promotions > 0:
            logger.info(f"✅ Schema merge completed with {type_promotions} type promotions")
        else:
            logger.info("✅ Schema merge completed with no type conflicts")
        
        return StructType(merged_fields)

    def _resolve_type_conflict(self, field_name: str, type1: DataType, type2: DataType) -> DataType:
        """Resolve type conflicts between two data types for the same field.
        
        Args:
            field_name: Name of the field (for logging)
            type1: First data type
            type2: Second data type
            
        Returns:
            Resolved data type that can accommodate both types
        """        
        # Define type promotion hierarchy for numeric types
        # Order from most specific to most general
        numeric_hierarchy = [
            BooleanType(),  # Can be promoted to any numeric type
            IntegerType(),  # Can be promoted to long or double
            LongType(),     # Can be promoted to double
            FloatType(),    # Can be promoted to double
            DoubleType(),   # Most general numeric type
        ]
        
        # Get the hierarchy positions (-1 if not numeric)
        pos1 = self._get_type_hierarchy_position(type1, numeric_hierarchy)
        pos2 = self._get_type_hierarchy_position(type2, numeric_hierarchy)
        
        # Both types are numeric - promote to the more general type
        if pos1 >= 0 and pos2 >= 0:
            promoted_type = numeric_hierarchy[max(pos1, pos2)]
            logger.debug(f"🔢 Numeric type resolution for '{field_name}': {type1} + {type2} -> {promoted_type}")
            return promoted_type
        
        # If one is numeric and the other is string, use string (most compatible)
        if (pos1 >= 0 and isinstance(type2, StringType)) or (pos2 >= 0 and isinstance(type1, StringType)):
            logger.debug(f"🔤 Mixed type resolution for '{field_name}': {type1} + {type2} -> StringType")
            return StringType()
        
        # Both are non-numeric and different - use string as fallback
        logger.debug(f"🔀 Fallback type resolution for '{field_name}': {type1} + {type2} -> StringType")
        return StringType()

    def _get_type_hierarchy_position(self, data_type: DataType, hierarchy: list) -> int:
        """Get the position of a data type in the hierarchy.
        
        Args:
            data_type: Data type to find
            hierarchy: List of types in promotion order
            
        Returns:
            Position in hierarchy, or -1 if not found
        """
        for i, hierarchy_type in enumerate(hierarchy):
            if type(data_type) == type(hierarchy_type):
                return i
        return -1



    def _validate_schema(self, schema: StructType) -> bool:
        """Validate that the inferred schema has required fields."""
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
        """Create raw streaming DataFrame with flexible schema handling.
        
        Args:
            schema: Schema to use as target (with type conflicts resolved)
            
        Returns:
            Raw streaming DataFrame with automatic type adaptation
        """
        # For streaming, we need a more flexible approach since we can't predict
        # the schema of each individual file. Instead, we'll read without strict schema
        # enforcement and then apply normalization.
        
        try:
            # First attempt: try to read with the resolved schema
            raw_stream: DataFrame = (
                self.spark.readStream
                .schema(schema)
                .option("basePath", self.bronze_path)
                .option("maxFilesPerTrigger", SparkConfig.MAX_FILES_PER_TRIGGER)
                .option("ignoreCorruptFiles", "true")  # Skip files that can't be read with this schema
                .parquet(f"{self.bronze_path}ingestion_id=*/date=*/hour=*")
            )
            
            logger.info("Raw stream created successfully with resolved schema")
        except Exception as e:
            logger.warning(f"Could not create stream with resolved schema: {e}")
            logger.info("Falling back to schema-flexible reading approach")
            
            # Fallback: create a more permissive schema where all potential numeric conflicts are strings
            # This allows us to handle type conversion in the transformation phase
            flexible_schema = self._create_flexible_schema(schema)
            
            raw_stream = (
                self.spark.readStream
                .schema(flexible_schema)
                .option("basePath", self.bronze_path)
                .option("maxFilesPerTrigger", SparkConfig.MAX_FILES_PER_TRIGGER)
                .option("ignoreCorruptFiles", "true")
                .parquet(f"{self.bronze_path}ingestion_id=*/date=*/hour=*")
            )
            
            logger.info("Raw stream created with flexible schema")
        
        # Add debug logging
        try:
            logger.info(f"Raw stream columns ({len(raw_stream.columns)}): {raw_stream.columns}")
            schema_details: List[str] = []
            for field in raw_stream.schema.fields:
                schema_details.append(f"{field.name}({field.dataType.simpleString()})")
            logger.info(f"Raw stream schema details: {schema_details}")
        except Exception as e:
            logger.warning(f"Could not log raw stream details: {e}")

        return raw_stream

    def _create_flexible_schema(self, resolved_schema: StructType) -> StructType:
        """Create a flexible schema that can accommodate type variations.
        
        For fields that had type conflicts, use StringType to allow flexible reading,
        then handle type conversion in the transformation phase.
        
        Args:
            resolved_schema: The schema with resolved type conflicts
            
        Returns:
            Flexible schema that can read files with different numeric types
        """
        flexible_fields = []
        
        for field in resolved_schema.fields:
            # For potentially conflicting numeric fields, use string type for flexibility
            if isinstance(field.dataType, (IntegerType, LongType, DoubleType, FloatType)):
                # Use string type to avoid read-time type conflicts
                flexible_field = StructField(field.name, StringType(), nullable=True)
                flexible_fields.append(flexible_field)
                logger.debug(f"🔄 Made field '{field.name}' flexible: {field.dataType} -> StringType")
            else:
                # Keep non-numeric fields as they are
                flexible_fields.append(field)
        
        flexible_schema = StructType(flexible_fields)
        logger.info(f"✅ Created flexible schema with {len(flexible_fields)} fields")
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
