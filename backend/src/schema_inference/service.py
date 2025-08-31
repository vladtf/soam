"""
Schema service for accessing stored schema information from SQLite.
Provides fast access to schema data without Spark overhead.
"""
import json
from typing import Optional, Dict, List, Any
from contextlib import contextmanager
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from .models import Base, SchemaInfo, SchemaInferenceLog
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SchemaService:
    """Service for accessing schema information stored in SQLite."""
    
    def __init__(self, db_url: str = "sqlite:///schema_inference.db"):
        """Initialize the schema service.
        
        Args:
            db_url: Database URL for schema information
        """
        self.db_url = db_url
        self._engine = None
        self._setup_database()
    
    def _setup_database(self):
        """Setup database connection."""
        try:
            self._engine = create_engine(
                self.db_url,
                poolclass=StaticPool,
                connect_args={"check_same_thread": False, "timeout": 30},
                echo=False
            )
            
            # Create tables if they don't exist
            Base.metadata.create_all(bind=self._engine)
            logger.debug(f"Schema service database initialized: {self.db_url}")
            
        except Exception as e:
            logger.error(f"Failed to setup schema service database: {e}")
            raise
    
    @contextmanager
    def get_db_session(self):
        """Context manager for schema database sessions with automatic cleanup."""
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self._engine)
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
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self._engine)
        return SessionLocal()
    
    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """Get all available schemas."""
        def query_schemas(db: Session) -> List[Dict[str, Any]]:
            schemas = db.query(SchemaInfo)\
                       .filter_by(is_active=True)\
                       .order_by(SchemaInfo.last_updated.desc())\
                       .all()
            return [schema.to_dict() for schema in schemas]
        
        result = self.safe_db_operation(query_schemas, "get all schemas", {"service": "schema_inference"})
        return result or []
    
    def get_schema(self, ingestion_id: str) -> Optional[Dict[str, Any]]:
        """Get schema for a specific ingestion ID.
        
        Args:
            ingestion_id: Ingestion ID to get schema for
            
        Returns:
            Schema dictionary or None if not found
        """
        def query_schema(db: Session) -> Optional[Dict[str, Any]]:
            schema = db.query(SchemaInfo)\
                      .filter_by(ingestion_id=ingestion_id, is_active=True)\
                      .order_by(SchemaInfo.last_updated.desc())\
                      .first()
            return schema.to_dict() if schema else None
        
        return self.safe_db_operation(query_schema, f"get schema for {ingestion_id}", {"ingestion_id": ingestion_id})
    
    def get_available_sources(self) -> List[str]:
        """Get list of available ingestion IDs (sources)."""
        def query_sources(db: Session) -> List[str]:
            result = db.query(SchemaInfo.ingestion_id)\
                      .filter_by(is_active=True)\
                      .distinct()\
                      .all()
            return [row[0] for row in result]
        
        result = self.safe_db_operation(query_sources, "get available sources", {"service": "schema_inference"})
        return result or []
    
    def build_data_context(self) -> Dict[str, Any]:
        """Build comprehensive data context from schema database.
        
        Returns:
            Dictionary containing data context information
        """
        def build_context_data(db: Session) -> Dict[str, Any]:
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
                        "sample_data": []
                    }
                
                # Parse schema JSON to get field information
                try:
                    schema_dict = json.loads(schema_info.schema_json) if schema_info.schema_json else {}
                    fields = []
                    for field_name, field_info in schema_dict.items():
                        fields.append({
                            "name": field_name,
                            "type": field_info.get("type", "unknown") if isinstance(field_info, dict) else str(field_info),
                            "nullable": field_info.get("nullable", True) if isinstance(field_info, dict) else True
                        })
                    
                    sources_dict[ingestion_id]["fields"] = fields
                    sources_dict[ingestion_id]["field_count"] = len(fields)
                    
                    # Parse sample data
                    if schema_info.sample_data:
                        sample_data = json.loads(schema_info.sample_data) if isinstance(schema_info.sample_data, str) else schema_info.sample_data
                        sources_dict[ingestion_id]["sample_data"] = sample_data
                    
                except Exception as e:
                    logger.warning(f"Could not parse schema for {ingestion_id}: {e}")
                    sources_dict[ingestion_id]["field_count"] = schema_info.field_count or 0
                
                sources_dict[ingestion_id]["record_count"] = max(
                    sources_dict[ingestion_id]["record_count"], 
                    schema_info.record_count or 0
                )
                
                total_fields += sources_dict[ingestion_id]["field_count"]
                total_records += sources_dict[ingestion_id]["record_count"]
                
                if not latest_update or (schema_info.last_updated and schema_info.last_updated > latest_update):
                    latest_update = schema_info.last_updated
            
            context["sources"] = sources_dict
            context["total_sources"] = len(sources_dict)
            context["total_fields"] = total_fields
            context["total_records"] = total_records
            context["last_updated"] = latest_update.isoformat() if latest_update else None
            
            return context
        
        result = self.safe_db_operation(build_context_data, "build data context", {"service": "schema_inference"})
        return result or {"sources": {}, "error": "Failed to build data context"}
    
    def get_schema_stats(self) -> Dict[str, Any]:
        """Get schema database statistics.
        
        Returns:
            Dictionary containing statistics
        """
        def query_stats(db: Session) -> Dict[str, Any]:
            # Count active schemas
            schema_count = db.query(SchemaInfo).filter_by(is_active=True).count()
            
            # Count inference operations
            success_count = db.query(SchemaInferenceLog)\
                             .filter_by(operation="inferred")\
                             .count()
            
            failure_count = db.query(SchemaInferenceLog)\
                             .filter_by(operation="failed")\
                             .count()
            
            # Get recent activity
            recent_logs = db.query(SchemaInferenceLog)\
                           .order_by(SchemaInferenceLog.created_at.desc())\
                           .limit(5)\
                           .all()
            
            return {
                "active_schemas": schema_count,
                "inference_success": success_count,
                "inference_failures": failure_count,
                "success_rate": success_count / max(success_count + failure_count, 1) * 100,
                "recent_activity": [log.to_dict() for log in recent_logs]
            }
        
        result = self.safe_db_operation(query_stats, "get schema stats", {"service": "schema_inference"})
        return result or {"error": "Failed to get schema stats"}


# Singleton instance
_schema_service: Optional[SchemaService] = None


def get_schema_service() -> SchemaService:
    """Get the global schema service instance."""
    global _schema_service
    if _schema_service is None:
        _schema_service = SchemaService()
    return _schema_service


def reset_schema_service():
    """Reset the global schema service (for testing)."""
    global _schema_service
    _schema_service = None
