#!/usr/bin/env python3
"""
Writes three sensor rows to MinIO as Parquet, reads them back,
and prints the mean temperature.

# 1. Copy the test script into the soam-simulator container and run it
docker cp perf_test_mqtt.py soam-simulator:/tmp/perf_test_mqtt.py && \
docker exec -it soam-simulator python /tmp/perf_test_mqtt.py
"""
import time
import json
import random
import paho.mqtt.client as mqttClient
import os
import logging
import threading  # Import threading module
from datetime import datetime, timedelta  # Import timedelta
from collections import deque  # Import deque for throughput calculation

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

broker = os.getenv("MQTT_BROKER", "localhost")
sensor_id = os.getenv("SENSOR_ID", "sensor_1")
port = 1883                  # Default MQTT port
topic = "smartcity/sensor"   # Topic for the sensor data

logging.info(f"Connecting to MQTT broker: {broker}:{port}")

client = mqttClient.Client(mqttClient.CallbackAPIVersion.VERSION2)

client.connect(broker, port, 60)

# Initialize variables for performance metrics
latency_records = deque(maxlen=100)  # Store the last 100 latencies
message_count = 0
start_time = time.time()

def on_publish(client, userdata, mid, properties=None, reasonCode=None):
    """Callback for when a message is published."""
    if mid in userdata:
        latency = time.time() - userdata[mid]
        latency_records.append(latency)
        del userdata[mid]
    else:
        logging.warning(f"Message ID {mid} not found in userdata.")

client.user_data_set({})  # Initialize userdata for tracking timestamps
client.on_publish = on_publish

# Define temperature ranges for different time periods
temperature_ranges = {
    (0, 6): (10.0, 20.0),   # Midnight to 6 AM
    (6, 12): (15.0, 25.0),  # 6 AM to Noon
    (12, 18): (20.0, 35.0), # Noon to 6 PM
    (18, 24): (15.0, 25.0)  # 6 PM to Midnight
}

def publish_messages():
    """Function to be executed by each thread for publishing messages."""
    global message_count, start_time  # Access shared variables
    while True:
        current_hour = datetime.now().hour
        for (start, end), (min_temp, max_temp) in temperature_ranges.items():
            if start <= current_hour < end:
                base_temperature = random.uniform(min_temp, max_temp)
                break

        payload = {
            "temperature": round(base_temperature, 2),
            "humidity": round(random.uniform(20, 70), 2),         # Expanded range for humidity
            "timestamp": (datetime.now() + 
                          timedelta(seconds=random.randint(-10, 10))).isoformat(),  # Slight timestamp variation
            "sensorId": sensor_id,
        }
        message_id = client.publish(topic, json.dumps(payload)).mid
        client._userdata[message_id] = time.time()  # Record the timestamp for latency calculation

        # Update performance metrics
        with threading.Lock():  # Ensure thread-safe updates
            message_count += 1
            if time.time() - start_time >= 10:
                avg_latency = sum(latency_records) / len(latency_records) if latency_records else 0
                throughput = message_count / (time.time() - start_time)
                logging.info(f"Average Latency: {avg_latency:.3f} seconds, Throughput: {throughput:.2f} messages/second")
                start_time = time.time()
                message_count = 0

        logging.info("Published: %s", payload)
        time.sleep(random.randint(3, 7))  # Randomized sleep interval

# Create and start multiple threads
num_threads = 5  # Number of threads to run
threads = []
for _ in range(num_threads):
    thread = threading.Thread(target=publish_messages)
    thread.daemon = True  # Ensure threads exit when the main program exits
    threads.append(thread)
    thread.start()

# Keep the main thread alive
for thread in threads:
    thread.join()