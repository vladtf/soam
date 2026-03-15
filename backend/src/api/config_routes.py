from src.api.models import ApiResponse
from src.api.response_utils import success_response, internal_server_error

"""
Configuration API routes for runtime settings.
"""
from typing import Dict, Any, List
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.spark.config import SparkConfig
from src.utils.logging import get_logger
from src.utils.api_utils import handle_api_errors
from src.auth.dependencies import require_admin

from .dependencies import SparkManagerDep, MinioClientDep, ConfigDep

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


@router.post("/config/enrichment/restart", response_model=ApiResponse, dependencies=[Depends(require_admin)])
@handle_api_errors("restart enrichment stream")
async def restart_enrichment_stream(spark_manager: SparkManagerDep) -> ApiResponse:
    """Restart the enrichment stream (admin only).

    Stops the current enrichment stream and starts a new one with the
    latest schema from the ingestor. Useful after schema evolution or
    checkpoint cleanup.
    """
    sm = spark_manager.streaming_manager
    if not sm or not sm.enrichment_manager:
        raise internal_server_error("Streaming manager not initialized")

    em = sm.enrichment_manager
    was_active = em.is_enrichment_active()

    em.stop_enrichment_stream()
    em.ingestor_client._schema_cache = None
    em.start_enrichment_stream()

    return success_response(
        data={
            "was_active": was_active,
            "is_active": em.is_enrichment_active(),
            "active_schema_fields": sorted(em._active_schema_fields) if em._active_schema_fields else [],
        },
        message="Enrichment stream restarted successfully",
    )


@router.post("/config/enrichment/reset", response_model=ApiResponse, dependencies=[Depends(require_admin)])
@handle_api_errors("reset enrichment pipeline")
async def reset_enrichment_pipeline(
    spark_manager: SparkManagerDep,
    config: ConfigDep,
    client: MinioClientDep,
) -> ApiResponse:
    """Reset the enrichment pipeline by clearing checkpoints and Silver data (admin only).

    Stops all streaming queries (enrichment + Gold), deletes their
    checkpoints and output data from MinIO, then restarts everything
    so the pipeline reprocesses all Bronze data from scratch.
    """
    from minio.deleteobjects import DeleteObject

    sm = spark_manager.streaming_manager
    if not sm or not sm.enrichment_manager:
        raise internal_server_error("Streaming manager not initialized")

    em = sm.enrichment_manager

    # 1. Stop all streams (Gold reads from Silver, so must stop first)
    sm._qm.stop_gracefully(sm.AVG_QUERY_NAME, timeout_seconds=5)
    sm._qm.stop_gracefully(sm.ALERT_QUERY_NAME, timeout_seconds=5)
    sm.avg_query = None
    sm.alert_query = None
    em.stop_enrichment_stream()
    logger.info("🛑 All streams stopped for pipeline reset")

    bucket = config.minio_bucket
    deleted_counts: Dict[str, int] = {}

    # 2. Delete all checkpoints and data
    prefixes_to_delete = {
        "enrichment_checkpoint": f"{SparkConfig.ENRICH_STREAM_CHECKPOINT}/",
        "gold_temp_avg_checkpoint": f"{SparkConfig.GOLD_TEMP_AVG_CHECKPOINT}_union/",
        "gold_alert_checkpoint": f"{SparkConfig.GOLD_ALERT_CHECKPOINT}_union/",
        "enriched_data": f"{SparkConfig.ENRICHED_PATH}/",
        "gold_temp_avg_data": f"{SparkConfig.GOLD_TEMP_AVG_PATH}/",
        "gold_alerts_data": f"{SparkConfig.GOLD_ALERTS_PATH}/",
    }

    for label, prefix in prefixes_to_delete.items():
        objs = list(client.list_objects(bucket, prefix=prefix, recursive=True))
        if objs:
            errors = list(client.remove_objects(bucket, [DeleteObject(o.object_name) for o in objs]))
            deleted_counts[label] = len(objs) - len(errors)
            logger.info("🗑️ Deleted %d files from %s", deleted_counts[label], prefix)
        else:
            deleted_counts[label] = 0

    # 3. Restart all streams
    em.ingestor_client._schema_cache = None
    em.start_enrichment_stream()
    logger.info("✅ Enrichment stream restarted after reset")

    # Gold streams will be restarted by the watchdog once Silver data is available

    return success_response(
        data={
            "deleted": deleted_counts,
            "is_active": em.is_enrichment_active(),
            "active_schema_fields": sorted(em._active_schema_fields) if em._active_schema_fields else [],
        },
        message="Full pipeline reset — reprocessing all Bronze data. Gold streams will auto-start when Silver data is available.",
    )
