"""
Asynchronous schema inference stream.
Monitors bronze layer for new files and infers schemas without blocking other Spark operations.
"""
import json
import time
import asyncio
from typing import Optional, Dict, List, Any, Set
from datetime import datetime
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.types import StructType
from pyspark.sql.streaming import StreamingQuery
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from .models import Base, SchemaInfo, SchemaInferenceLog
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AsyncSchemaInferenceStream:
    """Asynchronous schema inference stream for bronze data."""
    
    def __init__(self, spark: SparkSession, db_url: str = "sqlite:///schema_inference.db"):
        """Initialize the async schema inference stream.
        
        Args:
            spark: Spark session to use
            db_url: Database URL for storing schema information
        """
        self.spark = spark
        self.db_url = db_url
        self.query: Optional[StreamingQuery] = None
        self._running = False
        self._background_task: Optional[asyncio.Task] = None
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="schema-inference")
        self._file_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._processed_files: Set[str] = set()
        self._setup_database()
        
        # Configuration
        self.bronze_path = "s3a://lake/bronze/"
        self.checkpoint_path = "s3a://lake/checkpoints/schema_inference_async/"
        self.processing_interval = "60 seconds"  # Longer interval to reduce load
        self.batch_size = 5  # Process max 5 files per batch to avoid blocking

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
            
            # Load processed files into memory for faster lookup
            self._load_processed_files()
            
            logger.info(f"✅ Async schema inference database initialized: {self.db_url}")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup async schema inference database: {e}")
            raise

    def _load_processed_files(self):
        """Load already processed files into memory for fast lookup."""
        try:
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            with SessionLocal() as db:
                processed_paths = db.query(SchemaInfo.source_path).all()
                self._processed_files = {path[0] for path in processed_paths}
                logger.info(f"🔍 Loaded {len(self._processed_files)} processed files into memory")
        except Exception as e:
            logger.warning(f"⚠️ Could not load processed files: {e}")
            self._processed_files = set()

    @asynccontextmanager
    async def get_db_session(self):
        """Async context manager for schema database sessions."""
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        db = SessionLocal()
        try:
            yield db
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Async database operation failed: {e}")
            raise
        finally:
            db.close()

    async def safe_db_operation(self, operation, operation_name: str, context: Optional[Dict] = None):
        """Execute database operation asynchronously with proper error handling."""
        try:
            # Run DB operation in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor, 
                lambda: self._sync_db_operation(operation, operation_name, context)
            )
            return result
        except Exception as e:
            logger.error(f"❌ Async {operation_name} failed: {e}", extra=context)
            return None

    def _sync_db_operation(self, operation, operation_name: str, context: Optional[Dict] = None):
        """Synchronous database operation wrapper."""
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        db = SessionLocal()
        try:
            result = operation(db)
            db.commit()
            logger.debug(f"✅ {operation_name} completed successfully", extra=context)
            return result
        except Exception as e:
            db.rollback()
            logger.error(f"❌ {operation_name} failed: {e}", extra=context)
            raise
        finally:
            db.close()

    async def start_inference_stream(self) -> StreamingQuery:
        """Start the asynchronous schema inference stream."""
        logger.info("🚀 Starting async schema inference stream...")
        
        try:
            # Start background file processing task
            self._running = True
            self._background_task = asyncio.create_task(self._background_file_processor())
            
            # Create a minimal streaming source for periodic file discovery
            dummy_df = (
                self.spark
                .readStream
                .format("rate")
                .option("rowsPerSecond", 1)  # Minimal rate
                .option("numPartitions", 1)
                .load()
                .selectExpr("current_timestamp() as trigger_time", "value as trigger_id")
            )
            
            # Start the stream with lightweight file discovery
            self.query = (
                dummy_df
                .writeStream
                .queryName("bronze_layer_schema_discovery")
                .trigger(processingTime=self.processing_interval)
                .option("checkpointLocation", self.checkpoint_path)
                .foreachBatch(self._discover_files_batch)
                .outputMode("append")
                .start()
            )
            
            logger.info(f"✅ Async schema inference stream started with ID: {self.query.id}")
            return self.query
            
        except Exception as e:
            logger.error(f"❌ Failed to start async schema inference stream: {e}")
            self._running = False
            if self._background_task:
                self._background_task.cancel()
            raise

    def _discover_files_batch(self, batch_df: DataFrame, batch_id: int):
        """Lightweight file discovery that queues files for async processing."""
        logger.debug(f"🔍 File discovery trigger {batch_id}")
        
        try:
            # Run file discovery in a separate thread to avoid blocking Spark
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._async_discover_files(batch_id))
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"❌ Error in file discovery batch {batch_id}: {e}")

    async def _async_discover_files(self, batch_id: int):
        """Asynchronously discover new files and queue them for processing."""
        try:
            # Use thread pool for Spark operations to avoid blocking
            loop = asyncio.get_event_loop()
            new_files = await loop.run_in_executor(
                self._executor, 
                self._discover_new_files_sync
            )
            
            if new_files:
                logger.info(f"📁 Found {len(new_files)} new files in trigger {batch_id}")
                
                # Queue files for processing (non-blocking)
                for file_path in new_files:
                    try:
                        await asyncio.wait_for(
                            self._file_queue.put(file_path), 
                            timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning(f"⚠️ File queue full, skipping {file_path}")
                        break
            else:
                logger.debug(f"🔍 No new files found in trigger {batch_id}")
                
        except Exception as e:
            logger.error(f"❌ Error discovering files async: {e}")

    def _discover_new_files_sync(self) -> List[str]:
        """Synchronous file discovery (runs in thread pool)."""
        try:
            # Try to list files using Spark SQL (lightweight operation)
            try:
                files_df = self.spark.sql(f"LIST '{self.bronze_path}' RECURSIVE")
                # Use take() instead of collect() to limit memory usage
                file_rows = files_df.take(50)  # Limit to 50 files per scan
                
                new_files = []
                for row in file_rows:
                    file_path = row['path']
                    # Only process parquet files that haven't been processed yet
                    if (file_path.endswith('.parquet') and 
                        file_path not in self._processed_files):
                        new_files.append(file_path)
                        # Limit to batch size to prevent overwhelming
                        if len(new_files) >= self.batch_size:
                            break
                
                return new_files
                
            except Exception as e:
                logger.debug(f"Spark SQL LIST failed, using fallback: {e}")
                return self._fallback_file_discovery()
                
        except Exception as e:
            logger.error(f"❌ Error in sync file discovery: {e}")
            return []

    def _fallback_file_discovery(self) -> List[str]:
        """Fallback file discovery method."""
        try:
            # Use a pattern-based approach with limited results
            pattern_path = f"{self.bronze_path}*/*/*/*.parquet"
            df = self.spark.read.parquet(pattern_path)
            input_files = df.inputFiles()
            
            new_files = []
            for file_path in input_files:
                if (file_path not in self._processed_files and 
                    len(new_files) < self.batch_size):
                    new_files.append(file_path)
            
            return new_files
            
        except Exception as e:
            logger.debug(f"Fallback discovery failed: {e}")
            return []

    async def _background_file_processor(self):
        """Background task that processes queued files asynchronously."""
        logger.info("🔄 Starting background file processor")
        
        while self._running:
            try:
                # Wait for files with timeout to allow periodic cleanup
                try:
                    file_path = await asyncio.wait_for(
                        self._file_queue.get(), 
                        timeout=30.0
                    )
                except asyncio.TimeoutError:
                    # Periodic maintenance
                    await self._periodic_maintenance()
                    continue
                
                # Process file asynchronously
                await self._process_file_async(file_path)
                
                # Mark task as done
                self._file_queue.task_done()
                
                # Small delay to prevent overwhelming the system
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                logger.info("🛑 Background file processor cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in background file processor: {e}")
                await asyncio.sleep(1.0)  # Back off on error

    async def _process_file_async(self, file_path: str):
        """Process a single file asynchronously."""
        if file_path in self._processed_files:
            return  # Already processed
            
        start_time = time.time()
        ingestion_id = self._extract_ingestion_id(file_path)
        
        logger.debug(f"🔍 Processing file async: {file_path}")
        
        try:
            # Run Spark operations in thread pool
            loop = asyncio.get_event_loop()
            schema_data = await loop.run_in_executor(
                self._executor,
                self._infer_schema_sync,
                file_path
            )
            
            if schema_data:
                # Store in database asynchronously
                await self._store_schema_async(file_path, ingestion_id, schema_data, start_time)
                
                # Add to processed files cache
                self._processed_files.add(file_path)
                
                processing_time = (time.time() - start_time) * 1000
                logger.info(f"✅ Schema inferred async: {ingestion_id} ({processing_time:.1f}ms)")
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            logger.error(f"❌ Async schema inference failed for {file_path}: {e}")
            await self._log_inference_error_async(file_path, str(e), int(processing_time))

    def _infer_schema_sync(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Synchronous schema inference (runs in thread pool)."""
        try:
            # Read file with optimizations
            file_df = self.spark.read.option("inferSchema", "false").parquet(file_path)
            schema = file_df.schema
            
            # Use sampling instead of full count to reduce blocking
            sample_df = file_df.sample(fraction=0.1).limit(100)  # Sample for estimation
            sample_count = sample_df.count()
            estimated_count = max(sample_count * 10, sample_count)  # Rough estimation
            
            # Get sample data efficiently
            sample_data = []
            if sample_count > 0:
                sample_rows = sample_df.limit(3).collect()
                sample_data = [row.asDict() for row in sample_rows]
            
            return {
                "schema": schema,
                "record_count": estimated_count,
                "sample_data": sample_data,
                "is_estimated": True
            }
            
        except Exception as e:
            logger.error(f"❌ Sync schema inference failed: {e}")
            return None

    async def _store_schema_async(self, file_path: str, ingestion_id: str, schema_data: Dict[str, Any], start_time: float):
        """Store schema information asynchronously."""
        def store_operation(db: Session):
            # Check if already exists (race condition protection)
            existing = db.query(SchemaInfo).filter(SchemaInfo.source_path == file_path).first()
            if existing:
                return existing  # Already processed by another thread
            
            # Create schema info
            schema_info = SchemaInfo.create_or_update(
                session=db,
                ingestion_id=ingestion_id,
                source_path=file_path,
                spark_schema=schema_data["schema"],
                record_count=schema_data["record_count"],
                sample_data=schema_data["sample_data"]
            )
            
            # Log the operation
            processing_time = (time.time() - start_time) * 1000
            log_entry = SchemaInferenceLog(
                ingestion_id=ingestion_id,
                source_path=file_path,
                operation="inferred_async",
                message=f"Async schema inferred: {len(schema_data['schema'].fields)} fields, ~{schema_data['record_count']} records",
                processing_time_ms=int(processing_time)
            )
            db.add(log_entry)
            
            return schema_info
        
        await self.safe_db_operation(store_operation, f"store schema for {ingestion_id}")

    async def _log_inference_error_async(self, file_path: str, error_message: str, processing_time_ms: int = 0):
        """Log schema inference error asynchronously."""
        def log_operation(db: Session):
            ingestion_id = self._extract_ingestion_id(file_path) or "unknown"
            log_entry = SchemaInferenceLog(
                ingestion_id=ingestion_id,
                source_path=file_path,
                operation="failed_async",
                message=f"Async schema inference failed: {error_message}",
                processing_time_ms=processing_time_ms
            )
            db.add(log_entry)
        
        await self.safe_db_operation(log_operation, f"log error for {file_path}")

    async def _periodic_maintenance(self):
        """Periodic maintenance tasks."""
        try:
            # Refresh processed files cache periodically to catch external updates
            if len(self._processed_files) % 100 == 0:  # Every 100 files
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(self._executor, self._load_processed_files)
                
        except Exception as e:
            logger.debug(f"🔧 Maintenance task error: {e}")

    def _extract_ingestion_id(self, file_path: str) -> Optional[str]:
        """Extract ingestion_id from file path."""
        try:
            parts = file_path.split("/")
            for part in parts:
                if part.startswith("ingestion_id="):
                    return part.split("=", 1)[1]
            return None
        except Exception:
            return None

    async def get_schema_info_async(self, ingestion_id: str = None) -> List[Dict[str, Any]]:
        """Get schema information asynchronously."""
        def query_operation(db: Session):
            query = db.query(SchemaInfo).filter_by(is_active=True)
            if ingestion_id:
                query = query.filter_by(ingestion_id=ingestion_id)
            schemas = query.order_by(SchemaInfo.last_updated.desc()).all()
            return [schema.to_dict() for schema in schemas]
        
        result = await self.safe_db_operation(query_operation, "get schema info async")
        return result or []

    async def get_inference_stats_async(self) -> Dict[str, Any]:
        """Get schema inference statistics asynchronously."""
        def stats_operation(db: Session):
            success_count = db.query(SchemaInferenceLog).filter(
                SchemaInferenceLog.operation.in_(["inferred", "inferred_async"])
            ).count()
            
            failure_count = db.query(SchemaInferenceLog).filter(
                SchemaInferenceLog.operation.in_(["failed", "failed_async"])
            ).count()
            
            recent_logs = db.query(SchemaInferenceLog).order_by(
                SchemaInferenceLog.created_at.desc()
            ).limit(10).all()
            
            return {
                "success_count": success_count,
                "failure_count": failure_count,
                "success_rate": success_count / max(success_count + failure_count, 1) * 100,
                "queue_size": self._file_queue.qsize(),
                "processed_files_cache": len(self._processed_files),
                "recent_activity": [log.to_dict() for log in recent_logs]
            }
        
        result = await self.safe_db_operation(stats_operation, "get inference stats async")
        return result or {}

    async def stop(self):
        """Stop the async schema inference stream."""
        logger.info("🛑 Stopping async schema inference stream...")
        
        # Stop background processing
        self._running = False
        
        # Cancel background task
        if self._background_task:
            self._background_task.cancel()
            try:
                await asyncio.wait_for(self._background_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        
        # Stop Spark streaming query
        if self.query and self.query.isActive:
            self.query.stop()
            self.query = None
        
        # Shutdown thread pool
        self._executor.shutdown(wait=True)
        
        logger.info("✅ Async schema inference stream stopped")

    def stop_sync(self):
        """Synchronous stop method for compatibility."""
        if self._background_task:
            # If we're in an async context, use the async stop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create a task to stop asynchronously
                    asyncio.create_task(self.stop())
                    return
            except RuntimeError:
                pass
        
        # Fallback to immediate shutdown
        self._running = False
        if self.query and self.query.isActive:
            self.query.stop()
            self.query = None
        self._executor.shutdown(wait=False)
        logger.info("✅ Async schema inference stream stopped (sync)")
