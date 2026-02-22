"""
Data source registry and management services.
Handles data source types and instances using SQLAlchemy ORM.
"""
import json
import asyncio
from typing import Dict, Any, List, Optional, Type
from dataclasses import dataclass
import logging
import hashlib
import re
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database.database import get_db
from ..database.models import DataSourceType, DataSource, DataSourceMetric
from ..connectors.base import BaseDataConnector, ConnectorRegistry

logger = logging.getLogger(__name__)


@dataclass
class DataSourceInfo:
    """Data transfer object for data source information."""
    id: int
    name: str
    type_name: str
    type_display_name: str
    config: Dict[str, Any]
    ingestion_id: str
    enabled: bool
    status: str
    created_by: Optional[str] = None
    last_connection: Optional[str] = None
    last_error: Optional[str] = None


class DataSourceRegistry:
    """Registry for managing data source types and instances using SQLAlchemy ORM."""
    
    @property
    def CONNECTOR_TYPES(self) -> Dict[str, Any]:
        """Dynamically resolved from ConnectorRegistry (auto-discovered)."""
        return ConnectorRegistry.get_all()
    
    def __init__(self):
        self._initialized = False
    
    def init_builtin_types(self):
        """Initialize built-in connector types in database."""
        if self._initialized:
            return
            
        db: Session = next(get_db())
        try:
            for type_name, connector_class in self.CONNECTOR_TYPES.items():
                # Check if type already exists
                existing = db.query(DataSourceType).filter(
                    DataSourceType.name == type_name
                ).first()
                
                if not existing:
                    try:
                        display_info = connector_class.get_display_info()
                        config_schema = connector_class.get_config_schema()
                        
                        new_type = DataSourceType(
                            name=type_name,
                            display_name=display_info.get("name", type_name),
                            description=display_info.get("description", ""),
                            connector_class=f"{connector_class.__module__}.{connector_class.__name__}",
                            config_schema=config_schema
                        )
                        
                        db.add(new_type)
                        db.commit()
                        logger.info(f"✅ Registered connector type: {type_name}")
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to register connector type {type_name}: {e}")
                        db.rollback()
                else:
                    logger.debug(f"🔍 Connector type already exists: {type_name}")
            
            self._initialized = True
            
        finally:
            db.close()
    
    def get_available_types(self) -> List[Dict[str, Any]]:
        """Get all available data source types."""
        db: Session = next(get_db())
        try:
            types = db.query(DataSourceType).filter(DataSourceType.enabled == True).all()
            result = []
            
            for type_obj in types:
                type_dict = type_obj.to_dict()
                # Add display information from connector class
                if type_obj.name in self.CONNECTOR_TYPES:
                    connector_class = self.CONNECTOR_TYPES[type_obj.name]
                    display_info = connector_class.get_display_info()
                    type_dict.update(display_info)
                result.append(type_dict)
            
            return result
        finally:
            db.close()
    
    def _generate_config_hash(self, config: Dict[str, Any]) -> str:
        """Generate MD5 hash of configuration for duplicate detection."""
        # Convert config to sorted JSON string for consistent hashing
        config_str = json.dumps(config, sort_keys=True, separators=(',', ':'))
        return hashlib.md5(config_str.encode()).hexdigest()
    
    def create_data_source(self, name: str, type_name: str, config: Dict[str, Any], 
                          created_by: str = "system") -> int:
        """Create a new data source instance."""
        db: Session = next(get_db())
        try:
            # Get the data source type
            ds_type = db.query(DataSourceType).filter(
                DataSourceType.name == type_name
            ).first()
            
            if not ds_type:
                raise ValueError(f"Unknown data source type: {type_name}")
            
            # Check if a data source with the same name, type, and configuration already exists
            # Generate config hash for comparison (but don't store it)
            config_hash = self._generate_config_hash(config)
            
            existing_sources = db.query(DataSource).filter(
                DataSource.name == name,
                DataSource.type_id == ds_type.id
            ).all()
            
            # Check if any existing source has the same config by comparing hashes
            for existing in existing_sources:
                if self._generate_config_hash(existing.config) == config_hash:
                    logger.info(f"ℹ️ Data source already exists: {name} (ID: {existing.id})")
                    # Return existing source ID instead of creating duplicate
                    return existing.id
            
            # Validate configuration against schema
            if not self._validate_config(ds_type.config_schema, config):
                raise ValueError(f"Invalid configuration for {type_name}")
            
            # Generate unique ingestion_id
            ingestion_id = self._generate_ingestion_id(name, type_name)
            
            # Create new data source (without storing config_hash)
            new_source = DataSource(
                name=name,
                type_id=ds_type.id,
                config=config,
                ingestion_id=ingestion_id,
                created_by=created_by
            )
            
            db.add(new_source)
            db.commit()
            db.refresh(new_source)
            
            logger.info(f"✅ Created data source: {name} ({ingestion_id})")
            return new_source.id
            
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Failed to create data source: {e}")
            raise
        finally:
            db.close()
    
    def get_data_sources(self, enabled_only: bool = True) -> List[DataSourceInfo]:
        """Get all data sources."""
        db: Session = next(get_db())
        try:
            query = db.query(DataSource).join(DataSourceType)
            if enabled_only:
                query = query.filter(DataSource.enabled == True)
            
            sources = query.all()
            
            return [
                DataSourceInfo(
                    id=source.id,
                    name=source.name,
                    type_name=source.type.name,
                    type_display_name=source.type.display_name,
                    config=source.config,
                    ingestion_id=source.ingestion_id,
                    enabled=source.enabled,
                    status=source.status,
                    created_by=source.created_by,
                    last_connection=source.last_connection.isoformat() if source.last_connection else None,
                    last_error=source.last_error
                )
                for source in sources
            ]
        finally:
            db.close()
    
    def get_data_source_by_id(self, source_id: int) -> Optional[DataSourceInfo]:
        """Get a single data source by ID."""
        db: Session = next(get_db())
        try:
            source = db.query(DataSource).join(DataSourceType).filter(DataSource.id == source_id).first()
            
            if not source:
                return None
            
            return DataSourceInfo(
                id=source.id,
                name=source.name,
                type_name=source.type.name,
                type_display_name=source.type.display_name,
                config=source.config,
                ingestion_id=source.ingestion_id,
                enabled=source.enabled,
                status=source.status,
                created_by=source.created_by,
                last_connection=source.last_connection.isoformat() if source.last_connection else None,
                last_error=source.last_error
            )
        finally:
            db.close()
    
    def update_source_status(self, source_id: int, status: str, error: Optional[str] = None):
        """Update data source status."""
        db: Session = next(get_db())
        try:
            source = db.query(DataSource).filter(DataSource.id == source_id).first()
            if source:
                source.status = status
                source.last_error = error
                if status == "active":
                    source.last_connection = func.now()
                db.commit()
                logger.debug(f"🔍 Updated source {source_id} status to {status}")
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Failed to update source status: {e}")
        finally:
            db.close()
    
    def update_data_source(self, source_id: int, name: Optional[str] = None, 
                          config: Optional[Dict[str, Any]] = None, 
                          enabled: Optional[bool] = None) -> bool:
        """Update data source configuration."""
        db: Session = next(get_db())
        try:
            source = db.query(DataSource).filter(DataSource.id == source_id).first()
            if not source:
                return False
            
            if name is not None:
                source.name = name
            if config is not None:
                # Validate configuration if provided
                ds_type = db.query(DataSourceType).filter(DataSourceType.id == source.type_id).first()
                if ds_type and not self._validate_config(ds_type.config_schema, config):
                    raise ValueError("Invalid configuration")
                source.config = config
            if enabled is not None:
                source.enabled = enabled
            
            db.commit()
            logger.info(f"✅ Updated data source {source_id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Failed to update data source: {e}")
            raise
        finally:
            db.close()
    
    def delete_data_source(self, source_id: int) -> bool:
        """Delete a data source."""
        db: Session = next(get_db())
        try:
            source = db.query(DataSource).filter(DataSource.id == source_id).first()
            if not source:
                return False
            
            db.delete(source)
            db.commit()
            logger.info(f"✅ Deleted data source {source_id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Failed to delete data source: {e}")
            raise
        finally:
            db.close()
    
    def _validate_config(self, schema: Dict[str, Any], config: Dict[str, Any]) -> bool:
        """Validate configuration against JSON schema."""
        try:
            # Basic validation - check required fields
            if schema.get("required"):
                required_fields = schema["required"]
                if not all(field in config for field in required_fields):
                    return False
            
            # TODO: Use jsonschema library for full validation
            return True
        except Exception:
            return False
    
    def _generate_ingestion_id(self, name: str, type_name: str) -> str:
        """Generate unique ingestion ID."""
        # Sanitize name
        sanitized = re.sub(r"[^a-zA-Z0-9]+", "_", name.lower().strip())
        # Add type prefix and hash for uniqueness
        timestamp = int(datetime.utcnow().timestamp())
        unique_part = hashlib.md5(f"{name}_{type_name}_{timestamp}".encode()).hexdigest()[:8]
        return f"{unique_part}_{sanitized}_{type_name}"


