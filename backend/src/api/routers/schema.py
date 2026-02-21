"""
API routes for schema information and metadata.
"""
from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any
from src.api.models import ApiResponse
from src.api.response_utils import success_response, internal_server_error
from src.services.ingestor_schema_client import IngestorSchemaClient
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/schema", tags=["schema"])

# Initialize schema client
schema_client = IngestorSchemaClient()


@router.get("/datasets", response_model=ApiResponse)
async def get_all_datasets() -> ApiResponse:
    """Get all available datasets with their metadata."""
    try:
        datasets = await schema_client.get_all_datasets()
        return success_response(
            data=datasets,
            message=f"Retrieved {len(datasets)} datasets"
        )
    except Exception as e:
        logger.error("❌ Error fetching datasets: %s", e)
        raise internal_server_error("Failed to fetch datasets", str(e))


@router.get("/datasets/{ingestion_id}", response_model=ApiResponse)
async def get_dataset_schema(ingestion_id: str) -> ApiResponse:
    """Get schema information for a specific dataset."""
    try:
        schema_info = await schema_client.get_dataset_schema(ingestion_id)
        if schema_info is None:
            raise HTTPException(status_code=404, detail=f"Schema not found for ingestion_id: {ingestion_id}")
        
        return success_response(
            data=schema_info,
            message=f"Retrieved schema for {ingestion_id}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Error fetching schema for %s: %s", ingestion_id, e)
        raise internal_server_error(f"Failed to fetch schema for {ingestion_id}", str(e))


@router.get("/datasets/{ingestion_id}/evolution", response_model=ApiResponse)
async def get_schema_evolution(ingestion_id: str) -> ApiResponse:
    """Get schema evolution history for a dataset."""
    try:
        evolution = await schema_client.get_schema_evolution(ingestion_id)
        return success_response(
            data=evolution,
            message=f"Retrieved {len(evolution)} schema evolution entries for {ingestion_id}"
        )
    except Exception as e:
        logger.error("❌ Error fetching schema evolution for %s: %s", ingestion_id, e)
        raise internal_server_error(f"Failed to fetch schema evolution for {ingestion_id}", str(e))


@router.get("/topics", response_model=ApiResponse)
async def get_topics_summary() -> ApiResponse:
    """Get summary of all topics and their schemas."""
    try:
        summary = await schema_client.get_topics_summary()
        return success_response(
            data=summary,
            message="Retrieved topics summary"
        )
    except Exception as e:
        logger.error("❌ Error fetching topics summary: %s", e)
        raise internal_server_error("Failed to fetch topics summary", str(e))


@router.get("/context", response_model=ApiResponse)
async def get_data_context() -> ApiResponse:
    """Get comprehensive data context for all available datasets."""
    try:
        context = await schema_client.build_data_context()
        return success_response(
            data=context,
            message=f"Retrieved data context for {context.get('total_sources', 0)} sources"
        )
    except Exception as e:
        logger.error("❌ Error building data context: %s", e)
        raise internal_server_error("Failed to build data context", str(e))


@router.get("/sources", response_model=ApiResponse) 
async def get_available_sources() -> ApiResponse:
    """Get list of available ingestion IDs."""
    try:
        datasets = await schema_client.get_all_datasets()
        sources = [dataset.get("ingestion_id") for dataset in datasets if dataset.get("ingestion_id")]
        return success_response(
            data=sources,
            message=f"Retrieved {len(sources)} available sources"
        )
    except Exception as e:
        logger.error("❌ Error fetching available sources: %s", e)
        raise internal_server_error("Failed to fetch available sources", str(e))
