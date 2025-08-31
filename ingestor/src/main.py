"""
FastAPI application with proper dependency injection for the SOAM ingestor.
"""
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.dependencies import get_config, get_minio_client, get_ingestor_state, get_metadata_service
from src.api.routers import data, health, metadata, data_sources
from src.logging_config import setup_logging
from src.middleware import RequestIdMiddleware
from src.database.database import init_database
from src.services.data_source_service import DataSourceRegistry, DataSourceManager
from src.connectors.base import DataMessage

# Configure structured logging once
setup_logging(service_name="ingestor", log_file="ingestor.log")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    """
    # Startup
    logger.info("Starting SOAM Ingestor...")
    
    # Initialize database
    logger.info("🗄️ Initializing database...")
    init_database()
    
    # Initialize dependencies manually (not through FastAPI DI in lifespan)
    try:
        config = get_config()
        minio_client = get_minio_client(config)
        state = get_ingestor_state(config)
        metadata_service = get_metadata_service()
        
        # Initialize data source system
        registry = DataSourceRegistry()
        registry.init_builtin_types()
        
        # Auto-register Local Simulators MQTT data source if it doesn't exist
        try:
            existing_sources = registry.get_data_sources(enabled_only=False)
            local_mqtt_exists = any(
                source.name == "Local Simulators MQTT" and source.type_name == "mqtt" 
                for source in existing_sources
            )
            
            if not local_mqtt_exists:
                logger.info("🔧 Auto-registering Local Simulators MQTT data source...")
                local_mqtt_config = {
                    "broker": "mosquitto",
                    "port": 1883,
                    "topics": ["smartcity/sensors/#"]
                }
                
                source_id = registry.create_data_source(
                    name="Local Simulators MQTT",
                    type_name="mqtt",
                    config=local_mqtt_config,
                    created_by="system_auto_register"
                )
                logger.info(f"✅ Auto-registered Local Simulators MQTT data source with ID: {source_id}")
                
                # Ensure it's enabled
                try:
                    from src.database.database import get_db
                    from src.database.models import DataSource
                    db = next(get_db())
                    try:
                        source = db.query(DataSource).filter(DataSource.id == source_id).first()
                        if source:
                            source.enabled = True
                            db.commit()
                            logger.info("✅ Auto-enabled Local Simulators MQTT data source")
                    finally:
                        db.close()
                except Exception as enable_error:
                    logger.warning(f"⚠️ Could not auto-enable Local Simulators MQTT: {enable_error}")
                    
            else:
                logger.info("ℹ️ Local Simulators MQTT data source already exists")
                
        except Exception as e:
            logger.error(f"⚠️ Failed to auto-register Local Simulators MQTT: {e}")
            # Continue startup even if auto-registration fails
        
        # Create data handler function for connectors
        def data_handler(message: DataMessage):
            """Handle data from any connector type."""
            try:
                # Process the standardized message
                logger.debug(f"📊 Processing message from source: {message.source_id}")
                
                # Ensure proper timestamp format
                from datetime import datetime, timezone
                
                # Use message timestamp if available, otherwise current time
                if message.timestamp and message.timestamp != 'timestamp':
                    try:
                        # Try to parse the timestamp if it's a string
                        if isinstance(message.timestamp, str):
                            timestamp = datetime.fromisoformat(message.timestamp.replace('Z', '+00:00'))
                        else:
                            timestamp = message.timestamp
                    except:
                        timestamp = datetime.now(timezone.utc)
                else:
                    timestamp = datetime.now(timezone.utc)
                
                # Convert DataMessage to the format expected by MinIO client
                # The MinIO client expects 'ingestion_id' and 'timestamp' as top-level fields
                payload = {
                    **message.data,  # Original sensor data
                    'ingestion_id': message.source_id,  # Required by MinIO client
                    'timestamp': timestamp.isoformat(),  # Required by MinIO client in ISO format
                    'source_type': message.metadata.get('source_type'),
                    'ingestion_timestamp': message.metadata.get('fetch_timestamp', timestamp.isoformat()),
                    # Add other useful metadata as top-level fields
                    **{k: v for k, v in message.metadata.items() if k not in ['source_type']}
                }
                
                # IMPORTANT: Add to partition buffer for legacy API compatibility
                # The backend devices API relies on /api/partitions which reads from these buffers
                state.get_partition_buffer(message.source_id).append(payload)
                logger.debug(f"📋 Added to partition buffer: {message.source_id}")
                
                # Use the same MinIO client as legacy system
                minio_client.add_row(payload)
                logger.debug(f"📥 Data stored to MinIO from {message.source_id}")
                
                # Extract metadata if metadata service is available
                if metadata_service:
                    metadata_service.process_data(payload)
                    logger.debug("🔍 Metadata extracted")
                
            except Exception as e:
                logger.error(f"❌ Error processing data message from {message.source_id}: {e}")
        
        manager = DataSourceManager(registry, data_handler)
        
        # Store in app state for shutdown access
        app.state.config = config
        app.state.minio_client = minio_client
        app.state.ingestor_state = state
        app.state.metadata_service = metadata_service
        app.state.data_source_registry = registry
        app.state.data_source_manager = manager
        
        # Initialize data source API dependencies
        data_sources.init_dependencies(registry, manager)
        
        logger.info("✅ All dependencies initialized successfully")
        
        # Start all enabled data sources
        await manager.start_all_enabled_sources()
        
        # Ensure Local Simulators MQTT is always started (if it exists and is enabled)
        try:
            sources = registry.get_data_sources(enabled_only=True)
            local_mqtt_source = next(
                (s for s in sources if s.name == "Local Simulators MQTT" and s.type_name == "mqtt"), 
                None
            )
            
            if local_mqtt_source:
                # Check if it's already running
                if local_mqtt_source.ingestion_id not in manager.active_connectors:
                    logger.info("🚀 Starting Local Simulators MQTT data source...")
                    await manager.start_source(local_mqtt_source)
                else:
                    logger.info("✅ Local Simulators MQTT is already running")
            else:
                logger.warning("⚠️ Local Simulators MQTT data source not found or not enabled")
                
        except Exception as e:
            logger.error(f"❌ Error ensuring Local Simulators MQTT is started: {e}")
        
        logger.info("🚀 SOAM Ingestor started successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize dependencies: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down SOAM Ingestor...")
    
    try:
        # Shutdown data source manager
        data_source_manager = getattr(app.state, 'data_source_manager', None)
        if data_source_manager:
            await data_source_manager.shutdown_all()
            logger.info("✅ Data source manager shut down")
        
        # Stop MQTT client (legacy)
        state = app.state.ingestor_state
        metadata_service = app.state.metadata_service
        
        if state.mqtt_handler:
            state.mqtt_handler.stop()
            logger.info("✅ MQTT client stopped successfully")
        
        # Shutdown metadata service
        if metadata_service:
            metadata_service.shutdown()
            logger.info("✅ Metadata service stopped successfully")
            
        # Flush any remaining MinIO data
        minio_client = app.state.minio_client
        if minio_client:
            minio_client.close()
            logger.info("✅ MinIO client closed successfully")
            
    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}")
    
    logger.info("🎯 Shutdown completed.")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    app = FastAPI(
        title="SOAM Ingestor",
        description="Data ingestion service for the Smart City Ontology and Analytics Management platform",
        version="1.0.0",
        lifespan=lifespan
    )
    app.add_middleware(RequestIdMiddleware)
    
    # Enable CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, replace with specific origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(data.router)
    app.include_router(health.router)
    app.include_router(metadata.router)
    app.include_router(data_sources.router)  # New data sources API
    
    return app


# Create the FastAPI app
app = create_app()


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with basic API information."""
    return {
        "message": "SOAM Ingestor API - Modular Data Source Platform",
        "version": "1.0.0",
        "features": [
            "Multi-source data ingestion (MQTT, REST API, etc.)",
            "Dynamic data source registration",
            "Real-time monitoring and health checks",
            "Extensible connector architecture"
        ],
        "endpoints": {
            "docs": "/docs",
            "health": "/api/health", 
            "metrics": "/api/metrics",
            "data_sources": "/api/data-sources",
            "data_source_types": "/api/data-sources/types"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