class DataSourceManager:
    """Manages active data source connectors using SQLAlchemy ORM."""
    
    def __init__(self, registry: DataSourceRegistry, data_handler):
        self.registry = registry
        self.data_handler = data_handler
        self.active_connectors: Dict[str, BaseDataConnector] = {}
        self.logger = logging.getLogger(__name__)
    
    async def start_all_enabled_sources(self):
        """Start all enabled data sources."""
        self.logger.info("🚀 Starting all enabled data sources...")
        sources = self.registry.get_data_sources(enabled_only=True)
        
        started_count = 0
        for source in sources:
            if await self.start_source(source):
                started_count += 1
        
        self.logger.info(f"✅ Started {started_count}/{len(sources)} data sources")
    
    async def start_source(self, source: DataSourceInfo) -> bool:
        """Start a specific data source."""
        if source.ingestion_id in self.active_connectors:
            self.logger.warning(f"⚠️ Data source {source.name} is already running")
            return True
        
        try:
            # Get connector class
            connector_class = self.registry.CONNECTOR_TYPES.get(source.type_name)
            if not connector_class:
                raise ValueError(f"Unknown connector type: {source.type_name}")
            
            # Create and start connector
            connector = connector_class(
                source_id=source.ingestion_id,
                config=source.config,
                data_handler=self.data_handler
            )
            
            if await connector.start():
                self.active_connectors[source.ingestion_id] = connector
                self.registry.update_source_status(source.id, "active")
                self.logger.info(f"✅ Started data source: {source.name}")
                return True
            else:
                # Try to get more detailed error information from the connector
                try:
                    health_info = await connector.health_check()
                    error_detail = health_info.error if health_info.error else "Failed to start connector"
                except Exception:
                    error_detail = "Failed to start connector"
                
                self.registry.update_source_status(source.id, "error", error_detail)
                self.logger.error(f"❌ Failed to start data source: {source.name}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error starting data source {source.name}: {e}")
            self.registry.update_source_status(source.id, "error", str(e))
            return False
    
    async def stop_source(self, source_id: str) -> bool:
        """Stop a specific data source by ingestion_id."""
        if source_id in self.active_connectors:
            connector = self.active_connectors[source_id]
            await connector.stop()
            del self.active_connectors[source_id]
            self.logger.info(f"🛑 Stopped data source: {source_id}")
            return True
        
        self.logger.warning(f"⚠️ Data source not found or not running: {source_id}")
        return False
    
    async def restart_source(self, source: DataSourceInfo) -> bool:
        """Restart a specific data source."""
        # Stop if running
        await self.stop_source(source.ingestion_id)
        # Start again
        return await self.start_source(source)
    
    def get_connector_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all active connectors."""
        status = {}
        for source_id, connector in self.active_connectors.items():
            try:
                status[source_id] = {
                    "status": connector.status.value,
                    "type": connector.__class__.__name__,
                    "running": connector.is_running()
                }
            except Exception as e:
                status[source_id] = {"error": str(e)}
        
        return status
    
    async def get_connector_health(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Get health check for a specific connector."""
        if source_id in self.active_connectors:
            try:
                health_response = await self.active_connectors[source_id].health_check()
                return health_response.to_dict()
            except Exception as e:
                return {"error": str(e), "healthy": False, "status": "error", "running": False}
        return None
    
    async def shutdown_all(self):
        """Shutdown all active connectors."""
        self.logger.info("🛑 Shutting down all data source connectors...")
        
        for source_id in list(self.active_connectors.keys()):
            await self.stop_source(source_id)
        
        self.logger.info("✅ All connectors shut down")
