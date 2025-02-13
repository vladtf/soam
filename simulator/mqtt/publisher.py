import time
import json
import random
import paho.mqtt.client as mqttClient

broker = "localhost"         # Replace with your MQTT broker address
port = 1883                  # Default MQTT port
topic = "smartcity/sensor"   # Topic for the sensor data
client_id = "publisher"      # Client ID

client = mqttClient.Client(mqttClient.CallbackAPIVersion.VERSION1, client_id)


client.connect(broker, port, 60)

while True:
    payload = {
        "temperature": round(random.uniform(20.0, 25.0), 2),
        "humidity": round(random.uniform(30, 50), 2)
    }
    client.publish(topic, json.dumps(payload))
    print("Published:", payload)
    time.sleep(5)
