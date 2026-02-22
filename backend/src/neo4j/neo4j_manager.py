from neo4j import GraphDatabase
import logging
import time
from typing import List, Dict, Any, Optional
from neo4j.exceptions import ServiceUnavailable, AuthError
from cachetools import TTLCache, cached

logger = logging.getLogger(__name__)

# Shared TTL cache for health checks (1 entry, 5 second TTL)
_health_cache: TTLCache = TTLCache(maxsize=1, ttl=5.0)


def _sanitize_value(value: Any) -> Any:
    """Convert Neo4j-specific types to JSON-serializable Python types."""
    # neo4j.time.DateTime / Date / Time / Duration
    if hasattr(value, 'iso_format'):
        return value.iso_format()
    # neo4j.spatial.Point (has latitude/longitude or x/y)
    if hasattr(value, 'latitude') and hasattr(value, 'longitude'):
        return {"latitude": value.latitude, "longitude": value.longitude}
    if hasattr(value, 'x') and hasattr(value, 'y'):
        coords: Dict[str, Any] = {"x": value.x, "y": value.y}
        if hasattr(value, 'z') and value.z is not None:
            coords["z"] = value.z
        return coords
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_value(v) for v in value]
    return value


def _sanitize_props(props: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize all property values in a node/relationship properties dict."""
    return {k: _sanitize_value(v) for k, v in props.items()} if props else {}


class Neo4jManager:
    def __init__(self, uri: str, user: str, password: str) -> None:
        self.uri: str = uri
        self.user: str = user
        self.password: str = password
        self.driver = None
        self._connect_with_retry()

    def _connect_with_retry(self, max_retries: int = 30, retry_delay: int = 2) -> None:
        """Connect to Neo4j with retry logic for startup scenarios."""
        logger.info(f"Attempting to connect to Neo4j at {self.uri}")
        
        for attempt in range(max_retries):
            try:
                self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
                # Test the connection
                with self.driver.session() as session:
                    session.run("RETURN 1")
                logger.info("Successfully connected to Neo4j")
                return
            except (ServiceUnavailable, AuthError) as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Neo4j connection attempt {attempt + 1}/{max_retries} failed: {e}")
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Failed to connect to Neo4j after {max_retries} attempts")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error connecting to Neo4j: {e}")
                raise

    def _wait_for_database_ready(self, max_retries: int = 30, retry_delay: int = 2) -> bool:
        """Wait for the database to be ready for operations."""
        logger.info("Waiting for Neo4j database to be ready...")
        
        for attempt in range(max_retries):
            try:
                with self.driver.session() as session:
                    # Try a simple query to ensure the database is operational
                    session.run("MATCH (n) RETURN count(n) as count LIMIT 1")
                logger.info("Neo4j database is ready for operations")
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Database readiness check {attempt + 1}/{max_retries} failed: {e}")
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Database not ready after {max_retries} attempts")
                    return False
        
        return False

    def get_buildings(self) -> List[Dict[str, Any]]:
        """Query Neo4j for all buildings with their coordinates."""
        if not self.driver:
            logger.error("No database connection available")
            return []
        
        query: str = """
        MATCH (b:Building)
        WHERE b.location IS NOT NULL
        RETURN b.name AS name, b.location.latitude AS lat, b.location.longitude AS lng
        """
        try:
            with self.driver.session() as session:
                result = session.run(query)
                buildings: List[Dict[str, Any]] = [{"name": record["name"], "lat": record["lat"], "lng": record["lng"]} for record in result]

            logging.info("Fetched buildings from Neo4j. Count: %s", len(buildings))
            return buildings
        except Exception as e:
            logger.error(f"Error fetching buildings: {e}")
            return []

    def add_building(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a building and its address to Neo4j."""
        if not self.driver:
            raise ConnectionError("No database connection available")
            
        query = """
        MERGE (b:Building { name: $name })
        SET b.description = $description,
            b.location = point({ latitude: $lat, longitude: $lng })
        MERGE (a:Address { street: $street, city: $city, country: $country })
        MERGE (b)-[:hasAddress]->(a)
        RETURN b, a
        """
        logger.info("Adding building with data: %s", data)
        if not all(key in data for key in ["name", "description", "street", "city", "country", "lat", "lng"]):
            raise ValueError("Missing required fields")
        try:
            with self.driver.session() as session:
                result = session.run(query, **data)
                record = result.single()
                if record is None:
                    raise RuntimeError("No building added")
                b = record["b"]
                a = record["a"]
                return {"building": dict(b), "address": dict(a)}
        except Exception as e:
            if isinstance(e, (ConnectionError, ValueError, RuntimeError)):
                raise
            raise RuntimeError(f"Failed to add building: {str(e)}")

    def delete_building(self, name: str, lat: float, lng: float):
        """Delete a building-address link by name and coordinates. If building/address become orphaned, delete them too."""
        if not self.driver:
            raise ConnectionError("No database connection available")

        query = """
        MATCH (b:Building { name: $name })- [r:hasAddress] -> (a:Address)
        WHERE a.location.latitude = $lat AND a.location.longitude = $lng
        DELETE r
        WITH b, a
        OPTIONAL MATCH (b)-[:hasAddress]->()
        WITH b, a, COUNT(*) AS remain
        FOREACH (_ IN CASE WHEN remain = 0 THEN [1] ELSE [] END | DETACH DELETE b)
        WITH a
        OPTIONAL MATCH (:Building)-[:hasAddress]->(a)
        WITH a, COUNT(*) AS ref
        FOREACH (_ IN CASE WHEN ref = 0 THEN [1] ELSE [] END | DETACH DELETE a)
        RETURN true AS done
        """
        try:
            with self.driver.session() as session:
                result = session.run(query, name=name, lat=lat, lng=lng)
                rec = result.single()
                if rec is None:
                    raise ValueError("Building/address not found")
        except Exception as e:
            if isinstance(e, (ConnectionError, ValueError)):
                raise
            raise RuntimeError(f"Failed to delete building: {str(e)}")

    def _clear_existing_data(self):
        """Clear existing test data to avoid conflicts."""
        if not self.driver:
            logger.warning("No database connection, skipping data clearing")
            return
            
        clear_queries = [
            "MATCH (n) WHERE n.name IN ['Bucharest', 'Corp EC', 'Corp ED', 'Centrul PRECIS'] OR n.sensorId = 'Sensor123' OR n.street = 'Splaiul Independenței, 313' DETACH DELETE n"
        ]
        try:
            with self.driver.session() as session:
                for query in clear_queries:
                    session.run(query)
            logger.info("Existing test data cleared successfully.")
        except Exception as e:
            logger.warning(f"Error clearing existing data (this is normal on first run): {e}")

    def provision_data(self):
        """Provision Neo4j with initial data."""
        # Wait for database to be ready before provisioning
        if not self._wait_for_database_ready():
            logger.error("Database not ready, skipping data provisioning")
            return
        
        # First clear existing data to ensure clean state
        self._clear_existing_data()
        
        queries = [
            # City
            """
            MERGE (sc:SmartCity { name: "Bucharest" })
            SET sc.description = "The capital city of Romania, leveraging technology to improve quality of life."
            """,
            # Single shared address (MERGE on street+city+country only — NOT coordinates)
            """
            MERGE (a:Address { street: "Splaiul Independenței, 313", city: "Bucharest", country: "Romania" })
            """,
            # Buildings — each with its own lat/lng stored on the Building node
            """
            MERGE (b:Building { name: "Corp EC" })
            SET b.description = "The central administrative building.",
                b.location = point({latitude: 44.435907, longitude: 26.047295})
            """,
            """
            MERGE (b:Building { name: "Corp ED" })
            SET b.description = "The central administrative building.",
                b.location = point({latitude: 44.435751, longitude: 26.048120})
            """,
            """
            MERGE (b:Building { name: "Centrul PRECIS" })
            SET b.description = "The central administrative building.",
                b.location = point({latitude: 44.435013, longitude: 26.047758})
            """,
            # Sensor
            """
            MERGE (s:Sensor { sensorId: "Sensor123" })
            SET s.measurementTime = datetime("2023-10-14T12:00:00"),
                s.temperature = 22.5,
                s.humidity = 45.0
            """,
            # All buildings share the same Address
            """
            MATCH (b:Building) WHERE b.name IN ["Corp EC", "Corp ED", "Centrul PRECIS"]
            MATCH (a:Address { street: "Splaiul Independenței, 313", city: "Bucharest", country: "Romania" })
            MERGE (b)-[:hasAddress]->(a)
            """,
            # Link address to city
            """
            MATCH (a:Address { city: "Bucharest" })
            MATCH (sc:SmartCity { name: "Bucharest" })
            MERGE (a)-[:locatedIn]->(sc)
            """,
            # Sensor located in building (sensors attach to buildings, not cities)
            """
            MATCH (s:Sensor { sensorId: "Sensor123" })
            MATCH (b:Building { name: "Corp EC" })
            MERGE (s)-[:locatedIn]->(b)
            """
        ]
        try:
            with self.driver.session() as session:
                for query in queries:
                    session.run(query)
            logger.info("Neo4j data provisioned successfully.")
        except Exception as e:
            logger.error("Error provisioning Neo4j data: %s", e)
            raise

    def close(self):
        """Close the Neo4j driver."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")

    @cached(_health_cache)
    def health_check(self):
        """
        Check if Neo4j connection is healthy.
        
        Results are cached for 5 seconds to avoid frequent expensive queries.
        """
        if not self.driver:
            raise ConnectionError("No database connection")
        
        with self.driver.session() as session:
            result = session.run("RETURN 1 as test")
            record = result.single()
            if record and record["test"] == 1:
                return {"message": "Neo4j connection is working"}
            raise RuntimeError("Unexpected response from database")

    # ── Knowledge-graph helpers (ontology live data) ─────────────

    def get_graph(self) -> Dict[str, Any]:
        """Return every node and relationship in the database as a graph payload."""
        if not self.driver:
            return {"nodes": [], "links": []}

        query = """
        MATCH (n)
        OPTIONAL MATCH (n)-[r]->(m)
        RETURN collect(DISTINCT {
            id: elementId(n),
            labels: labels(n),
            props: properties(n)
        }) AS raw_nodes,
        collect(DISTINCT CASE WHEN r IS NOT NULL THEN {
            source: elementId(n),
            target: elementId(m),
            type: type(r)
        } END) AS raw_links
        """
        try:
            with self.driver.session() as session:
                record = session.run(query).single()
                # Deduplicate nodes by elementId
                seen_ids: set = set()
                nodes: List[Dict[str, Any]] = []
                for n in (record["raw_nodes"] or []):
                    if n and n["id"] not in seen_ids:
                        seen_ids.add(n["id"])
                        n["props"] = _sanitize_props(n.get("props", {}))
                        nodes.append(n)
                links = [l for l in (record["raw_links"] or []) if l is not None]
            return {"nodes": nodes, "links": links}
        except Exception as e:
            logger.error(f"❌ Error fetching graph: {e}")
            return {"nodes": [], "links": []}

    def create_city(self, name: str, description: str = "") -> Dict[str, Any]:
        """Create a SmartCity node."""
        if not self.driver:
            raise ConnectionError("No database connection available")
        query = """
        MERGE (c:SmartCity {name: $name})
        SET c.description = $description
        RETURN elementId(c) AS id, labels(c) AS labels, properties(c) AS props
        """
        with self.driver.session() as session:
            rec = session.run(query, name=name, description=description).single()
            if not rec:
                raise RuntimeError("Failed to create city")
            return {"id": rec["id"], "labels": rec["labels"], "props": _sanitize_props(rec["props"])}

    def link_building_to_city(self, building_name: str, city_name: str) -> Dict[str, Any]:
        """Create (Building)-[:locatedIn]->(SmartCity) relationship."""
        if not self.driver:
            raise ConnectionError("No database connection available")
        query = """
        MATCH (b:Building {name: $building_name})
        MATCH (c:SmartCity {name: $city_name})
        MERGE (b)-[r:locatedIn]->(c)
        RETURN elementId(b) AS source, elementId(c) AS target, type(r) AS type
        """
        with self.driver.session() as session:
            rec = session.run(query, building_name=building_name, city_name=city_name).single()
            if not rec:
                raise ValueError("Building or city not found")
            return {"source": rec["source"], "target": rec["target"], "type": rec["type"]}

    def link_sensor_to_building(self, sensor_id: str, building_name: str) -> Dict[str, Any]:
        """Create (Sensor)-[:locatedIn]->(Building) relationship."""
        if not self.driver:
            raise ConnectionError("No database connection available")
        query = """
        MATCH (s:Sensor {sensorId: $sensor_id})
        MATCH (b:Building {name: $building_name})
        MERGE (s)-[r:locatedIn]->(b)
        RETURN elementId(s) AS source, elementId(b) AS target, type(r) AS type
        """
        with self.driver.session() as session:
            rec = session.run(query, sensor_id=sensor_id, building_name=building_name).single()
            if not rec:
                raise ValueError("Sensor or building not found")
            return {"source": rec["source"], "target": rec["target"], "type": rec["type"]}

    def link_sensor_to_city(self, sensor_id: str, city_name: str) -> Dict[str, Any]:
        """Create (SmartCity)-[:hasSensor]->(Sensor) relationship."""
        if not self.driver:
            raise ConnectionError("No database connection available")
        query = """
        MATCH (s:Sensor {sensorId: $sensor_id})
        MATCH (c:SmartCity {name: $city_name})
        MERGE (c)-[r:hasSensor]->(s)
        RETURN elementId(c) AS source, elementId(s) AS target, type(r) AS type
        """
        with self.driver.session() as session:
            rec = session.run(query, sensor_id=sensor_id, city_name=city_name).single()
            if not rec:
                raise ValueError("Sensor or city not found")
            return {"source": rec["source"], "target": rec["target"], "type": rec["type"]}

    def create_sensor_node(self, sensor_id: str) -> Dict[str, Any]:
        """Create or merge a Sensor node in the graph."""
        if not self.driver:
            raise ConnectionError("No database connection available")
        query = """
        MERGE (s:Sensor {sensorId: $sensor_id})
        RETURN elementId(s) AS id, labels(s) AS labels, properties(s) AS props
        """
        with self.driver.session() as session:
            rec = session.run(query, sensor_id=sensor_id).single()
            if not rec:
                raise RuntimeError("Failed to create sensor node")
            return {"id": rec["id"], "labels": rec["labels"], "props": _sanitize_props(rec["props"])}

    def delete_relationship(self, source_id: str, target_id: str, rel_type: str) -> None:
        """Delete a specific relationship between two nodes."""
        if not self.driver:
            raise ConnectionError("No database connection available")
        query = f"""
        MATCH (a)-[r:{rel_type}]->(b)
        WHERE elementId(a) = $source_id AND elementId(b) = $target_id
        DELETE r
        """
        with self.driver.session() as session:
            session.run(query, source_id=source_id, target_id=target_id)

    def delete_node(self, node_id: str) -> None:
        """Delete a node and all its relationships by elementId."""
        if not self.driver:
            raise ConnectionError("No database connection available")
        query = """
        MATCH (n) WHERE elementId(n) = $node_id
        DETACH DELETE n
        """
        with self.driver.session() as session:
            session.run(query, node_id=node_id)
