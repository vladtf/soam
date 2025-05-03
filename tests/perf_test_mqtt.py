#!/usr/bin/env python3
"""
Writes three sensor rows to MinIO as Parquet, reads them back,
and prints the mean temperature.

# 1. Copy the test script into the soam-simulator container and run it
docker cp perf_test_mqtt.py soam-simulator:/tmp/perf_test_mqtt.py && \
docker exec -it soam-simulator python /tmp/perf_test_mqtt.py --threads 5
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
parser.add_argument("--threads", type=int, default=5, help="Number of threads to simulate")
args = parser.parse_args()

num_threads = args.threads
logging.info(f"Starting {num_threads} threads for publishing messages.")


def publish_messages():
    """Function to be executed by each thread for publishing messages."""
    while True:
        payload = {
            "temperature": round(random.uniform(10.0, 35.0), 2),  # Simplified temperature range
            "humidity": round(random.uniform(20, 70), 2),         # Expanded range for humidity
            "timestamp": datetime.now().isoformat(),
            "sensorId": sensor_id,
        }
        client.publish(topic, json.dumps(payload))


# Create and start multiple threads
threads = []
for _ in range(num_threads):
    thread = threading.Thread(target=publish_messages)
    thread.daemon = True  # Ensure threads exit when the main program exits
    threads.append(thread)
    thread.start()

# Keep the main thread alive
for thread in threads:
    thread.join()
