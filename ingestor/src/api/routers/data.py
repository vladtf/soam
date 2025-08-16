"""
Data and connection management API endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException
from typing import List, Optional

from src.api.models import (
    ConnectionConfigCreate,
    ConnectionConfig,
    BrokerSwitchRequest,
    ConnectionsResponse,
    ApiResponse,
)
from src.api.dependencies import IngestorStateDep, MinioClientDep
from src.config import ConnectionConfig as ConfigDataclass

logger = logging.getLogger(__name__)

router = APIRouter(tags=["data"])


@router.get("/data", response_model=List[dict])
async def get_data(state: IngestorStateDep, limit_per_partition: Optional[int] = None):
    """Returns buffered sensor data across all partitions (optionally limited per partition)."""
    try:
        rows = state.all_data_flat(limit_per_partition=limit_per_partition)
        logger.debug("Fetched %d buffered rows across %d partitions", len(rows), len(state.data_buffers))
        return rows
    except Exception as e:
        logger.error("Error fetching data: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/partitions", response_model=List[str])
async def list_partitions(state: IngestorStateDep):
    """List known ingestion_id partitions currently in buffer."""
    try:
        parts = sorted(state.data_buffers.keys())
        return parts
    except Exception as e:
        logger.error("Error listing partitions: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/{ingestion_id}", response_model=List[dict])
async def get_data_by_partition(ingestion_id: str, state: IngestorStateDep):
    """Return buffered data for a specific ingestion_id partition."""
    try:
        buf = state.get_partition_buffer(ingestion_id)
        return list(buf)
    except Exception as e:
        logger.error("Error fetching partition data: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/diagnostics/topic-analysis", response_model=ApiResponse)
async def get_topic_analysis(state: IngestorStateDep):
    """Analyze what topics and ingestion_ids are being received for debugging."""
    try:
        analysis = {
            "total_partitions": len(state.data_buffers),
            "partitions": {},
            "topic_to_ingestion_id_mapping": {},
            "sensor_types_by_partition": {},
            "buffer_status": {
                "max_rows_per_partition": state.buffer_max_rows,
                "active_connections": 1 if state.active_connection else 0,
                "mqtt_handler_active": state.mqtt_handler is not None
            }
        }
        
        total_messages_in_buffers = 0
        for ingestion_id, buffer in state.data_buffers.items():
            buffer_length = len(buffer)
            total_messages_in_buffers += buffer_length
            
            if buffer_length > 0:
                # Analyze this partition
                recent_msgs = list(buffer)[-10:]  # Last 10 messages
                topics = set()
                sensor_ids = set()
                
                for msg in recent_msgs:
                    if "topic" in msg:
                        topics.add(msg["topic"])
                    if "sensor_id" in msg:
                        sensor_ids.add(msg["sensor_id"])
                    elif "sensorId" in msg:
                        sensor_ids.add(msg["sensorId"])
                
                analysis["partitions"][ingestion_id] = {
                    "message_count": buffer_length,
                    "topics_seen": list(topics),
                    "sensor_ids_seen": list(sensor_ids),
                    "sample_recent_messages": recent_msgs[-3:]  # Last 3 for debugging
                }
                
                # Build topic mapping
                for topic in topics:
                    if topic not in analysis["topic_to_ingestion_id_mapping"]:
                        analysis["topic_to_ingestion_id_mapping"][topic] = []
                    if ingestion_id not in analysis["topic_to_ingestion_id_mapping"][topic]:
                        analysis["topic_to_ingestion_id_mapping"][topic].append(ingestion_id)
            else:
                # Include empty partitions for debugging
                analysis["partitions"][ingestion_id] = {
                    "message_count": 0,
                    "topics_seen": [],
                    "sensor_ids_seen": [],
                    "sample_recent_messages": [],
                    "status": "empty_buffer"
                }
        
        analysis["buffer_status"]["total_messages_in_buffers"] = total_messages_in_buffers
        
        # Add MQTT connection info if available
        if state.active_connection:
            analysis["buffer_status"]["active_broker"] = f"{state.active_connection.broker}:{state.active_connection.port}"
            analysis["buffer_status"]["subscribed_topic"] = state.active_connection.topic
        
        return {
            "status": "success",
            "data": analysis,
            "message": f"Topic analysis completed - {len(state.data_buffers)} partitions analyzed, {total_messages_in_buffers} total messages in buffers"
        }
    except Exception as e:
        logger.error("Error in topic analysis: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/buffer/size", response_model=ApiResponse)
async def set_buffer_size(payload: dict, state: IngestorStateDep):
    """Set the maximum number of rows per partition buffer."""
    try:
        max_rows = int(payload.get("max_rows", 100))
        state.set_buffer_max_rows(max_rows)
        return {"status": "success", "data": {"max_rows": state.buffer_max_rows}}
    except Exception as e:
        logger.error("Error setting buffer size: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/connections", response_model=ConnectionsResponse)
async def get_connections(state: IngestorStateDep):
    """Get all connection configurations."""
    try:
        logger.debug(
            "Fetching %d connection configurations", len(state.connection_configs)
        )
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
                state.clear_all_buffers()
                
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
