import time
import json
import random
import paho.mqtt.client as mqttClient
import os
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

broker = os.getenv("MQTT_BROKER", "localhost")
sensor_id = os.getenv("SENSOR_ID", "sensor_1")
port = 1883                  # Default MQTT port
topic = "smartcity/sensor"   # Topic for the sensor data

logging.info(f"Connecting to MQTT broker: {broker}:{port}")

client = mqttClient.Client(mqttClient.CallbackAPIVersion.VERSION2)


client.connect(broker, port, 60)

while True:
    payload = {
        "temperature": round(random.uniform(20.0, 25.0), 2),
        "humidity": round(random.uniform(30, 50), 2),
        "timestamp": datetime.now().isoformat(),
        "sensorId": sensor_id,
    }
    client.publish(topic, json.dumps(payload))
    logging.info("Published: %s", payload)
    time.sleep(5)