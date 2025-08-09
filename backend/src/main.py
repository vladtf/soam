"""
FastAPI application with proper dependency injection for the SOAM smart city platform.
"""
import logging
import sys
from contextlib import asynccontextmanager
from collections import deque
from src.api import health_routes, feedback_routes
from src.api import minio_routes
from src.neo4j import building_routes
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.dependencies import get_spark_manager, get_neo4j_manager, get_config
from src.spark import spark_routes
from src.database import create_tables

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("backend.log")
    ]
)

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
    app.include_router(feedback_routes.router)
    
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
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
