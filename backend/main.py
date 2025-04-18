import json
import threading
from collections import deque
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import paho.mqtt.client as mqtt
import os
from dataclasses import dataclass
import asyncio
from neo4j import GraphDatabase
import logging


@dataclass
class ConnectionConfig:  # new class for connection configuration
    id: int
    broker: str
    port: int
    topic: str
    connectionType: str = "mqtt"


class SmartCityBackend:
    def __init__(self):
        self.app = FastAPI()
        self.data_buffer = deque(maxlen=100)  # Buffer to store the last 100 messages
        self.connection_configs = []          # List of connection configs
        self.active_connection = None         # Active connection config
        self.mqtt_client = None               # Store current mqtt client instance
        self.threads = {}                     # Map to store threads for later shutdown
        self.thread_counter = 1               # Counter for unique thread keys
        self.last_connection_error = None
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "verystrongpassword")
        self.neo4j_driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password))  # new driver initialization

        # Enable CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Default MQTT configuration
        self.DEFAULT_MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
        self.DEFAULT_MQTT_PORT = 1883
        self.DEFAULT_MQTT_TOPIC = "smartcity/sensor"

        # Replace default connection dict with ConnectionConfig instance
        default_config = ConnectionConfig(
            id=1,
            broker=self.DEFAULT_MQTT_BROKER,
            port=self.DEFAULT_MQTT_PORT,
            topic=self.DEFAULT_MQTT_TOPIC,
            connectionType="mqtt"
        )
        self.connection_configs.append(default_config)
        self.active_connection = default_config

        # Register routes
        self.app.get("/data")(self.get_data)
        self.app.post("/addConnection")(self.add_connection)
        self.app.post("/switchBroker")(self.switch_broker)
        self.app.get("/connections")(self.get_connections)
        self.app.get("/buildings")(self.get_buildings)  # new route to fetch buildings
        self.app.post("/addBuilding")(self.add_building)  # new endpoint to add a building

        # Provision Neo4j with initial data from utils.txt
        self.provision_data()

        # Start the MQTT client thread
        mqtt_thread = threading.Thread(target=self.mqtt_loop, daemon=True)
        self.threads[f"mqtt_loop_{self.thread_counter}"] = mqtt_thread  # store thread
        mqtt_thread.start()
        # Register shutdown event to gracefully close MQTT client
        self.app.on_event("shutdown")(self.shutdown_event)

    def on_connect(self, client, userdata, flags, rc):
        try:
            print("Connected to MQTT broker with result code", rc)
            client.subscribe(self.DEFAULT_MQTT_TOPIC)
            if self.active_connection:
                # Update status for active user
                self.connection_status = "Connected"
        except Exception as e:
            print("Error in on_connect:", e)
            self.last_connection_error = str(e)
            self.data_buffer.clear()
            self.connection_status = "Disconnected"
            self.data_buffer.append({"error": "Connection error"})
            self.active_connection = None

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            self.data_buffer.append(payload)
            print("Received message:", payload)
        except Exception as e:
            print("Error parsing message:", e)

    def mqtt_loop(self):
        # If an existing client is running, disconnect it before starting a new one
        if self.mqtt_client is not None:
            try:
                self.mqtt_client.disconnect()
            except Exception as e:
                print("Error disconnecting previous MQTT client:", e)

        client = mqtt.Client()
        self.mqtt_client = client  # Save current client
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        try:
            client.connect(self.DEFAULT_MQTT_BROKER, self.DEFAULT_MQTT_PORT, 60)
            client.loop_forever()
        except Exception as e:
            print("MQTT connection error:", e)
            self.last_connection_error = str(e)
            self.data_buffer.clear()
            self.data_buffer.append({"error": "Connection error"})

    def get_data(self):
        """Returns the buffered sensor data."""
        return list(self.data_buffer)

    async def add_connection(self, request: Request):
        config = await request.json()
        config_id = len(self.connection_configs) + 1
        new_config = ConnectionConfig(
            id=config_id,
            broker=config.get("broker", "localhost"),
            port=config.get("port", 1883),
            topic=config.get("topic", "smartcity/sensor"),
            connectionType=config.get("connectionType", "mqtt")
        )
        self.connection_configs.append(new_config)
        if self.active_connection is None:
            self.active_connection = new_config
            self.DEFAULT_MQTT_BROKER = new_config.broker
            self.DEFAULT_MQTT_PORT = new_config.port
            self.DEFAULT_MQTT_TOPIC = new_config.topic
        print("Added connection:", new_config)
        return {"status": "Connection added", "id": config_id}

    async def switch_broker(self, request: Request):
        body = await request.json()
        target_id = body.get("id")
        for config in self.connection_configs:
            if config.id == target_id:
                self.active_connection = config
                self.data_buffer.clear()
                self.DEFAULT_MQTT_BROKER = config.broker
                self.DEFAULT_MQTT_PORT = config.port
                self.DEFAULT_MQTT_TOPIC = config.topic
                print("Switched active broker to", config)
                if self.mqtt_client is not None:
                    try:
                        self.mqtt_client.disconnect()
                    except Exception as e:
                        print("Error disconnecting previous MQTT client:", e)
                # Reset last error before starting new thread
                self.last_connection_error = None
                self.thread_counter += 1  # increment counter for unique key
                new_thread = threading.Thread(target=self.mqtt_loop, daemon=True)
                self.threads[f"mqtt_loop_{self.thread_counter}"] = new_thread
                new_thread.start()
                # Wait briefly for connection attempt to occur
                await asyncio.sleep(1)
                if self.last_connection_error:
                    return {"status": "Error switching broker", "error": self.last_connection_error}
                return {"status": "Switched to connection", "active": config.__dict__}
        return {"status": "Connection id not found"}

    def get_connections(self):
        return {
            "connections": [c.__dict__ for c in self.connection_configs],
            "active": self.active_connection.__dict__ if self.active_connection else None
        }

    def get_buildings(self):
        """Query Neo4j for all buildings with their address coordinates."""
        query = """
        MATCH (b:Building)-[:hasAddress]->(a:Address)
        RETURN b.name AS name, a.location.latitude AS lat, a.location.longitude AS lng
        """
        with self.neo4j_driver.session() as session:
            result = session.run(query)
            buildings = [{"name": record["name"], "lat": record["lat"], "lng": record["lng"]} for record in result]

        logging.info("Fetched buildings from Neo4j. Count: %s", len(buildings))
        return buildings

    async def add_building(self, request: Request):
        # Extract building and address details from the request
        data = await request.json()
        try:
            name = data["name"]
            description = data.get("description", "")
            street = data["street"]
            city = data["city"]
            country = data["country"]
            lat = data["lat"]
            lng = data["lng"]
        except KeyError as e:
            return {"status": "error", "detail": f"Missing field: {str(e)}"}
        
        query = """
        MERGE (b:Building { name: $name })
        SET b.description = $description
        MERGE (a:Address { street: $street, city: $city, country: $country })
        SET a.location = point({ latitude: $lat, longitude: $lng })
        MERGE (b)-[:hasAddress]->(a)
        RETURN b, a
        """
        try:
            with self.neo4j_driver.session() as session:
                result = session.run(query, name=name, description=description,
                                     street=street, city=city, country=country,
                                     lat=lat, lng=lng)
                record = result.single()
                if record is None:
                    return {"status": "No building added"}
                # Return simplified representations of the nodes
                b = record["b"]
                a = record["a"]
                return {"status": "Building added", "building": dict(b), "address": dict(a)}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    def provision_data(self):
        # Pre-provision data from utils.txt (excluding clear and show queries)
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
            with self.neo4j_driver.session() as session:
                for query in queries:
                    session.run(query)
            print("Provisioned initial data to Neo4j.")
        except Exception as e:
            print("Error provisioning Neo4j data:", e)

    async def shutdown_event(self):
        # Gracefully disconnect the MQTT client on shutdown
        if self.mqtt_client is not None:
            try:
                self.mqtt_client.disconnect()
            except Exception as e:
                print("Error disconnecting MQTT client during shutdown:", e)
        # Stop and join all threads stored in the map
        for key, thread in self.threads.items():
            if thread.is_alive():
                thread.join(timeout=5)  # join with timeout for safety
        print("Shutdown event triggered")


# Instantiate the backend and expose its app
backend = SmartCityBackend()
app = backend.app
