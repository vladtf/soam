"""
SQLAlchemy models for schema inference functionality.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import Session
from src.database.database import Base
import json
from datetime import datetime
from typing import Dict, Any, Optional


def _convert_spark_schema_to_dict(spark_schema) -> Dict[str, Any]:
    """Convert Spark schema (StructType or dict) to JSON-serializable dictionary."""
    if hasattr(spark_schema, 'jsonValue'):
        # It's a Spark StructType - convert to JSON
        return spark_schema.jsonValue()
    elif hasattr(spark_schema, 'json'):
        # Alternative method for Spark schemas
        return json.loads(spark_schema.json())
    elif isinstance(spark_schema, dict):
        # It's already a dictionary
        return spark_schema
    else:
        # Try to convert to string and then parse
        try:
            schema_str = str(spark_schema)
            if schema_str.startswith('{'):
                return json.loads(schema_str)
            else:
                # Return a simple representation
                return {"schema_string": schema_str}
        except Exception:
            return {"error": "Could not serialize schema", "type": str(type(spark_schema))}


def _calculate_field_count(spark_schema) -> int:
    """Calculate the number of fields in a Spark schema."""
    if hasattr(spark_schema, 'fields'):
        # It's a Spark StructType
        return len(spark_schema.fields)
    elif isinstance(spark_schema, dict):
        if 'fields' in spark_schema:
            return len(spark_schema['fields'])
        else:
            return len(spark_schema)
    else:
        return 0


class SchemaInfo(Base):
    """Schema information for ingested data sources."""
    __tablename__ = "schema_info"

    id = Column(Integer, primary_key=True, index=True)
    ingestion_id = Column(String(255), nullable=False, index=True)  # Source identifier
    source_path = Column(String(1024), nullable=False, index=True)  # File path
    schema_json = Column(Text, nullable=False)                      # Schema as JSON string
    field_count = Column(Integer, nullable=False, default=0)        # Number of fields
    record_count = Column(Integer, nullable=False, default=0)       # Number of records
    sample_data = Column(Text, nullable=True)                       # Sample data as JSON
    is_active = Column(Boolean, nullable=False, default=True)       # Whether this schema is current
    
    # Timestamps
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        """Convert the model to a dictionary."""
        try:
            schema_dict = json.loads(self.schema_json) if self.schema_json else {}
        except json.JSONDecodeError:
            schema_dict = {}
        
        try:
            sample_dict = json.loads(self.sample_data) if self.sample_data else None
        except json.JSONDecodeError:
            sample_dict = None

        return {
            "id": self.id,
            "ingestion_id": self.ingestion_id,
            "source_path": self.source_path,
            "schema": schema_dict,
            "field_count": self.field_count,
            "record_count": self.record_count,
            "sample_data": sample_dict,
            "is_active": self.is_active,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }

    @classmethod
    def create_or_update(cls, 
                        session,
                        ingestion_id: str,
                        source_path: str, 
                        spark_schema: Any,  # Can be StructType or dict
                        record_count: int = 0,
                        sample_data: Optional[Dict] = None):
        """Create a new SchemaInfo instance or update existing one."""
        # Check if a schema already exists for this source
        existing = session.query(cls).filter(
            cls.source_path == source_path
        ).first()
        
        # Convert Spark schema to JSON-serializable format
        schema_dict = _convert_spark_schema_to_dict(spark_schema)
        field_count = _calculate_field_count(spark_schema)
        
        if existing:
            # Update existing schema
            existing.schema_json = json.dumps(schema_dict)
            existing.field_count = field_count
            existing.record_count = record_count
            existing.sample_data = json.dumps(sample_data) if sample_data else existing.sample_data
            existing.last_updated = datetime.utcnow()
            existing.is_active = True
            return existing
        else:
            # Create new schema
            new_schema = cls(
                ingestion_id=ingestion_id,
                source_path=source_path,
                schema_json=json.dumps(schema_dict),
                field_count=field_count,
                record_count=record_count,
                sample_data=json.dumps(sample_data) if sample_data else None,
                is_active=True
            )
            session.add(new_schema)
            return new_schema


class SchemaInferenceLog(Base):
    """Log of schema inference operations for debugging and monitoring."""
    __tablename__ = "schema_inference_log"

    id = Column(Integer, primary_key=True, index=True)
    operation = Column(String(64), nullable=False, index=True)      # Operation type (inferred, failed, etc.)
    source_path = Column(String(1024), nullable=False)             # File path processed
    ingestion_id = Column(String(255), nullable=True, index=True)  # Source identifier
    processing_time_ms = Column(Float, nullable=True)              # Processing time in milliseconds
    message = Column(Text, nullable=True)                          # Log message (success or error)
    error_message = Column(Text, nullable=True)                    # Error message if failed (backwards compatibility)
    context = Column(Text, nullable=True)                          # Additional context as JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self) -> dict:
        """Convert the model to a dictionary."""
        try:
            context_dict = json.loads(self.context) if self.context else {}
        except json.JSONDecodeError:
            context_dict = {}

        return {
            "id": self.id,
            "operation": self.operation,
            "source_path": self.source_path,
            "ingestion_id": self.ingestion_id,
            "processing_time_ms": self.processing_time_ms,
            "message": self.message,
            "error_message": self.error_message,
            "context": context_dict,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
