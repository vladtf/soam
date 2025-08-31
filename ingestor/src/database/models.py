"""
SQLAlchemy models for data source management.
Following backend ORM patterns for consistency.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base


class DataSourceType(Base):
    """Data source type definition (MQTT, REST API, etc.)."""
    __tablename__ = "data_source_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)           # mqtt, rest_api, database, file
    display_name = Column(String(100), nullable=False)                         # "MQTT Broker", "REST API"
    description = Column(Text, nullable=True)
    connector_class = Column(String(200), nullable=False)                      # Python class path
    config_schema = Column(JSON, nullable=False)                               # JSON schema for validation
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship to data sources
    data_sources = relationship("DataSource", back_populates="type")
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "connector_class": self.connector_class,
            "config_schema": self.config_schema,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DataSource(Base):
    """Individual data source instance."""
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)                                 # User-friendly name
    type_id = Column(Integer, ForeignKey("data_source_types.id"), nullable=False)
    config = Column(JSON, nullable=False)                                      # Type-specific configuration
    ingestion_id = Column(String(100), unique=True, nullable=False, index=True)  # Generated identifier
    enabled = Column(Boolean, nullable=False, default=True)
    status = Column(String(20), nullable=False, default='inactive')            # active, inactive, error, stopped
    last_connection = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    
    # Ownership and audit fields
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    type = relationship("DataSourceType", back_populates="data_sources")
    metrics = relationship("DataSourceMetric", back_populates="data_source", cascade="all, delete-orphan")
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type_id": self.type_id,
            "type_name": self.type.name if self.type else None,
            "type_display_name": self.type.display_name if self.type else None,
            "config": self.config,
            "ingestion_id": self.ingestion_id,
            "enabled": self.enabled,
            "status": self.status,
            "last_connection": self.last_connection.isoformat() if self.last_connection else None,
            "last_error": self.last_error,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DataSourceMetric(Base):
    """Data source metrics and monitoring."""
    __tablename__ = "data_source_metrics"

    id = Column(Integer, primary_key=True, index=True)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False)
    messages_received = Column(Integer, nullable=False, default=0)
    messages_processed = Column(Integer, nullable=False, default=0)
    last_processed = Column(DateTime(timezone=True), nullable=True)
    processing_latency_ms = Column(Float, nullable=True)
    error_count = Column(Integer, nullable=False, default=0)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    data_source = relationship("DataSource", back_populates="metrics")
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "data_source_id": self.data_source_id,
            "messages_received": self.messages_received,
            "messages_processed": self.messages_processed,
            "last_processed": self.last_processed.isoformat() if self.last_processed else None,
            "processing_latency_ms": self.processing_latency_ms,
            "error_count": self.error_count,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
        }
