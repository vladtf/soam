"""
Ontology / knowledge-graph API endpoints.

Exposes the live Neo4j graph (cities, buildings, sensors and their
relationships) and allows creating nodes + linking them together.
Also provides a read-only Cypher query interface and schema introspection.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List

from src.api.models import ApiResponse
from src.api.response_utils import (
    success_response,
    bad_request_error,
    internal_server_error,
)
from src.api.dependencies import Neo4jManagerDep, OntologyServiceDep
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


class OntologyQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="Cypher query (read-only)")
    params: dict = Field(default_factory=dict, description="Query parameters")


class QueryTemplate(BaseModel):
    name: str
    description: str
    query: str
    params: List[str] = Field(default_factory=list, description="Parameter names used in query")


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


# ── Ontology schema ──────────────────────────────────────────────

@router.get("/schema", response_model=ApiResponse)
async def get_ontology_schema(ontology: OntologyServiceDep):
    """Return the parsed OWL schema (classes, properties, domains, ranges)."""
    try:
        schema = ontology.get_full_schema()
        return success_response(schema, "Ontology schema retrieved successfully")
    except Exception as e:
        logger.error("❌ Error fetching ontology schema: %s", e)
        raise internal_server_error("Failed to fetch ontology schema", str(e))


# ── Query templates ──────────────────────────────────────────────

_QUERY_TEMPLATES = [
    QueryTemplate(
        name="All Sensors",
        description="List every sensor in the graph",
        query="MATCH (s:Sensor) RETURN s.sensorId AS sensorId, labels(s) AS types",
        params=[],
    ),
    QueryTemplate(
        name="All Buildings",
        description="List every building with its address",
        query="MATCH (b:Building) OPTIONAL MATCH (b)-[:hasAddress]->(a:Address) RETURN b.name AS building, a.street AS street, a.city AS city, a.country AS country",
        params=[],
    ),
    QueryTemplate(
        name="Sensors in Building",
        description="Find sensors located in a specific building",
        query="MATCH (s:Sensor)-[:locatedIn]->(b:Building {name: $building}) RETURN s.sensorId AS sensor, b.name AS building",
        params=["building"],
    ),
    QueryTemplate(
        name="Sensor Context",
        description="Get the full location chain for a sensor",
        query=(
            "MATCH (s:Sensor {sensorId: $sensorId})"
            "-[:locatedIn]->(b:Building)"
            "-[:hasAddress]->(a:Address)"
            "-[:locatedIn]->(sc:SmartCity) "
            "RETURN s.sensorId AS sensor, b.name AS building, "
            "a.street AS street, a.city AS city, sc.name AS smartCity"
        ),
        params=["sensorId"],
    ),
    QueryTemplate(
        name="City Overview",
        description="All buildings and sensors in a city",
        query=(
            "MATCH (sc:SmartCity {name: $city})<-[:locatedIn]-(a:Address)"
            "<-[:hasAddress]-(b:Building)<-[:locatedIn]-(s:Sensor) "
            "RETURN sc.name AS city, b.name AS building, collect(s.sensorId) AS sensors"
        ),
        params=["city"],
    ),
    QueryTemplate(
        name="Buildings Without Sensors",
        description="Find buildings with no sensors installed",
        query="MATCH (b:Building) WHERE NOT (b)<-[:locatedIn]-(:Sensor) RETURN b.name AS building",
        params=[],
    ),
    QueryTemplate(
        name="Relationship Summary",
        description="Count relationships grouped by type",
        query="MATCH ()-[r]->() RETURN type(r) AS relType, count(r) AS count ORDER BY count DESC",
        params=[],
    ),
    QueryTemplate(
        name="Node Statistics",
        description="Count nodes grouped by label",
        query="MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS count ORDER BY count DESC",
        params=[],
    ),
]


@router.get("/query/templates", response_model=ApiResponse)
async def get_query_templates():
    """Return available query templates with descriptions."""
    return success_response(
        [t.model_dump() for t in _QUERY_TEMPLATES],
        "Query templates retrieved successfully",
    )


@router.post("/query", response_model=ApiResponse)
async def execute_query(body: OntologyQueryRequest, neo4j: Neo4jManagerDep):
    """Execute a read-only Cypher query against the knowledge graph."""
    try:
        results = neo4j.execute_read_query(body.query, body.params)
        return success_response(
            {"rows": results, "count": len(results)},
            f"Query returned {len(results)} rows",
        )
    except ValueError as e:
        raise bad_request_error(str(e))
    except ConnectionError as e:
        raise internal_server_error("Database connection unavailable", str(e))
    except Exception as e:
        logger.error("❌ Query execution error: %s", e)
        raise internal_server_error("Query execution failed", str(e))
