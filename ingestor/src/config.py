import os
from dataclasses import dataclass

@dataclass
class ConnectionConfig:
    """Class to represent connection configuration."""
    id: int
    broker: str
    port: int
    topic: str
    connectionType: str = "mqtt"

# Default MQTT configuration
DEFAULT_MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
DEFAULT_MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
DEFAULT_MQTT_TOPIC = os.getenv("MQTT_TOPIC", "smartcity/sensor")

# MinIO configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minio123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "lake")
