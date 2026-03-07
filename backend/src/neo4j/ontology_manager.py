"""
Ontology Manager — high-level operations on the Neo4j knowledge graph.

Encapsulates ontology-specific business logic (e.g. registering a sensor
with default placement) so that API routes stay thin.
"""
import logging
from typing import Dict, Any, Optional

from src.neo4j.neo4j_manager import Neo4jManager

logger = logging.getLogger(__name__)


class OntologyManager:
    """Facade over Neo4jManager for ontology-level operations."""

    def __init__(self, neo4j: Neo4jManager, ontology=None) -> None:
        self._neo4j = neo4j
        self._ontology = ontology

    # ── Sensor registration ──────────────────────────────────────

    def register_sensor(
        self,
        sensor_id: str,
        sensor_type: Optional[str] = None,
        building: Optional[str] = None,
        street: Optional[str] = None,
        city: Optional[str] = None,
        country: Optional[str] = None,
    ) -> None:
        """Create a Sensor node and optionally link it into the building → address → city chain.

        If sensor_type is provided it is validated against the ontology
        (when available) and added as an additional Neo4j label.
        Location linking only occurs when *building* is supplied.
        Best-effort: failures are logged but never raised.
        """
        if sensor_type and self._ontology:
            if not self._ontology.is_valid_sensor_type(sensor_type):
                valid = self._ontology.get_class_names()
                logger.warning(
                    "⚠️ Sensor type '%s' not in ontology. Valid: %s", sensor_type, valid
                )

        try:
            self._neo4j.create_sensor_node(sensor_id)

            # Add sensor subclass label if provided
            if sensor_type:
                with self._neo4j.driver.session() as session:
                    session.run(
                        f"MATCH (s:Sensor {{sensorId: $sid}}) SET s:{sensor_type}",
                        sid=sensor_id,
                    )

            # Only link to building/city if building is provided
            if building:
                query = """
                MATCH (s:Sensor {sensorId: $sensor_id})
                MERGE (b:Building {name: $building})
                MERGE (s)-[:locatedIn]->(b)
                """
                params: Dict[str, Any] = {"sensor_id": sensor_id, "building": building}

                if street and city and country:
                    query += """
                    MERGE (a:Address {street: $street, city: $addr_city, country: $country})
                    MERGE (b)-[:hasAddress]->(a)
                    """
                    params.update(street=street, addr_city=city, country=country)

                    query += """
                    MERGE (sc:SmartCity {name: $city})
                    MERGE (a)-[:locatedIn]->(sc)
                    """
                    params["city"] = city

                with self._neo4j.driver.session() as session:
                    session.run(query, **params)

            logger.info(
                "📊 Sensor '%s' registered (type=%s, building=%s)",
                sensor_id, sensor_type, building,
            )
        except Exception as e:
            logger.warning(
                "⚠️ Failed to register sensor '%s' in ontology: %s",
                sensor_id, e,
            )
