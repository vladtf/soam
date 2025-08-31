from src.api.models import ApiResponse
from src.api.response_utils import success_response, internal_server_error

"""
Configuration API routes for runtime settings.
"""
from typing import Dict, Any
from fastapi import APIRouter
from pydantic import BaseModel

from src.spark.config import SparkConfig
from src.utils.logging import get_logger
from src.utils.api_utils import handle_api_errors

from .dependencies import SparkManagerDep

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["configuration"])


class SchemaConfigResponse(BaseModel):
    """Response model for schema configuration."""
    use_union_schema: bool
    schema_type: str
    message: str


class SchemaConfigRequest(BaseModel):
    """Request model for schema configuration."""
    use_union_schema: bool


@router.get("/config/schema", response_model=ApiResponse)
@handle_api_errors("get schema configuration")
async def get_schema_config(spark_manager: SparkManagerDep) -> ApiResponse:
    """
    Get current schema configuration.
    
    Returns:
        Current schema configuration (always union schema)
    """
    return success_response(
        data={
            "use_union_schema": True,
            "schema_type": "union"
        },
        message="Using union schema format for flexible data storage"
    )


@router.get("/config", response_model=ApiResponse)
@handle_api_errors("get system configuration")
async def get_system_config(spark_manager: SparkManagerDep) -> ApiResponse:
    """
    Get comprehensive system configuration.
    
    Returns:
        System configuration including schema, paths, and connection details
    """
    # Get Spark master status
    spark_status = spark_manager.get_spark_master_status()
    
    config_data = {
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
            "status": spark_status.status if spark_status else "unknown",
            "master_host": spark_status.url if spark_status else "unknown",
            "workers": [
                {
                    "id": worker.id,
                    "host": worker.host,
                    "cores": worker.cores,
                    "coresused": worker.coresused,
                    "state": worker.state
                } for worker in spark_status.workers
            ] if spark_status else []
        },
        "streaming": {
            "enrichment_active": (
                spark_manager.streaming_manager.enrichment_manager.is_enrichment_active() 
                if spark_manager.streaming_manager and spark_manager.streaming_manager.enrichment_manager 
                else False
            ),
            "temperature_active": (
                spark_manager.streaming_manager.avg_query.isActive 
                if spark_manager.streaming_manager and spark_manager.streaming_manager.avg_query 
                else False
            ),
            "alert_active": (
                spark_manager.streaming_manager.alert_query.isActive 
                if spark_manager.streaming_manager and spark_manager.streaming_manager.alert_query 
                else False
            )
        }
    }
    
    return success_response(
        data=config_data,
        message="System configuration retrieved successfully"
    )


@router.get("/config/features", response_model=Dict[str, Any])
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
