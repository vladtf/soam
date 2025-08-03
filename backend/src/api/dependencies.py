"""
Dependency injection for FastAPI.
"""
import os
import logging
from functools import lru_cache
from fastapi import Depends
from typing import Annotated

from src.spark import SparkManager
from src.neo4j.neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)


class AppConfig:
    """Application configuration."""

    def __init__(self):
        # Neo4j configuration
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "verystrongpassword")

        # Spark configuration
        self.spark_host = os.getenv("SPARK_HOST", "localhost")
        self.spark_port = os.getenv("SPARK_PORT", "7077")
        self.spark_ui_port = os.getenv("SPARK_UI_PORT", "8080")
        self.minio_endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
        self.minio_access_key = os.getenv("MINIO_ACCESS_KEY", "minio")
        self.minio_secret_key = os.getenv("MINIO_SECRET_KEY", "minio123")
        self.minio_bucket = os.getenv("MINIO_BUCKET", "lake")


@lru_cache()
def get_config() -> AppConfig:
    """Get application configuration (cached)."""
    return AppConfig()


@lru_cache()
def get_spark_manager(config: Annotated[AppConfig, Depends(get_config)]) -> SparkManager:
    """Get SparkManager instance (cached)."""
    return SparkManager(
        config.spark_host,
        config.spark_port,
        config.minio_endpoint,
        config.minio_access_key,
        config.minio_secret_key,
        config.minio_bucket,
        config.spark_ui_port,
    )


@lru_cache()
def get_neo4j_manager(config: Annotated[AppConfig, Depends(get_config)]) -> Neo4jManager:
    """Get Neo4jManager instance (cached)."""
    manager = Neo4jManager(config.neo4j_uri, config.neo4j_user, config.neo4j_password)
    # Provision data on first access
    try:
        manager.provision_data()
    except Exception as e:
        logger.warning(f"Failed to provision Neo4j data: {e}")
    return manager


# Type aliases for dependency injection
SparkManagerDep = Annotated[SparkManager, Depends(get_spark_manager)]
Neo4jManagerDep = Annotated[Neo4jManager, Depends(get_neo4j_manager)]
ConfigDep = Annotated[AppConfig, Depends(get_config)]
