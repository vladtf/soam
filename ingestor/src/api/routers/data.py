"""
Data and connection management API endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException
from typing import Optional

from src.api.models import (
    ApiResponse,
    ApiListResponse,
)
from src.api.response_utils import success_response, list_response
from src.api.dependencies import IngestorStateDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["data"])


@router.get("/data", response_model=ApiListResponse)
async def get_data(state: IngestorStateDep, limit_per_partition: Optional[int] = None):
    """Returns buffered sensor data across all partitions (optionally limited per partition)."""
    try:
        rows = state.all_data_flat(limit_per_partition=limit_per_partition)
        logger.debug("Fetched %d buffered rows across %d partitions", len(rows), len(state.data_buffers))
        return list_response(rows, f"Retrieved {len(rows)} sensor data records")
    except Exception as e:
        logger.error("Error fetching data: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/partitions", response_model=ApiListResponse)
async def list_partitions(state: IngestorStateDep):
    """List known ingestion_id partitions currently in buffer."""
    try:
        parts = sorted(state.data_buffers.keys())
        return list_response(parts, f"Retrieved {len(parts)} partitions")
    except Exception as e:
        logger.error("Error listing partitions: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data/{ingestion_id}", response_model=ApiListResponse)
async def get_data_by_partition(ingestion_id: str, state: IngestorStateDep):
    """Return buffered data for a specific ingestion_id partition."""
    try:
        buf = state.get_partition_buffer(ingestion_id)
        data = list(buf)
        return list_response(data, f"Retrieved {len(data)} records from partition {ingestion_id}")
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
                "note": "Using modular data source system"
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
        
        return success_response(
            data=analysis,
            message=f"Topic analysis completed - {len(state.data_buffers)} partitions analyzed, {total_messages_in_buffers} total messages in buffers"
        )
    except Exception as e:
        logger.error("Error in topic analysis: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/buffer/size", response_model=ApiResponse)
async def set_buffer_size(payload: dict, state: IngestorStateDep):
    """Set the maximum number of rows per partition buffer."""
    try:
        max_rows = int(payload.get("max_rows", 100))
        state.set_buffer_max_rows(max_rows)
        return success_response(data={"max_rows": state.buffer_max_rows})
    except Exception as e:
        logger.error("Error setting buffer size: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))
