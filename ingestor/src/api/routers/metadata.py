"""
Metadata API endpoints for dataset schema and statistics.
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional

from src.api.dependencies import MetadataServiceDep
from src.api.models import ApiResponse
from src.api.response_utils import success_response, error_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metadata", tags=["metadata"])


@router.get("/datasets", response_model=ApiResponse)
async def get_datasets(metadata_service: MetadataServiceDep) -> ApiResponse:
    """Get metadata for all datasets."""
    try:
        datasets = metadata_service.get_all_datasets()
        return success_response(
            data={"datasets": datasets, "total": len(datasets)},
            message=f"Retrieved metadata for {len(datasets)} datasets"
        )
    except Exception as e:
        logger.error(f"Error getting datasets: {e}")
        return error_response(f"Failed to retrieve datasets: {str(e)}")


@router.get("/datasets/{ingestion_id}", response_model=ApiResponse)
async def get_dataset(ingestion_id: str, metadata_service: MetadataServiceDep) -> ApiResponse:
    """Get metadata for a specific dataset."""
    try:
        dataset = metadata_service.get_dataset(ingestion_id)
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset '{ingestion_id}' not found")
        
        return success_response(
            data={"dataset": dataset},
            message=f"Retrieved metadata for dataset '{ingestion_id}'"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dataset {ingestion_id}: {e}")
        return error_response(f"Failed to retrieve dataset: {str(e)}")


@router.get("/datasets/{ingestion_id}/schema", response_model=ApiResponse)
async def get_dataset_schema(ingestion_id: str, metadata_service: MetadataServiceDep) -> ApiResponse:
    """Get schema information for a specific dataset."""
    try:
        dataset = metadata_service.get_dataset(ingestion_id)
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset '{ingestion_id}' not found")
        
        schema_fields = dataset.get("schema_fields", [])
        return success_response(
            data={
                "ingestion_id": ingestion_id,
                "schema_fields": schema_fields,
                "field_count": len(schema_fields)
            },
            message=f"Retrieved schema with {len(schema_fields)} fields for dataset '{ingestion_id}'"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting schema for dataset {ingestion_id}: {e}")
        return error_response(f"Failed to retrieve schema: {str(e)}")


@router.get("/datasets/{ingestion_id}/evolution", response_model=ApiResponse)
async def get_schema_evolution(ingestion_id: str, metadata_service: MetadataServiceDep) -> ApiResponse:
    """Get schema evolution history for a specific dataset."""
    try:
        evolution = metadata_service.get_schema_evolution(ingestion_id)
        return success_response(
            data={
                "ingestion_id": ingestion_id,
                "evolution": evolution,
                "change_count": len(evolution)
            },
            message=f"Retrieved {len(evolution)} schema evolution entries for dataset '{ingestion_id}'"
        )
    except Exception as e:
        logger.error(f"Error getting schema evolution for dataset {ingestion_id}: {e}")
        return error_response(f"Failed to retrieve schema evolution: {str(e)}")


@router.get("/topics", response_model=ApiResponse)
async def get_topics_summary(metadata_service: MetadataServiceDep) -> ApiResponse:
    """Get summary statistics by topic."""
    try:
        topics = metadata_service.get_topics_summary()
        return success_response(
            data={"topics": topics, "total": len(topics)},
            message=f"Retrieved summary for {len(topics)} topics"
        )
    except Exception as e:
        logger.error(f"Error getting topics summary: {e}")
        return error_response(f"Failed to retrieve topics summary: {str(e)}")


@router.get("/current", response_model=ApiResponse)
async def get_current_metadata(metadata_service: MetadataServiceDep) -> ApiResponse:
    """Get current in-memory metadata state."""
    try:
        current_metadata = metadata_service.get_current_metadata()
        return success_response(
            data={"current_metadata": current_metadata, "dataset_count": len(current_metadata)},
            message=f"Retrieved current metadata for {len(current_metadata)} datasets"
        )
    except Exception as e:
        logger.error(f"Error getting current metadata: {e}")
        return error_response(f"Failed to retrieve current metadata: {str(e)}")


@router.get("/datasets/{ingestion_id}/quality", response_model=ApiResponse)
async def get_quality_metrics(ingestion_id: str, metadata_service: MetadataServiceDep) -> ApiResponse:
    """Get data quality metrics for a specific dataset."""
    try:
        metrics = metadata_service.get_quality_metrics(ingestion_id)
        return success_response(
            data={
                "ingestion_id": ingestion_id,
                "metrics": metrics,
                "metric_count": len(metrics)
            },
            message=f"Retrieved {len(metrics)} quality metrics for dataset '{ingestion_id}'"
        )
    except Exception as e:
        logger.error(f"Error getting quality metrics for dataset {ingestion_id}: {e}")
        return error_response(f"Failed to retrieve quality metrics: {str(e)}")


@router.post("/datasets/{ingestion_id}/quality", response_model=ApiResponse)
async def store_quality_metric(
    ingestion_id: str, 
    metric_data: Dict[str, Any],
    metadata_service: MetadataServiceDep
) -> ApiResponse:
    """Store a data quality metric for a dataset."""
    try:
        metric_name = metric_data.get("metric_name")
        metric_value = metric_data.get("metric_value")
        
        if not metric_name or metric_value is None:
            raise HTTPException(
                status_code=400, 
                detail="Both 'metric_name' and 'metric_value' are required"
            )
        
        metadata_service.store_quality_metric(ingestion_id, metric_name, float(metric_value))
        
        return success_response(
            data={
                "ingestion_id": ingestion_id,
                "metric_name": metric_name,
                "metric_value": metric_value
            },
            message=f"Stored quality metric '{metric_name}' for dataset '{ingestion_id}'"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error storing quality metric for dataset {ingestion_id}: {e}")
        return error_response(f"Failed to store quality metric: {str(e)}")


@router.post("/cleanup", response_model=ApiResponse)
async def cleanup_old_data(
    metadata_service: MetadataServiceDep,
    days_to_keep: Optional[int] = 30
) -> ApiResponse:
    """Clean up old metadata records."""
    try:
        deleted_count = metadata_service.cleanup_old_data(days_to_keep)
        return success_response(
            data={"deleted_count": deleted_count, "days_to_keep": days_to_keep},
            message=f"Cleaned up {deleted_count} old records (kept last {days_to_keep} days)"
        )
    except Exception as e:
        logger.error(f"Error cleaning up old data: {e}")
        return error_response(f"Failed to clean up old data: {str(e)}")


@router.get("/stats", response_model=ApiResponse)
async def get_metadata_stats(metadata_service: MetadataServiceDep) -> ApiResponse:
    """Get overall metadata statistics."""
    try:
        # Get all datasets
        datasets = metadata_service.get_all_datasets()
        topics = metadata_service.get_topics_summary()
        current_metadata = metadata_service.get_current_metadata()
        
        # Calculate aggregate stats
        total_records = sum(dataset.get("record_count", 0) for dataset in datasets)
        total_size_bytes = sum(dataset.get("data_size_bytes", 0) for dataset in datasets)
        total_unique_sensors = sum(dataset.get("unique_sensor_count", 0) for dataset in datasets)
        
        stats = {
            "dataset_count": len(datasets),
            "topic_count": len(topics),
            "active_datasets": len(current_metadata),
            "total_records": total_records,
            "total_size_bytes": total_size_bytes,
            "total_unique_sensors": total_unique_sensors,
            "size_mb": round(total_size_bytes / (1024 * 1024), 2) if total_size_bytes > 0 else 0
        }
        
        return success_response(
            data={"stats": stats},
            message="Retrieved metadata statistics"
        )
    except Exception as e:
        logger.error(f"Error getting metadata stats: {e}")
        return error_response(f"Failed to retrieve metadata stats: {str(e)}")
