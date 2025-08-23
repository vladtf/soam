"""
FastAPI application with proper dependency injection for the SOAM smart city platform.
"""
import logging
from contextlib import asynccontextmanager
from collections import deque
from src.api import health_routes, feedback_routes
from src.api import error_routes
from src.api import device_routes
from src.api import normalization_routes
from src.api import normalization_preview_routes
from src.api import dashboard_tiles_routes
from src.api import minio_routes
from src.api import config_routes
from src.api import settings_routes
from src.api import troubleshooting
from src.neo4j import building_routes
from src.computations import computation_routes
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.dependencies import get_spark_manager, get_neo4j_manager, get_config
from src.logging_config import setup_logging
from src.middleware import RequestIdMiddleware
from src.spark import spark_routes
from src.database import create_tables, ensure_rule_metrics_columns, ensure_rule_ownership_columns, ensure_computation_ownership_columns, ensure_device_ownership_columns
from src.spark.cleaner import DataCleaner
from src.spark.usage_tracker import NormalizationRuleUsageTracker
from src.api.settings_routes import ensure_default_settings

# Configure structured logging once
setup_logging(service_name="backend", log_file="backend.log")

logger = logging.getLogger(__name__)

# Global state for thread management (if needed for future features)
app_state = {
    "data_buffer": deque(maxlen=100),
    "connection_configs": [],
    "active_connection": None,
    "threads": {},
    "thread_counter": 1,
    "last_connection_error": None
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    """
    # Startup
    logger.info("Starting SOAM Smart City Backend...")

    # Initialize database tables
    try:
        create_tables()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise

    # Ensure metrics columns exist (idempotent)
    try:
        ensure_rule_metrics_columns()
    except Exception as e:
        logger.warning("Could not ensure normalization rule metrics columns: %s", e)

    # Ensure ownership columns exist (idempotent)
    try:
        ensure_rule_ownership_columns()
    except Exception as e:
        logger.warning("Could not ensure normalization rule ownership columns: %s", e)

    try:
        ensure_computation_ownership_columns()
    except Exception as e:
        logger.warning("Could not ensure computation ownership columns: %s", e)

    try:
        ensure_device_ownership_columns()
    except Exception as e:
        logger.warning("Could not ensure device ownership columns: %s", e)

    # Seed normalization rules (no-op if already present)
    try:
        inserted = DataCleaner.seed_normalization_rules()
        if inserted:
            logger.info("Seeded %d normalization rules", inserted)
    except Exception as e:
        logger.error("Error seeding normalization rules: %s", e)

    # Initialize default settings
    try:
        from src.database.database import SessionLocal
        from src.utils.settings_manager import settings_manager
        
        db = SessionLocal()
        try:
            ensure_default_settings(db)
            # Also ensure settings manager has fresh data
            settings_manager.clear_cache()
        finally:
            db.close()
    except Exception as e:
        logger.warning("Could not initialize default settings: %s", e)

    # Start background aggregator for normalization rule usage
    try:
        NormalizationRuleUsageTracker.start()
    except Exception as e:
        logger.warning("Could not start normalization usage aggregator: %s", e)

    # Initialize dependencies to ensure they're created
    try:
        config = get_config()
        spark_manager = get_spark_manager(config)
        neo4j_manager = get_neo4j_manager(config)
        logger.info("All dependencies initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize dependencies: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down SOAM Smart City Backend...")

    # Stop and join all threads stored in the map
    for key, thread in app_state["threads"].items():
        if thread.is_alive():
            logger.info(f"Stopping thread {key}")
            thread.join(timeout=5)  # join with timeout for safety

    # Clean shutdown of managers
    try:
        # Get cached instances for cleanup
        config = get_config()
        spark_manager = get_spark_manager(config)
        neo4j_manager = get_neo4j_manager(config)

        # Stop Spark streams and close manager
        if spark_manager:
            spark_manager.close()
            logger.info("SparkManager stopped successfully")

        # Close Neo4j connection
        if neo4j_manager:
            neo4j_manager.close()
            logger.info("Neo4jManager stopped successfully")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

    # Stop usage aggregator
    try:
        NormalizationRuleUsageTracker.stop()
    except Exception as e:
        logger.warning("Error stopping normalization usage aggregator: %s", e)

    logger.info("Shutdown completed.")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    app = FastAPI(
        title="SOAM Smart City Backend",
        description="Backend API for the Smart City Ontology and Analytics Management platform",
        version="1.0.0",
        lifespan=lifespan
    )
    # Request ID middleware and basic access logging
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
    app.include_router(building_routes.router)
    app.include_router(spark_routes.router)
    app.include_router(health_routes.router)
    app.include_router(minio_routes.router)
    app.include_router(device_routes.router)
    app.include_router(feedback_routes.router)
    app.include_router(normalization_routes.router)
    app.include_router(normalization_preview_routes.router)
    app.include_router(error_routes.router)
    app.include_router(computation_routes.router)
    app.include_router(dashboard_tiles_routes.router)
    app.include_router(config_routes.router)
    app.include_router(settings_routes.router)
    app.include_router(troubleshooting.router)

    return app


# Create the FastAPI app
app = create_app()


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with basic API information."""
    return {
        "message": "SOAM Smart City Backend API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
