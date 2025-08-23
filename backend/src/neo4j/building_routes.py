"""
Building-related API endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException, Query

from src.api.models import BuildingLocation, BuildingCreateNeo4j, ApiResponse, ApiListResponse
from src.api.response_utils import success_response, error_response, list_response, not_found_error, bad_request_error, internal_server_error
from src.api.dependencies import Neo4jManagerDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["buildings"])


@router.get("/buildings", response_model=ApiListResponse[BuildingLocation])
async def get_buildings(neo4j_manager: Neo4jManagerDep):
    """Get all buildings from the database."""
    try:
        buildings = neo4j_manager.get_buildings()
        return list_response(buildings, message="Buildings retrieved successfully")
    except Exception as e:
        logger.error(f"Error fetching buildings: {str(e)}")
        internal_server_error("Failed to retrieve buildings", str(e))


@router.post("/buildings", response_model=ApiResponse)
async def add_building(building: BuildingCreateNeo4j, neo4j_manager: Neo4jManagerDep):
    """Add a new building and its address to the database (Neo4j-backed)."""
    try:
        building_data = building.dict()
        res = neo4j_manager.add_building(building_data)
        return success_response(res, "Building added successfully")
    except ValueError as e:
        logger.error(f"Invalid data in add_building: {str(e)}")
        bad_request_error(str(e))
    except ConnectionError as e:
        logger.error(f"Database connection error in add_building: {str(e)}")
        internal_server_error("Database connection error", str(e))
    except Exception as e:
        logger.error(f"Error adding building: {str(e)}")
        internal_server_error("Failed to add building", str(e))


@router.delete("/buildings", response_model=ApiResponse)
async def delete_building(
    name: str = Query(..., description="Building name"),
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    neo4j_manager: Neo4jManagerDep = None,
):
    """Delete a building by name and coordinates. If only the relationship exists, remove it; cleanup orphan nodes."""
    try:
        neo4j_manager.delete_building(name=name, lat=lat, lng=lng)
        return success_response(None, "Building deleted successfully")
    except ValueError as e:
        logger.error(f"Invalid data in delete_building: {str(e)}")
        not_found_error(str(e))
    except ConnectionError as e:
        logger.error(f"Database connection error in delete_building: {str(e)}")
        internal_server_error("Database connection error", str(e))
    except Exception as e:
        logger.error(f"Error deleting building: {str(e)}")
        internal_server_error("Failed to delete building", str(e))
