"""
Health and monitoring API endpoints.
"""
import logging
from fastapi import APIRouter

from src.api.models import HealthStatus
from src.api.dependencies import SparkManagerDep, Neo4jManagerDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


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
            if neo4j_health["status"] == "healthy":
                health_status["components"]["neo4j"] = "healthy"
            else:
                health_status["components"]["neo4j"] = f"unhealthy: {neo4j_health['message']}"
                health_status["status"] = "degraded"
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
