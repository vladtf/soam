"""
Continuous schema inference stream.
Monitors bronze layer for new files and infers schemas, storing results in SQLite.
"""
import json
import time
from typing import Optional, Dict, List, Any
from datetime import datetime
from contextlib import contextmanager
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.types import StructType
from pyspark.sql.streaming import StreamingQuery
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from .models import Base, SchemaInfo, SchemaInferenceLog
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SchemaInferenceStream:
    """Continuous schema inference stream for bronze data."""
    
    def __init__(self, spark: SparkSession, db_url: str = "sqlite:///schema_inference.db"):
        """Initialize the schema inference stream.
        
        Args:
            spark: Spark session to use
            db_url: Database URL for storing schema information
        """
        self.spark = spark
        self.db_url = db_url
        self.query: Optional[StreamingQuery] = None
        self._setup_database()
        
        # Configuration
        self.bronze_path = "s3a://lake/bronze/"
        self.checkpoint_path = "s3a://lake/checkpoints/schema_inference/"
        self.processing_interval = "30 seconds"  # Check for new files every 30 seconds

    def _setup_database(self):
        """Setup SQLite database with proper configuration."""
        try:
            # Create engine with SQLite optimizations
            self.engine = create_engine(
                self.db_url,
                poolclass=StaticPool,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30
                },
                echo=False
            )
            
            # Setup SQLite pragmas for better performance
            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA temp_store=memory")
                cursor.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
                cursor.close()
            
            # Create all tables
            Base.metadata.create_all(bind=self.engine)
            logger.info(f"✅ Schema inference database initialized: {self.db_url}")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup schema inference database: {e}")
            raise

    @contextmanager
    def get_db_session(self):
        """Context manager for schema database sessions with automatic cleanup."""
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        db = SessionLocal()
        try:
            yield db
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            db.close()
    
    def safe_db_operation(self, operation, operation_name: str, context: Optional[Dict] = None):
        """Execute database operation with proper error handling and logging."""
        try:
            with self.get_db_session() as db:
                result = operation(db)
                logger.debug(f"✅ {operation_name} completed successfully", extra=context)
                return result
        except Exception as e:
            logger.error(f"❌ {operation_name} failed: {e}", extra=context)
            return None

    def get_session(self) -> Session:
        """Get database session."""
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        return SessionLocal()

    def start_inference_stream(self) -> StreamingQuery:
        """Start the continuous schema inference stream.
        
        For schema inference, we can't use structured streaming directly since we don't know
        the schema ahead of time. Instead, we'll use a different approach that periodically
        scans for new files and processes them in batches.
        """
        logger.info("🚀 Starting schema inference stream...")
        
        try:
            # Create a dummy streaming source that triggers periodically
            # We'll use this to trigger our schema inference logic at regular intervals
            dummy_df = (
                self.spark
                .readStream
                .format("rate")  # Creates a streaming DataFrame with timestamp and value columns
                .option("rowsPerSecond", 1)  # Generate 1 row per second
                .option("numPartitions", 1)  # Single partition for simplicity
                .load()
                .selectExpr("current_timestamp() as trigger_time", "value as trigger_id")
            )
            
            # Start the stream with our processing function
            self.query = (
                dummy_df
                .writeStream
                .trigger(processingTime=self.processing_interval)
                .option("checkpointLocation", self.checkpoint_path)
                .foreachBatch(self._process_batch)
                .outputMode("append")
                .start()
            )
            
            logger.info(f"✅ Schema inference stream started with ID: {self.query.id}")
            return self.query
            
        except Exception as e:
            logger.error(f"❌ Failed to start schema inference stream: {e}")
            raise

    def _process_batch(self, batch_df: DataFrame, batch_id: int):
        """Process each trigger interval to discover and analyze new bronze files."""
        start_time = time.time()
        logger.info(f"📊 Schema inference trigger {batch_id} - scanning for new files...")
        
        def batch_processing(db: Session):
            # Discover new bronze files
            new_files = self._discover_new_files(db)
            
            if not new_files:
                logger.debug(f"🔍 No new files found in trigger {batch_id}")
                return
            
            logger.info(f"📁 Found {len(new_files)} new files to process in trigger {batch_id}")
            
            for file_path in new_files:
                try:
                    self._infer_schema_for_file(db, file_path)
                except Exception as e:
                    logger.error(f"❌ Error processing file {file_path}: {e}")
                    self._log_inference_error(db, file_path, str(e))
            
            processing_time = (time.time() - start_time) * 1000
            logger.info(f"✅ Schema inference trigger {batch_id} completed in {processing_time:.1f}ms")
        
        self.safe_db_operation(batch_processing, f"process batch {batch_id}")

    def _discover_new_files(self, session: Session) -> List[str]:
        """Discover new bronze files that haven't been processed yet."""
        try:
            # Get list of files already processed
            processed_paths = set()
            existing_schemas = session.query(SchemaInfo.source_path).all()
            for (path,) in existing_schemas:
                processed_paths.add(path)
            
            # Use Spark to list files in bronze directory
            try:
                # Try to list files using Spark's file listing capabilities
                bronze_files = []
                
                # Use Spark SQL to list files
                files_df = self.spark.sql(f"LIST '{self.bronze_path}' RECURSIVE")
                file_rows = files_df.collect()
                
                for row in file_rows:
                    file_path = row['path']
                    # Only process parquet files that haven't been processed yet
                    if (file_path.endswith('.parquet') and 
                        file_path not in processed_paths):
                        bronze_files.append(file_path)
                
                return bronze_files[:10]  # Limit to 10 files per batch to avoid overload
                
            except Exception as e:
                logger.warning(f"Could not list files using Spark SQL: {e}")
                # Fallback: try direct MinIO/S3 listing if available
                return self._fallback_file_discovery(processed_paths)
                
        except Exception as e:
            logger.error(f"❌ Error discovering new files: {e}")
            return []

    def _fallback_file_discovery(self, processed_paths: set) -> List[str]:
        """Fallback method for file discovery when Spark SQL LIST doesn't work."""
        try:
            # This is a simplified fallback - in a real implementation, you might
            # want to integrate with MinIO client or use other file listing methods
            logger.info("Using fallback file discovery method")
            
            # Try to read from a known pattern and see what files exist
            try:
                # This will list files that match the pattern
                pattern_path = f"{self.bronze_path}*/*/*/*.parquet"
                df = self.spark.read.parquet(pattern_path)
                input_files = df.inputFiles()
                
                new_files = []
                for file_path in input_files:
                    if file_path not in processed_paths:
                        new_files.append(file_path)
                
                return new_files[:5]  # Limit for safety
                
            except Exception as e:
                logger.debug(f"Pattern-based discovery also failed: {e}")
                return []
                
        except Exception as e:
            logger.warning(f"Fallback file discovery failed: {e}")
            return []

    def _infer_schema_for_file(self, session: Session, file_path: str):
        """Infer schema for a specific file."""
        start_time = time.time()
        
        # Extract ingestion_id from file path
        ingestion_id = self._extract_ingestion_id(file_path)
        if not ingestion_id:
            logger.warning(f"⚠️ Could not extract ingestion_id from path: {file_path}")
            return
        
        try:
            # Check if we already have schema for this exact file
            existing_schema = session.query(SchemaInfo).filter(
                SchemaInfo.source_path == file_path
            ).first()
            
            if existing_schema:
                logger.debug(f"⏭️  Schema already exists for {file_path}")
                return
            
            # Read the specific file to get its schema
            file_df = self.spark.read.parquet(file_path)
            schema = file_df.schema
            
            # Get record count and sample data
            record_count = file_df.count()
            sample_data = []
            
            if record_count > 0:
                # Get up to 3 sample records
                sample_rows = file_df.limit(3).collect()
                sample_data = [row.asDict() for row in sample_rows]
            
            # Extract additional metadata
            device_type = self._extract_device_type_from_path(file_path)
            
            # Create or update schema info record using the model's method
            schema_info = SchemaInfo.create_or_update(
                session=session,
                ingestion_id=ingestion_id,
                source_path=file_path,
                spark_schema=schema,
                record_count=record_count,
                sample_data=sample_data
            )
            
            processing_time = (time.time() - start_time) * 1000
            
            # Log the operation
            log_entry = SchemaInferenceLog(
                ingestion_id=ingestion_id,
                source_path=file_path,
                operation="inferred",
                message=f"Schema inferred: {len(schema.fields)} fields, {record_count} records",
                processing_time_ms=int(processing_time)
            )
            session.add(log_entry)
            
            logger.info(f"✅ Schema inferred for {device_type} ({ingestion_id}): {len(schema.fields)} fields, {record_count} records ({processing_time:.1f}ms)")
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            logger.error(f"❌ Schema inference failed for {file_path}: {e}")
            self._log_inference_error(session, file_path, str(e), int(processing_time))
            raise

    def _extract_ingestion_id(self, file_path: str) -> Optional[str]:
        """Extract ingestion_id from file path."""
        try:
            # Path format: s3a://lake/bronze/ingestion_id=<id>/date=<date>/hour=<hour>/...
            parts = file_path.split("/")
            for part in parts:
                if part.startswith("ingestion_id="):
                    return part.split("=", 1)[1]
            return None
        except Exception:
            return None

    def _extract_device_type_from_path(self, file_path: str) -> str:
        """Extract device type from file path."""
        try:
            # Try to infer from path structure or filename
            # This is a simplified version - you might want to enhance this
            # based on your actual path structure
            if "temperature" in file_path.lower():
                return "temperature_sensor"
            elif "air" in file_path.lower() or "quality" in file_path.lower():
                return "air_quality_sensor"
            elif "bin" in file_path.lower() or "smart" in file_path.lower():
                return "smart_bin"
            else:
                return "unknown_device"
        except Exception:
            return "unknown_device"

    def _extract_ingestion_id_from_path(self, file_path: str) -> str:
        """Extract ingestion_id from file path, with fallback."""
        ingestion_id = self._extract_ingestion_id(file_path)
        return ingestion_id or "unknown"

    def _extract_schema_dict(self, schema: StructType) -> Dict[str, Any]:
        """Convert Spark schema to dictionary format."""
        def field_to_dict(field):
            return {
                "name": field.name,
                "type": str(field.dataType),
                "nullable": field.nullable,
                "metadata": field.metadata if field.metadata else {}
            }
        
        return {
            "fields": [field_to_dict(field) for field in schema.fields],
            "field_count": len(schema.fields),
            "schema_version": "1.0"
        }

    def _log_inference_error(self, session: Session, file_path: str, error_message: str, processing_time_ms: int = 0):
        """Log schema inference error."""
        try:
            ingestion_id = self._extract_ingestion_id(file_path) or "unknown"
            
            log_entry = SchemaInferenceLog(
                ingestion_id=ingestion_id,
                source_path=file_path,
                operation="failed",
                message=f"Schema inference failed: {error_message}",
                processing_time_ms=processing_time_ms
            )
            session.add(log_entry)
            logger.debug(f"🔍 Logged inference error for {ingestion_id}: {error_message}")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not log inference error: {e}")

    def get_schema_info(self, ingestion_id: str = None) -> List[Dict[str, Any]]:
        """Get schema information from database."""
        def query_schema_info(db: Session) -> List[Dict[str, Any]]:
            query = db.query(SchemaInfo).filter_by(is_active=True)
            if ingestion_id:
                query = query.filter_by(ingestion_id=ingestion_id)
            schemas = query.order_by(SchemaInfo.last_updated.desc()).all()
            return [schema.to_dict() for schema in schemas]
        
        result = self.safe_db_operation(query_schema_info, "get schema info", {"ingestion_id": ingestion_id})
        return result or []

    def get_available_sources(self) -> List[str]:
        """Get list of available ingestion IDs (sources)."""
        def query_sources(db: Session) -> List[str]:
            result = db.query(SchemaInfo.ingestion_id)\
                      .filter_by(is_active=True)\
                      .distinct()\
                      .all()
            return [row[0] for row in result]
        
        result = self.safe_db_operation(query_sources, "get available sources")
        return result or []

    def build_data_context(self) -> Dict[str, Any]:
        """Build comprehensive data context from schema database."""
        def build_context_data(db: Session) -> Dict[str, Any]:
            # Get all active schemas
            schemas = db.query(SchemaInfo)\
                       .filter_by(is_active=True)\
                       .order_by(SchemaInfo.last_updated.desc())\
                       .all()
            
            context = {
                "sources": {},
                "total_sources": 0,
                "total_fields": 0,
                "total_records": 0,
                "last_updated": None
            }
            
            sources_dict = {}
            total_fields = 0
            total_records = 0
            latest_update = None
            
            for schema_info in schemas:
                ingestion_id = schema_info.ingestion_id
                
                if ingestion_id not in sources_dict:
                    sources_dict[ingestion_id] = {
                        "ingestion_id": ingestion_id,
                        "fields": [],
                        "field_count": 0,
                        "record_count": 0,
                        "first_seen": schema_info.first_seen.isoformat() if schema_info.first_seen else None,
                        "last_updated": schema_info.last_updated.isoformat() if schema_info.last_updated else None,
                        "sample_data": schema_info.sample_data
                    }
                
                # Parse schema JSON to get field information
                try:
                    schema_dict = json.loads(schema_info.schema_json)
                    for field_name, field_info in schema_dict.items():
                        sources_dict[ingestion_id]["fields"].append({
                            "name": field_name,
                            "type": field_info.get("type", "unknown"),
                            "nullable": field_info.get("nullable", True)
                        })
                except Exception as e:
                    logger.warning(f"Could not parse schema for {ingestion_id}: {e}")
                
                sources_dict[ingestion_id]["field_count"] = max(
                    sources_dict[ingestion_id]["field_count"], 
                    schema_info.field_count
                )
                sources_dict[ingestion_id]["record_count"] = max(
                    sources_dict[ingestion_id]["record_count"], 
                    schema_info.record_count
                )
                
                total_fields += schema_info.field_count
                total_records += schema_info.record_count
                
                if not latest_update or (schema_info.last_updated and schema_info.last_updated > latest_update):
                    latest_update = schema_info.last_updated
            
            context["sources"] = sources_dict
            context["total_sources"] = len(sources_dict)
            context["total_fields"] = total_fields
            context["total_records"] = total_records
            context["last_updated"] = latest_update.isoformat() if latest_update else None
            
            return context
        
        result = self.safe_db_operation(build_context_data, "build data context")
        return result or {"sources": {}, "error": "Failed to build data context"}

    def get_inference_stats(self) -> Dict[str, Any]:
        """Get schema inference statistics."""
        def query_stats(db: Session) -> Dict[str, Any]:
            # Get success/failure counts
            success_count = db.query(SchemaInferenceLog)\
                             .filter_by(operation="inferred")\
                             .count()
            
            failure_count = db.query(SchemaInferenceLog)\
                             .filter_by(operation="failed")\
                             .count()
            
            # Get recent activity
            recent_logs = db.query(SchemaInferenceLog)\
                           .order_by(SchemaInferenceLog.created_at.desc())\
                           .limit(10)\
                           .all()
            
            return {
                "success_count": success_count,
                "failure_count": failure_count,
                "success_rate": success_count / max(success_count + failure_count, 1) * 100,
                "recent_activity": [log.to_dict() for log in recent_logs]
            }
        
        result = self.safe_db_operation(query_stats, "get inference stats")
        return result or {}

    def stop(self):
        """Stop the schema inference stream."""
        if self.query and self.query.isActive:
            logger.info("🛑 Stopping schema inference stream...")
            self.query.stop()
            self.query = None
            logger.info("✅ Schema inference stream stopped")
