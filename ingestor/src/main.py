"""
FastAPI application with proper dependency injection for the SOAM ingestor.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.dependencies import get_config, get_minio_client, get_ingestor_state, get_metadata_service
from src.api.routers import data, health, metadata, data_sources
from src.logging_config import setup_logging
from src.middleware import RequestIdMiddleware
from src.database.database import init_database
from src.services.data_source_service import DataSourceRegistry, DataSourceManager
from src.services.data_handler import create_data_handler
from src.services.auto_register import auto_register_default_sources
from src import metrics as ingestor_metrics

# Configure structured logging once
setup_logging(service_name="ingestor", log_file="ingestor.log")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    logger.info("Starting SOAM Ingestor...")

    # Initialize database
    logger.info("🗄️ Initializing database...")
    init_database()

    try:
        # ── Core dependencies ────────────────────────────────────
        config = get_config()
        minio_client = get_minio_client(config)
        state = get_ingestor_state(config)
        metadata_service = get_metadata_service()

        # ── Data source system ───────────────────────────────────
        registry = DataSourceRegistry()
        registry.init_builtin_types()
        auto_register_default_sources(registry)

        # ── Metrics & data handler ───────────────────────────────
        ingestor_metrics.init_metrics()
        handler = create_data_handler(minio_client, state, metadata_service)
        manager = DataSourceManager(registry, handler)

        # ── Store in app state ───────────────────────────────────
        app.state.config = config
        app.state.minio_client = minio_client
        app.state.ingestor_state = state
        app.state.metadata_service = metadata_service
        app.state.data_source_registry = registry
        app.state.data_source_manager = manager
        data_sources.init_dependencies(registry, manager)

        logger.info("✅ All dependencies initialized successfully")

        # ── Start connectors ─────────────────────────────────────
        await manager.start_all_enabled_sources()
        logger.info("🚀 SOAM Ingestor started successfully")

    except Exception as e:
        logger.error(f"❌ Failed to initialize dependencies: {e}")
        raise

    yield

    # ── Shutdown ─────────────────────────────────────────────────
    logger.info("🛑 Shutting down SOAM Ingestor...")
    try:
        if mgr := getattr(app.state, "data_source_manager", None):
            await mgr.shutdown_all()
            logger.info("✅ Data source manager shut down")

        st = app.state.ingestor_state
        if st.mqtt_handler:
            st.mqtt_handler.stop()
            logger.info("✅ MQTT client stopped successfully")

        ms = app.state.metadata_service
        if ms:
            ms.shutdown()
            logger.info("✅ Metadata service stopped successfully")

        mc = app.state.minio_client
        if mc:
            mc.close()
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
            "Multi-source data ingestion (MQTT, REST API, CoAP, etc.)",
            "Dynamic data source registration",
            "Real-time monitoring and health checks",
            "Extensible connector architecture with auto-discovery"
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
