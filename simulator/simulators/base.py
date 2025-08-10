"""
Base components for simulators.
"""
import os
import json
import time
import random
import logging
from abc import ABC, abstractmethod
from datetime import datetime
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class BaseSimulator(ABC):
    """
    Abstract base class for a simulator.
    """

    def __init__(self, sensor_id_prefix, topic):
        self.broker = os.getenv("MQTT_BROKER", "localhost")
        self.port = int(os.getenv("MQTT_PORT", 1883))
        self.topic = topic
        # Prefer an explicit, stable SENSOR_ID; fallback to SENSOR_ID_PREFIX or the provided prefix.
        env_sensor_id = os.getenv("SENSOR_ID")
        env_prefix = os.getenv("SENSOR_ID_PREFIX", sensor_id_prefix)
        if env_sensor_id and env_sensor_id.strip():
            self.sensor_id = env_sensor_id.strip()
        else:
            # Stable-ish default using prefix and a bounded random suffix
            self.sensor_id = f"{env_prefix}_{random.randint(1, 100)}"
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info(f"[{self.sensor_id}] Connected to MQTT Broker at {self.broker}:{self.port}")
        else:
            logging.error(f"[{self.sensor_id}] Failed to connect, return code {rc}\n")

    @abstractmethod
    def generate_payload(self):
        """
        Generate a data payload. This should be implemented by subclasses.
        """
        pass

    def run(self):
        """
        Connect to MQTT and run the simulation loop.
        """
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            while True:
                payload = self.generate_payload()
                payload["sensor_id"] = self.sensor_id
                payload["timestamp"] = datetime.now().isoformat()

                self.client.publish(self.topic, json.dumps(payload))
                logging.info(f"[{self.sensor_id}] Published to {self.topic}: {payload}")
                time.sleep(random.uniform(5, 15))
        except KeyboardInterrupt:
            logging.info(f"[{self.sensor_id}] Simulation stopped.")
        except Exception as e:
            logging.error(f"[{self.sensor_id}] An error occurred: {e}")
        finally:
            self.client.loop_stop()
            self.client.disconnect()
