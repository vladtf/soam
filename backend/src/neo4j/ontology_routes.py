"""
Ontology / knowledge-graph API endpoints.

Exposes the live Neo4j graph (cities, buildings, sensors and their
relationships) and allows creating nodes + linking them together.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from src.api.models import ApiResponse
from src.api.response_utils import (
    success_response,
    bad_request_error,
    internal_server_error,
)
from src.api.dependencies import Neo4jManagerDep
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/ontology", tags=["ontology"])


# ── Request models ───────────────────────────────────────────────

class CreateCityRequest(BaseModel):
    name: str = Field(..., min_length=1, description="City name")
    description: str = Field("", description="Optional description")


class CreateSensorNodeRequest(BaseModel):
    sensor_id: str = Field(..., min_length=1, description="Sensor identifier")


class LinkRequest(BaseModel):
    """Generic link between two named entities."""
    source_name: str = Field(..., min_length=1)
    target_name: str = Field(..., min_length=1)


class DeleteRelationshipRequest(BaseModel):
    source_id: str = Field(..., description="Element ID of the source node")
    target_id: str = Field(..., description="Element ID of the target node")
    rel_type: str = Field(..., description="Relationship type (e.g. locatedIn)")


class DeleteNodeRequest(BaseModel):
    node_id: str = Field(..., description="Element ID of the node to delete")


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/graph", response_model=ApiResponse)
async def get_graph(neo4j: Neo4jManagerDep):
    """Return the full knowledge graph (nodes + links)."""
    try:
        data = neo4j.get_graph()
        return success_response(data, "Graph retrieved successfully")
    except Exception as e:
        logger.error(f"❌ Error fetching graph: {e}")
        raise internal_server_error("Failed to fetch graph", str(e))


@router.post("/cities", response_model=ApiResponse)
async def create_city(body: CreateCityRequest, neo4j: Neo4jManagerDep):
    """Create a SmartCity node."""
    try:
        node = neo4j.create_city(body.name, body.description)
        return success_response(node, f"City '{body.name}' created")
    except Exception as e:
        logger.error(f"❌ Error creating city: {e}")
        raise internal_server_error("Failed to create city", str(e))


@router.post("/sensors", response_model=ApiResponse)
async def create_sensor_node(body: CreateSensorNodeRequest, neo4j: Neo4jManagerDep):
    """Create (or merge) a Sensor node in the graph."""
    try:
        node = neo4j.create_sensor_node(body.sensor_id)
        return success_response(node, f"Sensor node '{body.sensor_id}' created")
    except Exception as e:
        logger.error(f"❌ Error creating sensor node: {e}")
        raise internal_server_error("Failed to create sensor node", str(e))


@router.post("/link/building-city", response_model=ApiResponse)
async def link_building_to_city(body: LinkRequest, neo4j: Neo4jManagerDep):
    """Link a Building to a SmartCity via :locatedIn."""
    try:
        link = neo4j.link_building_to_city(body.source_name, body.target_name)
        return success_response(link, "Building linked to city")
    except ValueError as e:
        raise bad_request_error(str(e))
    except Exception as e:
        logger.error(f"❌ Error linking building→city: {e}")
        raise internal_server_error("Failed to link building to city", str(e))


@router.post("/link/sensor-building", response_model=ApiResponse)
async def link_sensor_to_building(body: LinkRequest, neo4j: Neo4jManagerDep):
    """Link a Sensor to a Building via :locatedIn."""
    try:
        link = neo4j.link_sensor_to_building(body.source_name, body.target_name)
        return success_response(link, "Sensor linked to building")
    except ValueError as e:
        raise bad_request_error(str(e))
    except Exception as e:
        logger.error(f"❌ Error linking sensor→building: {e}")
        raise internal_server_error("Failed to link sensor to building", str(e))


@router.post("/link/sensor-city", response_model=ApiResponse)
async def link_sensor_to_city(body: LinkRequest, neo4j: Neo4jManagerDep):
    """Link a Sensor to a SmartCity via :hasSensor."""
    try:
        link = neo4j.link_sensor_to_city(body.source_name, body.target_name)
        return success_response(link, "Sensor linked to city")
    except ValueError as e:
        raise bad_request_error(str(e))
    except Exception as e:
        logger.error(f"❌ Error linking sensor→city: {e}")
        raise internal_server_error("Failed to link sensor to city", str(e))


@router.delete("/relationship", response_model=ApiResponse)
async def delete_relationship(body: DeleteRelationshipRequest, neo4j: Neo4jManagerDep):
    """Delete a specific relationship."""
    try:
        neo4j.delete_relationship(body.source_id, body.target_id, body.rel_type)
        return success_response(None, "Relationship deleted")
    except Exception as e:
        logger.error(f"❌ Error deleting relationship: {e}")
        raise internal_server_error("Failed to delete relationship", str(e))


@router.delete("/node", response_model=ApiResponse)
async def delete_node(body: DeleteNodeRequest, neo4j: Neo4jManagerDep):
    """Delete a node and all its relationships."""
    try:
        neo4j.delete_node(body.node_id)
        return success_response(None, "Node deleted")
    except Exception as e:
        logger.error(f"❌ Error deleting node: {e}")
        raise internal_server_error("Failed to delete node", str(e))
