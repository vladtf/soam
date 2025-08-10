from neo4j import GraphDatabase
import logging
import time
from neo4j.exceptions import ServiceUnavailable, AuthError

logger = logging.getLogger(__name__)

class Neo4jManager:
    def __init__(self, uri, user, password):
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None
        self._connect_with_retry()

    def _connect_with_retry(self, max_retries=30, retry_delay=2):
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

    def _wait_for_database_ready(self, max_retries=30, retry_delay=2):
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

    def get_buildings(self):
        """Query Neo4j for all buildings with their address coordinates."""
        if not self.driver:
            logger.error("No database connection available")
            return []
        
        # If a building is linked to multiple addresses, pick the first deterministically to avoid duplicates in UI
        query = """
        MATCH (b:Building)-[:hasAddress]->(a:Address)
        WITH b, a ORDER BY a.location.latitude, a.location.longitude
        WITH b, head(collect(a)) AS a1
        RETURN b.name AS name, a1.location.latitude AS lat, a1.location.longitude AS lng
        """
        try:
            with self.driver.session() as session:
                result = session.run(query)
                buildings = [{"name": record["name"], "lat": record["lat"], "lng": record["lng"]} for record in result]

            logging.info("Fetched buildings from Neo4j. Count: %s", len(buildings))
            return buildings
        except Exception as e:
            logger.error(f"Error fetching buildings: {e}")
            return []

    def add_building(self, data):
        """Add a building and its address to Neo4j."""
        if not self.driver:
            return {"status": "error", "detail": "No database connection available"}
            
        query = """
        MERGE (b:Building { name: $name })
        SET b.description = $description
        MERGE (a:Address { street: $street, city: $city, country: $country })
        SET a.location = point({ latitude: $lat, longitude: $lng })
        MERGE (b)-[:hasAddress]->(a)
        RETURN b, a
        """
        logger.info("Adding building with data: %s", data)
        if not all(key in data for key in ["name", "description", "street", "city", "country", "lat", "lng"]):
            return {"status": "error", "detail": "Missing required fields"}
        try:
            with self.driver.session() as session:
                result = session.run(query, **data)
                record = result.single()
                if record is None:
                    return {"status": "No building added"}
                b = record["b"]
                a = record["a"]
                return {"status": "Building added", "building": dict(b), "address": dict(a)}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    def delete_building(self, name: str, lat: float, lng: float):
        """Delete a building-address link by name and coordinates. If building/address become orphaned, delete them too."""
        if not self.driver:
            return {"status": "error", "detail": "No database connection available"}

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
                    return {"status": "error", "detail": "Building/address not found"}
            return {"status": "Building deleted"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    def _clear_existing_data(self):
        """Clear existing test data to avoid conflicts."""
        if not self.driver:
            logger.warning("No database connection, skipping data clearing")
            return
            
        clear_queries = [
            "MATCH (n) WHERE n.name IN ['Metropolis', 'Corp EC', 'Corp ED', 'Centrul PRECIS'] OR n.sensorId = 'Sensor123' OR n.street = 'Splaiul Independenței, 313' DETACH DELETE n"
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
            """
            MERGE (sc:SmartCity { name: "Metropolis", description: "A smart city leveraging technology to improve quality of life." })
            """,
            """
            MERGE (corp_ec:Building { name: "Corp EC", description: "The central administrative building." })
            """,
            """
            MERGE (corp_ed:Building { name: "Corp ED", description: "The central administrative building." })
            """,
            """
            MERGE (c_precis:Building { name: "Centrul PRECIS", description: "The central administrative building." })
            """,
            """
            MERGE (a_corp_ec:Address { street: "Splaiul Independenței, 313", city: "Bucharest", country: "Romania",
                                         location: point({latitude: 44.435907, longitude: 26.047295}) })
            """,
            """
            MERGE (a_corp_ed:Address { street: "Splaiul Independenței, 313", city: "Bucharest", country: "Romania",
                                         location: point({latitude: 44.435751, longitude: 26.048120}) })
            """,
            """
            MERGE (a_c_precis:Address { street: "Splaiul Independenței, 313", city: "Bucharest", country: "Romania",
                                         location: point({latitude: 44.435013, longitude: 26.047758}) })
            """,
            """
            MERGE (s:Sensor { sensorId: "Sensor123", measurementTime: datetime("2023-10-14T12:00:00"),
                               temperature: 22.5, humidity: 45.0 })
            """,
                        """
                        MATCH (b:Building { name: "Corp EC" })
                        MATCH (a:Address)
                        WHERE a.street = "Splaiul Independenței, 313" AND a.city = "Bucharest" AND a.country = "Romania"
                            AND a.location.latitude = 44.435907 AND a.location.longitude = 26.047295
                        MERGE (b)-[:hasAddress]->(a)
                        """,
                        """
                        MATCH (b:Building { name: "Corp ED" })
                        MATCH (a:Address)
                        WHERE a.street = "Splaiul Independenței, 313" AND a.city = "Bucharest" AND a.country = "Romania"
                            AND a.location.latitude = 44.435751 AND a.location.longitude = 26.048120
                        MERGE (b)-[:hasAddress]->(a)
                        """,
                        """
                        MATCH (b:Building { name: "Centrul PRECIS" })
                        MATCH (a:Address)
                        WHERE a.street = "Splaiul Independenței, 313" AND a.city = "Bucharest" AND a.country = "Romania"
                            AND a.location.latitude = 44.435013 AND a.location.longitude = 26.047758
                        MERGE (b)-[:hasAddress]->(a)
                        """,
            """
            MATCH (sc:SmartCity)
            WHERE sc.name = "Metropolis"
            MATCH (s:Sensor)
            WHERE s.sensorId = "Sensor123"
            MERGE (sc)-[:hasSensor]->(s)
            """,
            """
            MATCH (s:Sensor)
            WHERE s.sensorId = "Sensor123"
            MATCH (b:Building)
            WHERE b.name = "Corp EC"
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

    def health_check(self):
        """Check if Neo4j connection is healthy."""
        try:
            if not self.driver:
                return {"status": "error", "message": "No database connection"}
            
            with self.driver.session() as session:
                result = session.run("RETURN 1 as test")
                record = result.single()
                if record and record["test"] == 1:
                    return {"status": "healthy", "message": "Neo4j connection is working"}
                else:
                    return {"status": "error", "message": "Unexpected response from database"}
        except Exception as e:
            return {"status": "error", "message": f"Database health check failed: {str(e)}"}
