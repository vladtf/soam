import json
import threading
import logging
from collections import deque
import paho.mqtt.client as mqtt
from minio import S3Error
from src.storage.minio_client import MinioClient


logger = logging.getLogger(__name__)


class MQTTClientHandler:
    def __init__(self, broker, port, topic, data_buffer, minio_client, messages_received, messages_processed, processing_latency):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.data_buffer = data_buffer
        self.minio_client = minio_client
        self.messages_received = messages_received
        self.messages_processed = messages_processed
        self.processing_latency = processing_latency
        self.client = None
        self.last_connection_error = None

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
                self.data_buffer.append(payload)
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
        self.data_buffer.clear()
        self.data_buffer.append({"error": "Connection error"})

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
