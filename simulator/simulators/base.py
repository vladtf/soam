"""
Base components for simulators.
Includes local edge buffer for offline tolerance.
"""
import os
import json
import time
import random
import logging
from abc import ABC, abstractmethod
from datetime import datetime
import paho.mqtt.client as mqtt

from .edge_buffer import EdgeBuffer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class BaseSimulator(ABC):
    """
    Abstract base class for a simulator with offline tolerance.
    Messages are buffered locally when MQTT is unavailable and replayed when reconnected.
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
        
        # Connection state tracking
        self._connected = False
        
        # In-memory buffer for offline tolerance
        max_buffer_size = int(os.getenv("EDGE_BUFFER_SIZE", 1000))
        self._buffer = EdgeBuffer(self.sensor_id, max_size=max_buffer_size)
        
        # Setup MQTT client with callbacks
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Handle successful connection."""
        if rc == 0:
            self._connected = True
            logging.info(f"[{self.sensor_id}] ✅ Connected to MQTT Broker at {self.broker}:{self.port}")
            # Replay any buffered messages
            self._replay_buffer()
        else:
            self._connected = False
            logging.error(f"[{self.sensor_id}] ❌ Failed to connect, return code {rc}")

    def _on_disconnect(self, client, userdata, disconnect_flags, rc, properties=None):
        """Handle disconnection."""
        self._connected = False
        logging.warning(f"[{self.sensor_id}] ⚠️ Disconnected from MQTT (rc={rc}), buffering enabled")

    def _replay_buffer(self):
        """Replay all buffered messages after reconnection."""
        if not self._buffer.has_pending():
            return
        
        count = self._buffer.count()
        logging.info(f"[{self.sensor_id}] 🔄 Replaying {count} buffered messages...")
        
        replayed = 0
        while self._buffer.has_pending() and self._connected:
            msg = self._buffer.pop()
            if msg:
                result = self.client.publish(msg.topic, json.dumps(msg.payload))
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    replayed += 1
                else:
                    # Re-buffer if publish failed
                    self._buffer.add(msg.topic, msg.payload)
                    break
        
        logging.info(f"[{self.sensor_id}] ✅ Replayed {replayed}/{count} buffered messages")

    def _publish(self, topic: str, payload: dict) -> bool:
        """Publish or buffer a message."""
        if self._connected:
            result = self.client.publish(topic, json.dumps(payload))
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logging.info(f"[{self.sensor_id}] 📤 Published to {topic}: {payload}")
                return True
            else:
                logging.warning(f"[{self.sensor_id}] ⚠️ Publish failed (rc={result.rc}), buffering")
                self._buffer.add(topic, payload)
                return False
        else:
            self._buffer.add(topic, payload)
            return False

    @abstractmethod
    def generate_payload(self):
        """
        Generate a data payload. This should be implemented by subclasses.
        """
        pass

    def run(self):
        """
        Connect to MQTT and run the simulation loop with offline tolerance.
        """
        # Enable automatic reconnection
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        
        try:
            logging.info(f"[{self.sensor_id}] 🔌 Connecting to {self.broker}:{self.port}...")
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            
            while True:
                payload = self.generate_payload()
                payload["sensor_id"] = self.sensor_id
                payload["timestamp"] = datetime.now().isoformat()
                
                self._publish(self.topic, payload)
                time.sleep(random.uniform(5, 15))
                
        except KeyboardInterrupt:
            logging.info(f"[{self.sensor_id}] Simulation stopped.")
        except Exception as e:
            logging.error(f"[{self.sensor_id}] ❌ Error: {e}")
        finally:
            pending = self._buffer.count()
            if pending > 0:
                logging.warning(f"[{self.sensor_id}] ⚠️ {pending} messages still buffered (will be lost)")
            self.client.loop_stop()
            self.client.disconnect()
