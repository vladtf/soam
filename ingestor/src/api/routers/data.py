"""
Data and connection management API endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException
from typing import List

from src.api.models import (
    ConnectionConfigCreate, 
    ConnectionConfig, 
    BrokerSwitchRequest,
    ConnectionsResponse,
    ApiResponse
)
from src.api.dependencies import IngestorStateDep, MinioClientDep
from src.config import ConnectionConfig as ConfigDataclass

logger = logging.getLogger(__name__)

router = APIRouter(tags=["data"])


@router.get("/data", response_model=List[dict])
async def get_data(state: IngestorStateDep):
    """Returns the buffered sensor data."""
    try:
        print(f"Fetching {len(state.data_buffer)} buffered rows")
        return list(state.data_buffer)
    except Exception as e:
        logger.error(f"Error fetching data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connections", response_model=ConnectionsResponse)
async def get_connections(state: IngestorStateDep):
    """Get all connection configurations."""
    try:
        print(f"Fetching {len(state.connection_configs)} connection configurations")
        return {
            "status": "success",
            "data": {
                "connections": [
                    {
                        "id": c.id,
                        "broker": c.broker,
                        "port": c.port,
                        "topic": c.topic,
                        "connectionType": c.connectionType
                    } for c in state.connection_configs
                ],
                "active": {
                    "id": state.active_connection.id,
                    "broker": state.active_connection.broker,
                    "port": state.active_connection.port,
                    "topic": state.active_connection.topic,
                    "connectionType": state.active_connection.connectionType
                } if state.active_connection else None
            }
        }
    except Exception as e:
        logger.error(f"Error fetching connections: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connections", response_model=ApiResponse)
async def add_connection(
    connection: ConnectionConfigCreate, 
    state: IngestorStateDep
):
    """Add a new connection configuration."""
    try:
        config_id = len(state.connection_configs) + 1
        new_config = ConfigDataclass(
            id=config_id,
            broker=connection.broker,
            port=connection.port,
            topic=connection.topic,
            connectionType=connection.connectionType
        )
        state.connection_configs.append(new_config)
        
        if state.active_connection is None:
            state.active_connection = new_config
            
        return {
            "status": "success",
            "data": {"id": config_id},
            "message": "Connection configuration added successfully"
        }
    except Exception as e:
        logger.error(f"Error adding connection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connections/switch", response_model=ApiResponse)
async def switch_broker(
    request: BrokerSwitchRequest, 
    state: IngestorStateDep
):
    """Switch the active broker."""
    try:
        target_id = request.id
        for config in state.connection_configs:
            if config.id == target_id:
                state.active_connection = config
                state.data_buffer.clear()
                
                # TODO: Restart MQTT client with new configuration
                # This would need to be handled in the application lifecycle
                
                return {
                    "status": "success",
                    "data": {
                        "id": config.id,
                        "broker": config.broker,
                        "port": config.port,
                        "topic": config.topic,
                        "connectionType": config.connectionType
                    },
                    "message": f"Switched to connection {target_id}"
                }
        
        raise HTTPException(
            status_code=404, 
            detail=f"Connection id {target_id} not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error switching broker: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
