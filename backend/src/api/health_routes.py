"""
Health and monitoring API endpoints.
"""
from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import generate_latest

from src.api.models import HealthStatus, ApiResponse
from src.api.dependencies import SparkManagerDep, Neo4jManagerDep
from src.api.response_utils import success_response, internal_server_error
from src.utils.logging import get_logger
from src.utils.api_utils import handle_api_errors
from src import metrics as backend_metrics

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/ready", response_model=ApiResponse)
async def get_readiness_status(
    spark_manager: SparkManagerDep,
    neo4j_manager: Neo4jManagerDep
):
    """Readiness check endpoint - indicates if the service is ready to serve traffic."""
    # For readiness, we need minimal functionality to be working
    ready_status = {
        "ready": True,
        "checks": {
            "neo4j": False,
            "spark_session": False,
            "database": False
        }
    }
    
    # Check Neo4j (critical for basic functionality)
    try:
        neo4j_health = neo4j_manager.health_check()
        ready_status["checks"]["neo4j"] = True  # If no exception, it's healthy
    except Exception as e:
        logger.error(f"Neo4j readiness check failed: {e}")
        ready_status["checks"]["neo4j"] = False
        ready_status["ready"] = False
    
    # Check Spark session (not streams, just session)
    try:
        if hasattr(spark_manager, 'session_manager'):
            ready_status["checks"]["spark_session"] = spark_manager.session_manager.is_connected()
        else:
            ready_status["checks"]["spark_session"] = False
            ready_status["ready"] = False
    except Exception as e:
        logger.error(f"Spark readiness check failed: {e}")
        ready_status["checks"]["spark_session"] = False
        ready_status["ready"] = False
    
    try:
        ready_status["checks"]["database"] = True
    except Exception as e:
        logger.error(f"Database readiness check failed: {e}")
        ready_status["checks"]["database"] = False
        ready_status["ready"] = False
    
    message = "Service is ready" if ready_status["ready"] else "Service is not ready"
    
    if not ready_status["ready"]:
        # Use internal_server_error for readiness failures
        raise internal_server_error(message, None)
    
    return success_response(
        data=ready_status,
        message=message
    )


@router.get("/health", response_model=HealthStatus)
async def get_health_status(
    spark_manager: SparkManagerDep,
    neo4j_manager: Neo4jManagerDep
):
    """Health check endpoint to monitor system status."""
    health_status = {
        "status": "healthy",
        "components": {
            "neo4j": "unknown",
            "spark": "unknown",
            "streams": {
                "temperature": "unknown",
                "alerts": "unknown"
            }
        }
    }
    
    try:
        neo4j_health = neo4j_manager.health_check()
        health_status["components"]["neo4j"] = "healthy"
    except Exception as e:
        logger.error(f"Neo4j health check failed: {e}")
        health_status["components"]["neo4j"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    try:
        if hasattr(spark_manager, 'session_manager') and spark_manager.session_manager.is_connected():
            health_status["components"]["spark"] = "healthy"
        else:
            health_status["components"]["spark"] = "unhealthy"
            health_status["status"] = "degraded"
    except Exception as e:
        logger.error(f"Spark health check failed: {e}")
        health_status["components"]["spark"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    try:
        if hasattr(spark_manager, 'streaming_manager'):
            streaming_mgr = spark_manager.streaming_manager
            
            if hasattr(streaming_mgr, 'avg_query') and streaming_mgr.avg_query:
                health_status["components"]["streams"]["temperature"] = "active" if streaming_mgr.avg_query.isActive else "inactive"
            else:
                health_status["components"]["streams"]["temperature"] = "not_started"
                
            if hasattr(streaming_mgr, 'alert_query') and streaming_mgr.alert_query:
                health_status["components"]["streams"]["alerts"] = "active" if streaming_mgr.alert_query.isActive else "inactive"
            else:
                health_status["components"]["streams"]["alerts"] = "not_started"
        else:
            health_status["components"]["streams"]["temperature"] = "not_available"
            health_status["components"]["streams"]["alerts"] = "not_available"
            
    except Exception as e:
        logger.error(f"Streams health check failed: {e}")
        health_status["components"]["streams"]["temperature"] = f"error: {str(e)}"
        health_status["components"]["streams"]["alerts"] = f"error: {str(e)}"
    
    return health_status


@router.get("/metrics")
async def get_metrics(spark_manager: SparkManagerDep):
    """Prometheus metrics endpoint."""
    try:
        # Update active streams metric before generating metrics
        try:
            spark = spark_manager.session_manager.spark
            active_stream_count = len(spark.streams.active)
            backend_metrics.update_active_streams(active_stream_count)
        except Exception as e:
            logger.debug(f"Could not update active streams metric: {e}")
        
        return Response(generate_latest(), media_type="text/plain")
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        return Response("# Error generating metrics\n", media_type="text/plain")
