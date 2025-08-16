import json
import hashlib
import re
import threading
import logging
from collections import deque
import paho.mqtt.client as mqtt
from minio import S3Error
from src.storage.minio_client import MinioClient


logger = logging.getLogger(__name__)


class MQTTClientHandler:
    def __init__(self, broker, port, topic, state, minio_client, messages_received, messages_processed, processing_latency):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.state = state
        self.minio_client = minio_client
        self.messages_received = messages_received
        self.messages_processed = messages_processed
        self.processing_latency = processing_latency
        self.client = None
        self.last_connection_error = None

    @staticmethod
    def _sanitize_string(s: str) -> str:
        return re.sub(r"[^a-zA-Z0-9]+", "_", s.strip())

    def _ingestion_id_for(self, topic: str) -> str:
        """Build a stable, unique ingestion id that includes the sanitized broker, port, and topic.
        
        This creates topic-specific ingestion_ids to ensure different sensor types get different IDs.
        """
        broker_str = self._sanitize_string(str(self.broker))
        port_str = self._sanitize_string(str(self.port))
        topic_str = self._sanitize_string(topic)
        result = f"{broker_str}_{port_str}_{topic_str}"
        logger.debug(f"Generated base ingestion_id '{result}' for topic '{topic}'")
        return result

    def on_connect(self, client, userdata, flags, rc):
        try:
            logger.info("Connected to MQTT broker with result code %s", rc)
            # Support comma-separated topics
            topics = [t.strip() for t in str(self.topic).split(',') if t.strip()]
            if len(topics) == 1:
                client.subscribe(topics[0])
            else:
                # subscribe to multiple topics with QoS 0
                client.subscribe([(t, 0) for t in topics])
        except Exception as e:
            self._handle_connection_error(e)

    def on_message(self, client, userdata, msg):
        self.messages_received.inc()  # Increment received messages counter
        with self.processing_latency.time():  # Measure processing time
            try:
                payload: dict = json.loads(msg.payload.decode("utf-8"))
                
                # Use topic-based ingestion_id (most reliable since simulators use different topics)
                ingestion_id = self._ingestion_id_for(msg.topic)
                
                payload["ingestion_id"] = ingestion_id
                payload["topic"] = msg.topic
                
                # Log for debugging
                sensor_id = payload.get("sensor_id") or payload.get("sensorId", "unknown")
                logger.debug(f"Processing sensor '{sensor_id}' from topic '{msg.topic}' -> ingestion_id '{ingestion_id}'")
                
                # Append to partitioned buffer
                self.state.get_partition_buffer(ingestion_id).append(payload)
                logger.debug("Received message: %s", payload)

                # Add to MinIO buffer (may not upload immediately)
                self.minio_client.add_row(payload)
                logger.debug("Added data to MinIO buffer")
                self.messages_processed.inc()  # Increment processed messages counter
            except S3Error as s3e:
                logger.error("MinIO error: %s", s3e)
            except Exception as e:
                logger.exception("Error processing message: %s", e)

    def _handle_connection_error(self, error):
        logger.error("Error in on_connect: %s", error)
        self.last_connection_error = str(error)
        self.state.clear_all_buffers()
        # Put a generic error in a synthetic partition for UI visibility
        self.state.get_partition_buffer("errors").append({"error": "Connection error"})

    def start(self):
        """Start the MQTT client loop."""
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_forever()
        except Exception as e:
            self._handle_connection_error(e)

    def stop(self):
        """Stop the MQTT client."""
        if self.client:
            try:
                self.client.disconnect()
            except Exception as e:
                logger.warning("Error disconnecting MQTT client: %s", e)
