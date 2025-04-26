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
        "temperature": round(random.uniform(15.0, 35.0), 2),  # Expanded range for temperature
        "humidity": round(random.uniform(20, 70), 2),         # Expanded range for humidity
        "timestamp": (datetime.now() + 
                      random.timedelta(seconds=random.randint(-10, 10))).isoformat(),  # Slight timestamp variation
        "sensorId": sensor_id,
    }
    client.publish(topic, json.dumps(payload))
    logging.info("Published: %s", payload)
    time.sleep(random.randint(3, 7))  # Randomized sleep interval