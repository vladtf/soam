"""
FastAPI application with proper dependency injection for the SOAM ingestor.
"""
import logging
import sys
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.dependencies import get_config, get_minio_client, get_ingestor_state, get_metadata_service
from src.api.routers import data, health, metadata
from src.mqtt_client import MQTTClientHandler
from src.logging_config import setup_logging
from src.middleware import RequestIdMiddleware

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
    
    # Initialize dependencies manually (not through FastAPI DI in lifespan)
    try:
        config = get_config()
        minio_client = get_minio_client(config)
        state = get_ingestor_state(config)
        metadata_service = get_metadata_service()
        
        # Store in app state for shutdown access
        app.state.config = config
        app.state.minio_client = minio_client
        app.state.ingestor_state = state
        app.state.metadata_service = metadata_service
        
        logger.info("All dependencies initialized successfully")
        
        # Start MQTT client
        start_mqtt_client(state, minio_client, metadata_service)
        logger.info("MQTT client started successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize dependencies: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down SOAM Ingestor...")
    
    try:
        # Stop MQTT client
        state = app.state.ingestor_state
        metadata_service = app.state.metadata_service
        
        if state.mqtt_handler:
            state.mqtt_handler.stop()
            logger.info("MQTT client stopped successfully")
        
        # Shutdown metadata service
        if metadata_service:
            metadata_service.shutdown()
            logger.info("Metadata service stopped successfully")
            
        # Flush any remaining MinIO data
        minio_client = app.state.minio_client
        if minio_client:
            minio_client.close()
            logger.info("MinIO client closed successfully")
            
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    
    logger.info("Shutdown completed.")


def start_mqtt_client(state, minio_client, metadata_service):
    """Start the MQTT client in a separate thread."""
    if state.active_connection:
        state.mqtt_handler = MQTTClientHandler(
            broker=state.active_connection.broker,
            port=state.active_connection.port,
            topic=state.active_connection.topic,
            state=state,
            minio_client=minio_client,
            metadata_service=metadata_service,
            messages_received=state.messages_received,
            messages_processed=state.messages_processed,
            processing_latency=state.processing_latency,
        )
        # Start MQTT client in daemon thread
        mqtt_thread = threading.Thread(target=state.mqtt_handler.start, daemon=True)
        mqtt_thread.start()
        logger.info(f"MQTT client started for broker: {state.active_connection.broker}")


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
    
    return app


# Create the FastAPI app
app = create_app()


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with basic API information."""
    return {
        "message": "SOAM Ingestor API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/api/health",
        "metrics": "/api/metrics"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
