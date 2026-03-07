"""
Alert API — serves aggregated alerts from all registered sources.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.models import ApiResponse
from src.api.response_utils import success_response, internal_server_error
from src.api.dependencies import get_neo4j_manager
from src.database.database import get_db
from src.database.models import User
from src.auth.dependencies import get_current_user
from src.neo4j.neo4j_manager import Neo4jManager
from src.services.alert_service import alert_service
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["alerts"])


@router.get("/alerts", response_model=ApiResponse)
def get_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    neo4j: Neo4jManager = Depends(get_neo4j_manager),
) -> ApiResponse:
    """Return all alerts for the current user from registered sources."""
    try:
        context = {
            "username": current_user.username,
            "user": current_user,
            "db": db,
            "neo4j": neo4j,
        }
        alerts = alert_service.collect(context)
        return success_response(alerts, f"{len(alerts)} alert(s)")
    except Exception as e:
        logger.error("❌ Error collecting alerts: %s", e)
        raise internal_server_error("Failed to collect alerts", str(e))
