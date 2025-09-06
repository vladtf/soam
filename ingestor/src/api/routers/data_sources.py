"""
API router for data source management.
Provides endpoints for managing data sources and their configurations.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging

from src.api.models import ApiResponse, ApiListResponse
from src.api.response_utils import success_response, list_response, error_response
from src.services.data_source_service import DataSourceRegistry, DataSourceManager, DataSourceInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data-sources", tags=["data-sources"])


class CreateDataSourceRequest(BaseModel):
    """Schema for creating a new data source."""
    name: str = Field(..., description="Display name for the data source")
    type_name: str = Field(..., description="Data source type (mqtt, rest_api, etc.)")
    config: Dict[str, Any] = Field(..., description="Type-specific configuration")
    enabled: bool = Field(True, description="Whether the data source should be enabled")
    created_by: str = Field("api", description="User who created this data source")


class UpdateDataSourceRequest(BaseModel):
    """Schema for updating a data source."""
    name: Optional[str] = Field(None, description="Updated display name")
    config: Optional[Dict[str, Any]] = Field(None, description="Updated configuration")
    enabled: Optional[bool] = Field(None, description="Updated enabled status")


class DataSourceResponse(BaseModel):
    """Schema for data source response."""
    id: int
    name: str
    type_name: str
    type_display_name: str
    config: Dict[str, Any]
    ingestion_id: str
    enabled: bool
    status: str
    created_by: Optional[str]
    last_connection: Optional[str]
    last_error: Optional[str]


class DataSourceTypeResponse(BaseModel):
    """Schema for data source type response."""
    id: int
    name: str
    display_name: str
    description: Optional[str]
    config_schema: Dict[str, Any]
    icon: Optional[str]
    category: Optional[str]
    supported_formats: Optional[List[str]]
    real_time: Optional[bool]


# Dependencies - these will be injected in main.py
_registry: Optional[DataSourceRegistry] = None
_manager: Optional[DataSourceManager] = None


def get_registry() -> DataSourceRegistry:
    """Get data source registry dependency."""
    if _registry is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Data source registry not initialized"
        )
    return _registry


def get_manager() -> DataSourceManager:
    """Get data source manager dependency."""
    if _manager is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Data source manager not initialized"
        )
    return _manager


def init_dependencies(registry: DataSourceRegistry, manager: DataSourceManager):
    """Initialize dependencies - called from main.py."""
    global _registry, _manager
    _registry = registry
    _manager = manager


@router.get("/types", response_model=ApiListResponse[DataSourceTypeResponse])
async def get_data_source_types(registry: DataSourceRegistry = Depends(get_registry)):
    """Get all available data source types."""
    try:
        types = registry.get_available_types()
        return list_response(types, "Data source types retrieved successfully")
    except Exception as e:
        logger.error(f"❌ Error getting data source types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve data source types: {str(e)}"
        )


@router.post("", response_model=ApiResponse[DataSourceResponse])
async def create_data_source(
    request: CreateDataSourceRequest,
    registry: DataSourceRegistry = Depends(get_registry)
):
    """Create a new data source."""
    try:
        source_id = registry.create_data_source(
            name=request.name,
            type_name=request.type_name,
            config=request.config,
            created_by=request.created_by
        )
        
        # Get the created data source
        source = registry.get_data_source_by_id(source_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created data source"
            )
        
        return success_response(source.__dict__, f"Data source '{request.name}' created successfully")
        
    except ValueError as e:
        logger.error(f"❌ Validation error creating data source: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Error creating data source: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create data source: {str(e)}"
        )


@router.get("", response_model=ApiListResponse[DataSourceResponse])
async def list_data_sources(
    enabled_only: bool = True,
    registry: DataSourceRegistry = Depends(get_registry)
):
    """List all data sources."""
    try:
        sources = registry.get_data_sources(enabled_only=enabled_only)
        return list_response([source.__dict__ for source in sources], f"Retrieved {len(sources)} data sources")
    except Exception as e:
        logger.error(f"❌ Error listing data sources: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list data sources: {str(e)}"
        )


@router.get("/{source_id}", response_model=ApiResponse[DataSourceResponse])
async def get_data_source(
    source_id: int,
    registry: DataSourceRegistry = Depends(get_registry)
):
    """Get a specific data source by ID."""
    try:
        source = registry.get_data_source_by_id(source_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Data source {source_id} not found"
            )
        
        return {
            "status": "success",
            "data": source.__dict__,
            "message": "Data source retrieved successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting data source {source_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve data source: {str(e)}"
        )


@router.put("/{source_id}", response_model=ApiResponse[DataSourceResponse])
async def update_data_source(
    source_id: int,
    request: UpdateDataSourceRequest,
    registry: DataSourceRegistry = Depends(get_registry)
):
    """Update a data source."""
    try:
        success = registry.update_data_source(
            source_id=source_id,
            name=request.name,
            config=request.config,
            enabled=request.enabled
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Data source {source_id} not found"
            )
        
        # Get the updated data source
        source = registry.get_data_source_by_id(source_id)
        return {
            "status": "success",
            "data": source.__dict__,
            "message": "Data source updated successfully"
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"❌ Validation error updating data source: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Error updating data source {source_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update data source: {str(e)}"
        )


@router.delete("/{source_id}")
async def delete_data_source(
    source_id: int,
    registry: DataSourceRegistry = Depends(get_registry)
):
    """Delete a data source."""
    try:
        success = registry.delete_data_source(source_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Data source {source_id} not found"
            )
        
        return {
            "status": "success",
            "message": "Data source deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting data source {source_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete data source: {str(e)}"
        )


@router.post("/{source_id}/start")
async def start_data_source(
    source_id: int,
    registry: DataSourceRegistry = Depends(get_registry),
    manager: DataSourceManager = Depends(get_manager)
):
    """Start a data source."""
    try:
        source = registry.get_data_source_by_id(source_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Data source {source_id} not found"
            )
        
        success = await manager.start_source(source)
        if success:
            return {
                "status": "success",
                "message": f"Data source '{source.name}' started successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start data source '{source.name}'"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error starting data source {source_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start data source: {str(e)}"
        )


@router.post("/{source_id}/stop")
async def stop_data_source(
    source_id: int,
    registry: DataSourceRegistry = Depends(get_registry),
    manager: DataSourceManager = Depends(get_manager)
):
    """Stop a data source."""
    try:
        source = registry.get_data_source_by_id(source_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Data source {source_id} not found"
            )
        
        success = await manager.stop_source(source.ingestion_id)
        registry.update_source_status(source_id, "stopped")
        
        return {
            "status": "success",
            "message": f"Data source '{source.name}' stopped successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error stopping data source {source_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop data source: {str(e)}"
        )


@router.post("/{source_id}/restart")
async def restart_data_source(
    source_id: int,
    registry: DataSourceRegistry = Depends(get_registry),
    manager: DataSourceManager = Depends(get_manager)
):
    """Restart a data source."""
    try:
        source = registry.get_data_source_by_id(source_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Data source {source_id} not found"
            )
        
        success = await manager.restart_source(source)
        if success:
            return {
                "status": "success",
                "message": f"Data source '{source.name}' restarted successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to restart data source '{source.name}'"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error restarting data source {source_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart data source: {str(e)}"
        )


@router.get("/{source_id}/health")
async def get_data_source_health(
    source_id: int,
    registry: DataSourceRegistry = Depends(get_registry),
    manager: DataSourceManager = Depends(get_manager)
):
    """Get data source health status."""
    try:
        source = registry.get_data_source_by_id(source_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Data source {source_id} not found"
            )
        
        health = await manager.get_connector_health(source.ingestion_id)
        if health is None:
            # Connector not running - provide detailed error info from database
            health = {
                "status": source.status,
                "healthy": source.status == "active",
                "message": source.last_error or "Connector not running",
                "last_error": source.last_error,
                "last_connection": source.last_connection
            }
        
        return {
            "status": "success",
            "data": health,
            "message": "Health check completed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error checking health for data source {source_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check health: {str(e)}"
        )


@router.get("/status/overview")
async def get_connector_status_overview(
    manager: DataSourceManager = Depends(get_manager)
):
    """Get overview of all active connector statuses."""
    try:
        status = manager.get_connector_status()
        return {
            "status": "success",
            "data": {
                "active_connectors": len(status),
                "connectors": status
            },
            "message": "Connector status overview retrieved"
        }
    except Exception as e:
        logger.error(f"❌ Error getting connector status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get connector status: {str(e)}"
        )
