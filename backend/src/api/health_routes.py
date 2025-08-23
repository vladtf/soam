"""
Health and monitoring API endpoints.
"""
import logging
from fastapi import APIRouter

from src.api.models import HealthStatus, ApiResponse
from src.api.dependencies import SparkManagerDep, Neo4jManagerDep
from src.api.response_utils import success_response, error_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/ready", response_model=ApiResponse)
async def get_readiness_status(
    spark_manager: SparkManagerDep,
    neo4j_manager: Neo4jManagerDep
):
    """Readiness check endpoint - indicates if the service is ready to serve traffic."""
    try:
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
        except Exception:
            ready_status["checks"]["neo4j"] = False
            ready_status["ready"] = False
        
        # Check Spark session (not streams, just session)
        try:
            if hasattr(spark_manager, 'session_manager'):
                ready_status["checks"]["spark_session"] = spark_manager.session_manager.is_connected()
            else:
                ready_status["checks"]["spark_session"] = False
                ready_status["ready"] = False
        except Exception:
            ready_status["checks"]["spark_session"] = False
            ready_status["ready"] = False
        
        # Check database (basic functionality)
        try:
            # Simple database check - this will be implemented based on your database setup
            ready_status["checks"]["database"] = True  # Assume database is ready for now
        except Exception:
            ready_status["checks"]["database"] = False
            ready_status["ready"] = False
        
        if ready_status["ready"]:
            return success_response(
                data=ready_status,
                message="Service is ready"
            )
        else:
            return error_response(
                message="Service is not ready",
                status_text="error"
            )
        
    except Exception as e:
        logger.error(f"Error in readiness check: {str(e)}")
        return error_response(
            message="Readiness check failed",
            detail=str(e)
        )


@router.get("/health", response_model=HealthStatus)
async def get_health_status(
    spark_manager: SparkManagerDep,
    neo4j_manager: Neo4jManagerDep
):
    """Health check endpoint to monitor system status."""
    try:
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
        
        # Check Neo4j
        try:
            neo4j_health = neo4j_manager.health_check()
            health_status["components"]["neo4j"] = "healthy"
        except Exception as e:
            health_status["components"]["neo4j"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
        
        # Check Spark connection through session manager
        try:
            if hasattr(spark_manager, 'session_manager') and spark_manager.session_manager.is_connected():
                health_status["components"]["spark"] = "healthy"
            else:
                health_status["components"]["spark"] = "unhealthy"
                health_status["status"] = "degraded"
        except Exception as e:
            health_status["components"]["spark"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"
        
        # Check Streams through streaming manager
        try:
            if hasattr(spark_manager, 'streaming_manager'):
                streaming_mgr = spark_manager.streaming_manager
                
                # Check temperature stream
                if hasattr(streaming_mgr, 'avg_query') and streaming_mgr.avg_query:
                    health_status["components"]["streams"]["temperature"] = "active" if streaming_mgr.avg_query.isActive else "inactive"
                else:
                    health_status["components"]["streams"]["temperature"] = "not_started"
                    
                # Check alert stream
                if hasattr(streaming_mgr, 'alert_query') and streaming_mgr.alert_query:
                    health_status["components"]["streams"]["alerts"] = "active" if streaming_mgr.alert_query.isActive else "inactive"
                else:
                    health_status["components"]["streams"]["alerts"] = "not_started"
            else:
                health_status["components"]["streams"]["temperature"] = "not_available"
                health_status["components"]["streams"]["alerts"] = "not_available"
                
        except Exception as e:
            health_status["components"]["streams"]["temperature"] = f"error: {str(e)}"
            health_status["components"]["streams"]["alerts"] = f"error: {str(e)}"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return {
            "status": "unhealthy", 
            "components": {},
            "error": str(e)
        }
