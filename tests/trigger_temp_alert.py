#!/usr/bin/env python3
"""
Writes three sensor rows to MinIO as Parquet, reads them back,
and prints the mean temperature.

# 1. Copy the test script into the soam-simulator container and run it
docker cp trigger_temp_alert.py soam-simulator:/tmp/trigger_temp_alert.py && \
docker exec -it soam-simulator python /tmp/trigger_temp_alert.py
"""
import time
import json
import random
import paho.mqtt.client as mqttClient
import os
import logging
import threading
from datetime import datetime
import argparse


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

broker = os.getenv("MQTT_BROKER", "localhost")
sensor_id = os.getenv("SENSOR_ID", "sensor_1")
port = 1883                  # Default MQTT port
topic = "smartcity/sensor"   # Topic for the sensor data

logging.info(f"Connecting to MQTT broker: {broker}:{port}")

client = mqttClient.Client(mqttClient.CallbackAPIVersion.VERSION2)
client.connect(broker, port, 60)

# read the number of threads from the script arguments using argparse
parser = argparse.ArgumentParser(description="MQTT Performance Test")
parser.add_argument("--threads", type=int, default=1, help="Number of threads to simulate")  # Default to 1 thread
args = parser.parse_args()

num_threads = args.threads

logging.info("Starting to publish messages.")

def publish_messages():
    """Function to publish messages in a single loop."""
    while True:
        payload = {
            "temperature": round(random.uniform(90.0, 100.0), 2),  # Very high temperature range
            "humidity": round(random.uniform(20, 70), 2),          # Expanded range for humidity
            "timestamp": datetime.now().isoformat(),
            "sensorId": sensor_id,
        }
        client.publish(topic, json.dumps(payload))
        time.sleep(1)  # Publish one message per second

# Start publishing messages
publish_messages()
