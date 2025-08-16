"""
Health and monitoring API endpoints.
"""
import logging
from fastapi import APIRouter
from prometheus_client import generate_latest
from fastapi.responses import Response

from src.api.models import HealthStatus
from src.api.dependencies import IngestorStateDep, MinioClientDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/ready")
async def get_readiness_status(
    state: IngestorStateDep,
    minio_client: MinioClientDep
):
    """Readiness check endpoint - indicates if the ingestor is ready to receive data."""
    try:
        ready_status = {
            "ready": True,
            "checks": {
                "minio": False,
                "mqtt": False
            }
        }
        
        # Check MinIO connection (critical for data storage)
        try:
            minio_client.client.list_buckets()
            ready_status["checks"]["minio"] = True
        except Exception:
            ready_status["checks"]["minio"] = False
            ready_status["ready"] = False
        
        # Check MQTT connection (critical for data ingestion)
        try:
            if state.mqtt_handler and hasattr(state.mqtt_handler, 'client'):
                if state.mqtt_handler.client and state.mqtt_handler.client.is_connected():
                    ready_status["checks"]["mqtt"] = True
                else:
                    ready_status["checks"]["mqtt"] = False
                    ready_status["ready"] = False
            else:
                ready_status["checks"]["mqtt"] = False
                ready_status["ready"] = False
        except Exception:
            ready_status["checks"]["mqtt"] = False
            ready_status["ready"] = False
        
        return ready_status
        
    except Exception as e:
        logger.error(f"Error in readiness check: {str(e)}")
        return {
            "ready": False,
            "error": str(e)
        }


@router.get("/health", response_model=HealthStatus)
async def get_health_status(
    state: IngestorStateDep,
    minio_client: MinioClientDep
):
    """Health check endpoint to monitor ingestor status."""
    try:
        health_status = {
            "status": "healthy",
            "components": {
                "mqtt": "unknown",
                "minio": "unknown",
                "data_buffer": "unknown"
            },
            "metrics": {
                "buffered_messages": sum(len(b) for b in state.data_buffers.values()),
                "active_connections": len(state.connection_configs),
                "messages_received": state.messages_received._value._value,
                "messages_processed": state.messages_processed._value._value
            }
        }
        
        # Check MQTT connection
        try:
            if state.mqtt_handler and hasattr(state.mqtt_handler, 'client'):
                if state.mqtt_handler.client and state.mqtt_handler.client.is_connected():
                    health_status["components"]["mqtt"] = "connected"
                else:
                    health_status["components"]["mqtt"] = "disconnected"
                    health_status["status"] = "degraded"
            else:
                health_status["components"]["mqtt"] = "not_initialized"
                health_status["status"] = "degraded"
        except Exception as e:
            health_status["components"]["mqtt"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
        
        # Check MinIO connection
        try:
            # Try to list buckets to test connection
            minio_client.client.list_buckets()
            health_status["components"]["minio"] = "healthy"
        except Exception as e:
            health_status["components"]["minio"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
        
        # Check data buffer status
        try:
            buffer_size = sum(len(b) for b in state.data_buffers.values())
            if buffer_size < 100:  # Buffer not full
                health_status["components"]["data_buffer"] = "healthy"
            else:
                health_status["components"]["data_buffer"] = "full"
                # Not necessarily unhealthy, just indicates high load
        except Exception as e:
            health_status["components"]["data_buffer"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return {
            "status": "unhealthy",
            "components": {},
            "error": str(e)
        }


@router.get("/metrics")
async def get_metrics(state: IngestorStateDep):
    """Prometheus metrics endpoint."""
    try:
        return Response(generate_latest(), media_type="text/plain")
    except Exception as e:
        logger.error(f"Error generating metrics: {str(e)}")
        return Response("# Error generating metrics\n", media_type="text/plain")
