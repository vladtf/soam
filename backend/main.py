import json
import threading
from collections import deque
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import paho.mqtt.client as mqtt
import os


class SmartCityBackend:
    def __init__(self):
        self.app = FastAPI()
        self.data_buffer = deque(maxlen=100)  # Buffer to store the last 100 messages
        self.connection_configs = []          # List of connection configs
        self.active_connection = None         # Active connection config
        self.mqtt_client = None               # Store current mqtt client instance

        # Enable CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Default MQTT configuration
        self.MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
        self.MQTT_PORT = 1883
        self.MQTT_TOPIC = "smartcity/sensor"

        # Register routes
        self.app.get("/data")(self.get_data)
        self.app.post("/addConnection")(self.add_connection)
        self.app.post("/switchBroker")(self.switch_broker)
        self.app.get("/connections")(self.get_connections)

        # Start the MQTT client thread
        threading.Thread(target=self.mqtt_loop, daemon=True).start()

    def on_connect(self, client, userdata, flags, rc):
        print("Connected to MQTT broker with result code", rc)
        client.subscribe(self.MQTT_TOPIC)
        if self.active_connection:
            # Update status for active user
            self.connection_status = "Connected"

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
        client.connect(self.MQTT_BROKER, self.MQTT_PORT, 60)
        client.loop_forever()

    def get_data(self):
        """Returns the buffered sensor data."""
        return list(self.data_buffer)

    async def add_connection(self, request: Request):
        config = await request.json()
        # Assign a simple incremental ID
        config_id = len(self.connection_configs) + 1
        config['id'] = config_id
        self.connection_configs.append(config)
        # If no active connection, set the new config as active
        if self.active_connection is None:
            self.active_connection = config
            self.MQTT_BROKER = config.get("broker", "localhost")
            self.MQTT_PORT = config.get("port", 1883)
            self.MQTT_TOPIC = config.get("topic", "smartcity/sensor")
        print("Added connection:", config)
        return {"status": "Connection added", "id": config_id}

    async def switch_broker(self, request: Request):
        body = await request.json()
        target_id = body.get("id")
        for config in self.connection_configs:
            if config.get("id") == target_id:
                self.active_connection = config
                # Clear the data buffer since we are switching active connection
                self.data_buffer.clear()
                # Update MQTT configuration with new active connection
                self.MQTT_BROKER = config.get("broker", "localhost")
                self.MQTT_PORT = config.get("port", 1883)
                self.MQTT_TOPIC = config.get("topic", "smartcity/sensor")
                print("Switched active broker to", config)
                # Disconnect the existing client if any before starting new loop
                if self.mqtt_client is not None:
                    try:
                        self.mqtt_client.disconnect()
                    except Exception as e:
                        print("Error disconnecting previous MQTT client:", e)
                threading.Thread(target=self.mqtt_loop, daemon=True).start()
                return {"status": "Switched to connection", "active": config}
        return {"status": "Connection id not found"}

    def get_connections(self):
        return {
            "connections": self.connection_configs,
            "active": self.active_connection
        }


# Instantiate the backend and expose its app
backend = SmartCityBackend()
app = backend.app
