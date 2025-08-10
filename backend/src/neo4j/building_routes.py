"""
Building-related API endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from typing import List

from src.api.models import BuildingLocation, BuildingCreateNeo4j, BuildingCreateResult, ApiResponse
from src.api.dependencies import Neo4jManagerDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/buildings", tags=["buildings"])


@router.get("/", response_model=List[BuildingLocation])
async def get_buildings(neo4j_manager: Neo4jManagerDep):
    """Get all buildings from the database."""
    try:
        return neo4j_manager.get_buildings()
    except Exception as e:
        logger.error(f"Error fetching buildings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=ApiResponse)
async def add_building(building: BuildingCreateNeo4j, neo4j_manager: Neo4jManagerDep):
    """Add a new building and its address to the database (Neo4j-backed)."""
    try:
        building_data = building.dict()
        res = neo4j_manager.add_building(building_data)
        # Normalize to ApiResponse shape for frontend doFetch()
        if isinstance(res, dict) and res.get("status") == "error":
            # surface as 400 so frontend sees detail
            raise HTTPException(status_code=400, detail=res.get("detail") or "Error adding building")
        payload = {
            "building": (res or {}).get("building") if isinstance(res, dict) else None,
            "address": (res or {}).get("address") if isinstance(res, dict) else None,
        }
        return {"status": "success", "data": payload, "message": (res or {}).get("status") if isinstance(res, dict) else None}
    except KeyError as e:
        logger.error(f"Missing field in add_building: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Missing field: {str(e)}")
    except Exception as e:
        logger.error(f"Error adding building: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/", response_model=ApiResponse)
async def delete_building(
    name: str = Query(..., description="Building name"),
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    neo4j_manager: Neo4jManagerDep = None,
):
    """Delete a building by name and coordinates. If only the relationship exists, remove it; cleanup orphan nodes."""
    try:
        res = neo4j_manager.delete_building(name=name, lat=lat, lng=lng)
        if res.get("status") == "error":
            raise HTTPException(status_code=400, detail=res.get("detail") or "Error deleting building")
        return {"status": "success", "data": {"message": res.get("status")}}
    except Exception as e:
        logger.error(f"Error deleting building: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
