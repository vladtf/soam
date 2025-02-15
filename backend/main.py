import json
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import paho.mqtt.client as mqtt


class SmartCityBackend:
    def __init__(self):
        self.app = FastAPI()
        self.latest_data = {}

        # Enable CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # MQTT configuration
        self.MQTT_BROKER = "localhost"
        self.MQTT_PORT = 1883
        self.MQTT_TOPIC = "smartcity/sensor"

        # Register routes
        self.app.get("/data")(self.get_data)

        # Start the MQTT client thread
        threading.Thread(target=self.mqtt_loop, daemon=True).start()

    def on_connect(self, client, userdata, flags, rc):
        print("Connected to MQTT broker with result code", rc)
        client.subscribe(self.MQTT_TOPIC)

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            self.latest_data = payload
            print("Received message:", payload)
        except Exception as e:
            print("Error parsing message:", e)

    def mqtt_loop(self):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "BackendListener")
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        client.connect(self.MQTT_BROKER, self.MQTT_PORT, 60)
        client.loop_forever()

    def get_data(self):
        """Returns the latest sensor data."""
        return self.latest_data


# Instantiate the backend and expose its app
backend = SmartCityBackend()
app = backend.app
