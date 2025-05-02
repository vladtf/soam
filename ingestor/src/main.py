import datetime
import io
import json
import threading
from collections import deque
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from minio import S3Error
import paho.mqtt.client as mqtt
import os
from dataclasses import dataclass
import asyncio
import logging
import requests  # Add this import for making HTTP requests

from src.storage.minio_client import MinioClient
from src.app import create_app
from src.config import DEFAULT_MQTT_BROKER, DEFAULT_MQTT_PORT, DEFAULT_MQTT_TOPIC, MINIO_BUCKET, ConnectionConfig
from src.mqtt_client import MQTTClientHandler
from src.routes import register_routes


class SmartCityIngestor:
    def __init__(self):
        self.app = create_app()
        self.data_buffer = deque(maxlen=100)
        self.connection_configs = []
        self.active_connection = None
        self.minio_client = MinioClient(MINIO_BUCKET)
        self.mqtt_handler = None

        # Default connection
        default_config = ConnectionConfig(
            id=1,
            broker=DEFAULT_MQTT_BROKER,
            port=DEFAULT_MQTT_PORT,
            topic=DEFAULT_MQTT_TOPIC
        )
        self.connection_configs.append(default_config)
        self.active_connection = default_config

        # Register routes
        register_routes(self.app, self)

        # Start MQTT client
        self.start_mqtt_client()

    def start_mqtt_client(self):
        """Start the MQTT client."""
        self.mqtt_handler = MQTTClientHandler(
            broker=self.active_connection.broker,
            port=self.active_connection.port,
            topic=self.active_connection.topic,
            data_buffer=self.data_buffer,
            minio_client=self.minio_client
        )
        threading.Thread(target=self.mqtt_handler.start, daemon=True).start()

    async def shutdown_event(self):
        """Shutdown event to stop MQTT client."""
        if self.mqtt_handler:
            self.mqtt_handler.stop()

# Instantiate the backend and expose its app
backend = SmartCityIngestor()
app = backend.app
app.on_event("shutdown")(backend.shutdown_event)
