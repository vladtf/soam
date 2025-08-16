"""
Configuration API routes for runtime settings.
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter
from pydantic import BaseModel

from src.spark.config import SparkConfig

from .dependencies import SparkManagerDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["configuration"])


class SchemaConfigResponse(BaseModel):
    """Response model for schema configuration."""
    use_union_schema: bool
    schema_type: str
    message: str


class SchemaConfigRequest(BaseModel):
    """Request model for schema configuration."""
    use_union_schema: bool


@router.get("/schema", response_model=SchemaConfigResponse)
async def get_schema_config(spark_manager: SparkManagerDep) -> SchemaConfigResponse:
    """
    Get current schema configuration.
    
    Returns:
        Current schema configuration (always union schema)
    """
    try:
        return SchemaConfigResponse(
            use_union_schema=True,
            schema_type="union",
            message="Using union schema format for flexible data storage"
        )
    except Exception as e:
        logger.error(f"Error getting schema config: {e}")
        return SchemaConfigResponse(
            use_union_schema=True,
            schema_type="union",
            message="Using union schema format"
        )


@router.get("/", response_model=Dict[str, Any])
async def get_system_config(spark_manager: SparkManagerDep) -> Dict[str, Any]:
    """
    Get comprehensive system configuration.
    
    Returns:
        System configuration including schema, paths, and connection details
    """
    try:
        # Get Spark master status
        spark_status = spark_manager.get_spark_master_status()
        
        return {
            "schema": {
                "use_union_schema": True,
                "schema_type": "union"
            },
            "storage": {
                "minio_bucket": spark_manager.minio_bucket,
                "bronze_path": f"s3a://{spark_manager.minio_bucket}/{SparkConfig.BRONZE_PATH}/",
                "enriched_path": f"s3a://{spark_manager.minio_bucket}/{SparkConfig.ENRICHED_PATH}/",
                "gold_temp_avg_path": f"s3a://{spark_manager.minio_bucket}/{SparkConfig.GOLD_TEMP_AVG_PATH}/",
                "gold_alerts_path": f"s3a://{spark_manager.minio_bucket}/{SparkConfig.GOLD_ALERTS_PATH}/"
            },
            "spark": {
                "status": spark_status.get("status", "unknown"),
                "master_host": spark_status.get("master", "unknown"),
                "workers": spark_status.get("workers", [])
            },
            "streaming": {
                "enrichment_active": spark_manager.streaming_manager.enrich_query.isActive if spark_manager.streaming_manager.enrich_query else False,
                "temperature_active": spark_manager.streaming_manager.avg_query.isActive if spark_manager.streaming_manager.avg_query else False,
                "alert_active": spark_manager.streaming_manager.alert_query.isActive if spark_manager.streaming_manager.alert_query else False
            }
        }
    except Exception as e:
        logger.error(f"Error getting system config: {e}")
        return {
            "error": f"Failed to retrieve system configuration: {str(e)}"
        }


@router.get("/features", response_model=Dict[str, Any])
async def get_feature_flags() -> Dict[str, Any]:
    """
    Get current feature flags and capabilities.
    
    Returns:
        Available features and their status
    """
    return {
        "union_schema": {
            "available": True,
            "enabled": True,
            "description": "Flexible schema for multi-sensor data storage",
            "benefits": [
                "Store arbitrary sensor data as JSON strings",
                "Normalized data as typed values",
                "Schema evolution without breaking changes",
                "Ingestion-specific normalization rules"
            ]
        },
        "dynamic_normalization": {
            "available": True,
            "enabled": True,
            "description": "Ingestion-ID specific normalization rules"
        },
        "stream_processing": {
            "available": True,
            "enabled": True,
            "description": "Real-time data processing with Spark Streaming"
        },
        "multi_sensor_support": {
            "available": True,
            "enabled": True,
            "description": "Support for diverse sensor types without schema changes"
        }
    }
