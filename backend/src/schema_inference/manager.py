"""
Async schema inference manager for non-blocking schema inference operations.
"""
import asyncio
from typing import Optional, Dict, List, Any
from pyspark.sql import SparkSession
from pyspark.sql.streaming import StreamingQuery

from .async_stream import AsyncSchemaInferenceStream
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SchemaInferenceManager:
    """Manager for async schema inference operations."""
    
    def __init__(self, spark: SparkSession, db_url: str = "sqlite:///schema_inference.db"):
        """Initialize the async schema inference manager.
        
        Args:
            spark: Spark session to use
            db_url: Database URL for storing schema information
        """
        self.spark = spark
        self.db_url = db_url
        self.stream_impl = AsyncSchemaInferenceStream(spark, db_url)
        self.query: Optional[StreamingQuery] = None
        
        logger.info("✅ Using async schema inference implementation")

    async def start_inference_stream(self) -> StreamingQuery:
        """Start the async schema inference stream."""
        self.query = await self.stream_impl.start_inference_stream()
        return self.query

    def start_inference_stream_sync(self) -> StreamingQuery:
        """Start the schema inference stream synchronously."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, create a task
                task = asyncio.create_task(self.stream_impl.start_inference_stream())
                logger.info("🚀 Starting async schema inference stream as background task")
                return None  # Will be available later
            else:
                # We can run the async function
                self.query = loop.run_until_complete(self.stream_impl.start_inference_stream())
        except RuntimeError:
            # No event loop, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                self.query = loop.run_until_complete(self.stream_impl.start_inference_stream())
            finally:
                loop.close()
        return self.query

    def get_schema_info(self, ingestion_id: str = None) -> List[Dict[str, Any]]:
        """Get schema information."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, use sync fallback
                return self._get_schema_info_sync(ingestion_id)
            else:
                return loop.run_until_complete(self.stream_impl.get_schema_info_async(ingestion_id))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.stream_impl.get_schema_info_async(ingestion_id))
            finally:
                loop.close()

    def _get_schema_info_sync(self, ingestion_id: str = None) -> List[Dict[str, Any]]:
        """Synchronous fallback for getting schema info."""
        try:
            from sqlalchemy.orm import sessionmaker
            from .models import SchemaInfo
            
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.stream_impl.engine)
            with SessionLocal() as db:
                query = db.query(SchemaInfo).filter_by(is_active=True)
                if ingestion_id:
                    query = query.filter_by(ingestion_id=ingestion_id)
                schemas = query.order_by(SchemaInfo.last_updated.desc()).all()
                return [schema.to_dict() for schema in schemas]
        except Exception as e:
            logger.error(f"❌ Error getting schema info: {e}")
            return []

    def get_available_sources(self) -> List[str]:
        """Get list of available ingestion IDs."""
        try:
            from sqlalchemy.orm import sessionmaker
            from .models import SchemaInfo
            
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.stream_impl.engine)
            with SessionLocal() as db:
                result = db.query(SchemaInfo.ingestion_id).filter_by(is_active=True).distinct().all()
                return [row[0] for row in result]
        except Exception as e:
            logger.error(f"❌ Error getting available sources: {e}")
            return []

    def build_data_context(self) -> Dict[str, Any]:
        """Build comprehensive data context."""
        try:
            from sqlalchemy.orm import sessionmaker
            from .models import SchemaInfo
            import json
            
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.stream_impl.engine)
            with SessionLocal() as db:
                schemas = db.query(SchemaInfo).filter_by(is_active=True).order_by(SchemaInfo.last_updated.desc()).all()
                
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
                    
                    # Parse schema JSON
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
                
        except Exception as e:
            logger.error(f"❌ Error building data context: {e}")
            return {"sources": {}, "error": "Failed to build data context"}

    def get_inference_stats(self) -> Dict[str, Any]:
        """Get schema inference statistics."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Fallback to sync implementation
                return self._get_inference_stats_sync()
            else:
                return loop.run_until_complete(self.stream_impl.get_inference_stats_async())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.stream_impl.get_inference_stats_async())
            finally:
                loop.close()

    def _get_inference_stats_sync(self) -> Dict[str, Any]:
        """Synchronous fallback for getting inference stats."""
        try:
            from sqlalchemy.orm import sessionmaker
            from .models import SchemaInferenceLog
            
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.stream_impl.engine)
            with SessionLocal() as db:
                success_count = db.query(SchemaInferenceLog).filter(
                    SchemaInferenceLog.operation.in_(["inferred", "inferred_async"])
                ).count()
                
                failure_count = db.query(SchemaInferenceLog).filter(
                    SchemaInferenceLog.operation.in_(["failed", "failed_async"])
                ).count()
                
                recent_logs = db.query(SchemaInferenceLog).order_by(
                    SchemaInferenceLog.created_at.desc()
                ).limit(10).all()
                
                stats = {
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "success_rate": success_count / max(success_count + failure_count, 1) * 100,
                    "recent_activity": [log.to_dict() for log in recent_logs]
                }
                
                # Add async-specific stats if available
                if hasattr(self.stream_impl, '_file_queue'):
                    stats["queue_size"] = self.stream_impl._file_queue.qsize()
                    stats["processed_files_cache"] = len(self.stream_impl._processed_files)
                
                return stats
                
        except Exception as e:
            logger.error(f"❌ Error getting inference stats: {e}")
            return {}

    def is_active(self) -> bool:
        """Check if the schema inference stream is active."""
        return self.query is not None and self.query.isActive

    def stop(self):
        """Stop the schema inference stream."""
        if hasattr(self.stream_impl, 'stop_sync'):
            self.stream_impl.stop_sync()
        else:
            # Try async stop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.stream_impl.stop())
                else:
                    loop.run_until_complete(self.stream_impl.stop())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.stream_impl.stop())
                finally:
                    loop.close()
        
        self.query = None
        logger.info("✅ Schema inference manager stopped")
