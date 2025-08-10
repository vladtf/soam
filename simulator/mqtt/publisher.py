import time
import json
import random
import paho.mqtt.client as mqttClient
import os
import logging
from datetime import datetime, timedelta  # Import timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

broker = os.getenv("MQTT_BROKER", "localhost")
sensor_id = os.getenv("SENSOR_ID", "sensor_1")
port = 1883                  # Default MQTT port
topic = "smartcity/sensor"   # Topic for the sensor data

logging.info(f"Connecting to MQTT broker: {broker}:{port}")

client = mqttClient.Client(mqttClient.CallbackAPIVersion.VERSION2)


client.connect(broker, port, 60)

# Define temperature ranges for different time periods
temperature_ranges = {
    (0, 6): (10.0, 20.0),   # Midnight to 6 AM
    (6, 12): (15.0, 25.0),  # 6 AM to Noon
    (12, 18): (20.0, 35.0), # Noon to 6 PM
    (18, 24): (15.0, 25.0)  # 6 PM to Midnight
}

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
        "sensor-id": sensor_id,
    }
    client.publish(topic, json.dumps(payload))
    logging.info("Published: %s", payload)
    time.sleep(random.randint(3, 7))  # Randomized sleep interval