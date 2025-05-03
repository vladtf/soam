from neo4j import GraphDatabase
import logging


class Neo4jManager:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def get_buildings(self):
        """Query Neo4j for all buildings with their address coordinates."""
        query = """
        MATCH (b:Building)-[:hasAddress]->(a:Address)
        RETURN b.name AS name, a.location.latitude AS lat, a.location.longitude AS lng
        """
        with self.driver.session() as session:
            result = session.run(query)
            buildings = [{"name": record["name"], "lat": record["lat"], "lng": record["lng"]} for record in result]

        logging.info("Fetched buildings from Neo4j. Count: %s", len(buildings))
        return buildings

    def add_building(self, data):
        """Add a building and its address to Neo4j."""
        query = """
        MERGE (b:Building { name: $name })
        SET b.description = $description
        MERGE (a:Address { street: $street, city: $city, country: $country })
        SET a.location = point({ latitude: $lat, longitude: $lng })
        MERGE (b)-[:hasAddress]->(a)
        RETURN b, a
        """
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

    def provision_data(self):
        """Provision Neo4j with initial data."""
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
            MATCH (b:Building), (a:Address)
            WHERE b.name = "Corp EC" AND a.street = "Splaiul Independenței, 313"
            MERGE (b)-[:hasAddress]->(a)
            """,
            """
            MATCH (b:Building), (a:Address)
            WHERE b.name = "Corp ED" AND a.street = "Splaiul Independenței, 313"
            MERGE (b)-[:hasAddress]->(a)
            """,
            """
            MATCH (b:Building), (a:Address)
            WHERE b.name = "Centrul PRECIS" AND a.street = "Splaiul Independenței, 313"
            MERGE (b)-[:hasAddress]->(a)
            """,
            """
            MATCH (sc:SmartCity), (s:Sensor)
            WHERE sc.name = "Metropolis" AND s.sensorId = "Sensor123"
            MERGE (sc)-[:hasSensor]->(s)
            """,
            """
            MATCH (s:Sensor), (b:Building)
            WHERE s.sensorId = "Sensor123" AND b.name = "Corp EC"
            MERGE (s)-[:locatedIn]->(b)
            """
        ]
        try:
            with self.driver.session() as session:
                for query in queries:
                    session.run(query)
            print("Provisioned initial data to Neo4j.")
        except Exception as e:
            print("Error provisioning Neo4j data:", e)

    def close(self):
        """Close the Neo4j driver."""
        self.driver.close()
