"""
Ontology Manager — high-level operations on the Neo4j knowledge graph.

Encapsulates ontology-specific business logic (e.g. registering a sensor
with default placement) so that API routes stay thin.
"""
import logging
from typing import Dict, Any

from src.neo4j.neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)

# Hardcoded defaults — will be configurable in the future
_DEFAULT_BUILDING = "Corp EC"
_DEFAULT_ADDRESS: Dict[str, str] = {
    "street": "Splaiul Independenței, 313",
    "city": "Bucharest",
    "country": "Romania",
}
_DEFAULT_CITY = "Bucharest"


class OntologyManager:
    """Facade over Neo4jManager for ontology-level operations."""

    def __init__(self, neo4j: Neo4jManager) -> None:
        self._neo4j = neo4j

    # ── Sensor registration ──────────────────────────────────────

    def register_sensor(
        self,
        sensor_id: str,
        building: str | None = None,
        street: str | None = None,
        city: str | None = None,
        country: str | None = None,
    ) -> None:
        """Create a Sensor node and link it into the building → address → city chain.

        All parameters except *sensor_id* fall back to hardcoded defaults.
        Best-effort: failures are logged but never raised.
        """
        building = building or _DEFAULT_BUILDING
        street = street or _DEFAULT_ADDRESS["street"]
        city = city or _DEFAULT_CITY
        country = country or _DEFAULT_ADDRESS["country"]

        try:
            self._neo4j.create_sensor_node(sensor_id)

            query = """
            MATCH (s:Sensor {sensorId: $sensor_id})
            MERGE (b:Building {name: $building})
            MERGE (s)-[:locatedIn]->(b)
            MERGE (a:Address {street: $street, city: $addr_city, country: $country})
            MERGE (b)-[:hasAddress]->(a)
            MERGE (sc:SmartCity {name: $city})
            MERGE (a)-[:locatedIn]->(sc)
            """
            with self._neo4j.driver.session() as session:
                session.run(
                    query,
                    sensor_id=sensor_id,
                    building=building,
                    street=street,
                    addr_city=city,
                    country=country,
                    city=city,
                )
            logger.info(
                "📊 Sensor '%s' registered in ontology (building: %s)",
                sensor_id,
                building,
            )
        except Exception as e:
            logger.warning(
                "⚠️ Failed to register sensor '%s' in ontology: %s",
                sensor_id,
                e,
            )
