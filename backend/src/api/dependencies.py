"""Dependency injection for FastAPI."""
import os
from fastapi import Depends, Request
from typing import Annotated

from src.spark import SparkManager
from src.neo4j.neo4j_manager import Neo4jManager
from src.utils.logging import get_logger
from minio import Minio

logger = get_logger(__name__)


class AppConfig:
    """Application configuration loaded from environment variables."""

    def __init__(self):
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "verystrongpassword")

        self.spark_host = os.getenv("SPARK_HOST", "localhost")
        self.spark_port = os.getenv("SPARK_PORT", "7077")
        self.spark_ui_port = os.getenv("SPARK_UI_PORT", "8080")
        self.minio_endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
        self.minio_access_key = os.getenv("MINIO_ACCESS_KEY", "minio")
        self.minio_secret_key = os.getenv("MINIO_SECRET_KEY", "minio123")
        self.minio_bucket = os.getenv("MINIO_BUCKET", "lake")


# ------------------------------------------------------------------ #
# Singleton registry — populated during app lifespan, read by Depends
# ------------------------------------------------------------------ #

_config: AppConfig | None = None
_spark_manager: SparkManager | None = None
_neo4j_manager: Neo4jManager | None = None
_minio_client: Minio | None = None


def init_dependencies(config: AppConfig) -> None:
    """Create all singleton instances. Called once during app startup."""
    global _config, _spark_manager, _neo4j_manager, _minio_client
    _config = config

    _spark_manager = SparkManager(
        config.spark_host, config.spark_port,
        config.minio_endpoint, config.minio_access_key,
        config.minio_secret_key, config.minio_bucket,
        config.spark_ui_port,
    )

    _neo4j_manager = Neo4jManager(config.neo4j_uri, config.neo4j_user, config.neo4j_password)
    try:
        _neo4j_manager.provision_data()
    except Exception as e:
        logger.warning("⚠️ Failed to provision Neo4j data: %s", e)

    endpoint = config.minio_endpoint
    secure = False
    if endpoint.startswith("http://"):
        endpoint = endpoint[len("http://"):]
    elif endpoint.startswith("https://"):
        endpoint = endpoint[len("https://"):]
        secure = True
    _minio_client = Minio(endpoint, config.minio_access_key, config.minio_secret_key, secure=secure)

    logger.info("✅ All dependencies initialized")


def shutdown_dependencies() -> None:
    """Gracefully close all singletons. Called during app shutdown."""
    if _spark_manager:
        logger.info("🛑 Stopping SparkManager...")
        _spark_manager.close()
    if _neo4j_manager:
        logger.info("🛑 Stopping Neo4jManager...")
        _neo4j_manager.close()
    logger.info("✅ All dependencies shut down")


# ------------------------------------------------------------------ #
# FastAPI dependency getters
# ------------------------------------------------------------------ #

def get_config() -> AppConfig:
    assert _config is not None, "Dependencies not initialized — call init_dependencies() during startup"
    return _config


def get_spark_manager() -> SparkManager:
    assert _spark_manager is not None, "SparkManager not initialized"
    return _spark_manager


def get_neo4j_manager() -> Neo4jManager:
    assert _neo4j_manager is not None, "Neo4jManager not initialized"
    return _neo4j_manager


def get_minio_client() -> Minio:
    assert _minio_client is not None, "MinIO client not initialized"
    return _minio_client


# Type aliases for dependency injection
SparkManagerDep = Annotated[SparkManager, Depends(get_spark_manager)]
Neo4jManagerDep = Annotated[Neo4jManager, Depends(get_neo4j_manager)]
ConfigDep = Annotated[AppConfig, Depends(get_config)]
MinioClientDep = Annotated[Minio, Depends(get_minio_client)]
