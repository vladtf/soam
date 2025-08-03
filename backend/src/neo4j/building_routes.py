"""
Building-related API endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException
from typing import List

from src.api.models import Building, BuildingCreate, BuildingLocation
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


@router.post("/", response_model=Building)
async def add_building(building: BuildingCreate, neo4j_manager: Neo4jManagerDep):
    """Add a new building to the database."""
    try:
        building_data = building.dict()
        return neo4j_manager.add_building(building_data)
    except KeyError as e:
        logger.error(f"Missing field in add_building: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Missing field: {str(e)}")
    except Exception as e:
        logger.error(f"Error adding building: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
