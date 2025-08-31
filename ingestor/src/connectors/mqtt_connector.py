"""
MQTT data source connector.
Refactored version of the existing MQTT client using the new connector architecture.
"""
import asyncio
import json
from typing import Dict, Any
import paho.mqtt.client as mqtt
from datetime import datetime, timezone
from .base import BaseDataConnector, DataMessage, ConnectorStatus


class MQTTConnector(BaseDataConnector):
    """MQTT data source connector."""
    
    def __init__(self, source_id: str, config: Dict[str, Any], data_handler):
        super().__init__(source_id, config, data_handler)
        self.client = None
        self.connected = asyncio.Event()
    
    async def connect(self) -> bool:
        """Connect to MQTT broker."""
        try:
            self.client = mqtt.Client()
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect
            
            broker = self.config["broker"]
            port = self.config.get("port", 1883)
            username = self.config.get("username")
            password = self.config.get("password")
            
            if username and password:
                self.client.username_pw_set(username, password)
            
            self.logger.info(f"🔌 Connecting to MQTT broker {broker}:{port}")
            self.client.connect(broker, port, 60)
            self.client.loop_start()
            
            # Wait for connection with timeout
            try:
                await asyncio.wait_for(self.connected.wait(), timeout=10.0)
                return True
            except asyncio.TimeoutError:
                self.logger.error("⏱️ MQTT connection timeout")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ MQTT connection failed: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.logger.info("📡 MQTT client disconnected")
    
    async def start_ingestion(self) -> None:
        """Start MQTT message ingestion."""
        self.logger.info("🔍 Starting MQTT message ingestion")
        while self._running:
            await asyncio.sleep(0.1)  # Keep alive, actual processing in callbacks
    
    async def stop_ingestion(self) -> None:
        """Stop MQTT ingestion."""
        pass  # Handled by disconnect
    
    async def health_check(self) -> Dict[str, Any]:
        """MQTT connector health check."""
        return {
            "status": self.status.value,
            "connected": self.client and self.client.is_connected() if self.client else False,
            "broker": self.config.get("broker"),
            "port": self.config.get("port", 1883),
            "topics": self.config.get("topics", []),
            "running": self._running
        }
    
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback."""
        if rc == 0:
            self.logger.info("✅ MQTT connected successfully")
            topics = self.config.get("topics", [])
            
            if isinstance(topics, str):
                topics = [topics]  # Handle single topic as string
                
            for topic in topics:
                client.subscribe(topic)
                self.logger.info(f"📩 Subscribed to topic: {topic}")
            
            self.connected.set()
        else:
            self.logger.error(f"❌ MQTT connection failed with code {rc}")
    
    def _on_message(self, client, userdata, msg):
        """MQTT message callback."""
        try:
            # Parse payload
            raw_payload = msg.payload.decode('utf-8')
            
            try:
                data = json.loads(raw_payload)
            except json.JSONDecodeError:
                # Handle non-JSON messages
                data = {"content": raw_payload, "raw": True}
            
            # Create topic-specific source_id for better data lake organization
            # Convert topic to safe filename format: smartcity/sensors/temperature -> smartcity_sensors_temperature
            topic_safe = msg.topic.replace("/", "_").replace("#", "wildcard").replace("+", "plus")
            topic_specific_source_id = f"{self.source_id}_{topic_safe}"
            
            # Create standard message
            message = DataMessage(
                data=data,
                metadata={
                    "topic": msg.topic,
                    "qos": msg.qos,
                    "retain": msg.retain,
                    "source_type": "mqtt",
                    "broker": self.config.get("broker"),
                    "original_source_id": self.source_id,  # Keep reference to original data source
                    "ingestion_timestamp": datetime.now(timezone.utc).isoformat()
                },
                source_id=topic_specific_source_id,  # Use topic-specific ID
                timestamp=data.get("timestamp") if isinstance(data, dict) else datetime.now(timezone.utc).isoformat(),
                raw_payload=raw_payload
            )
            
            # Emit to data handler
            self._emit_data(message)
            self.logger.debug(f"🔍 Processed message from topic: {msg.topic} -> {topic_specific_source_id}")
            
        except Exception as e:
            self.logger.error(f"❌ Error processing MQTT message: {e}")
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnect callback."""
        if rc != 0:
            self.logger.warning(f"⚠️ MQTT disconnected unexpectedly with code {rc}")
        else:
            self.logger.info("📡 MQTT disconnected cleanly")
        self.connected.clear()
    
    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Return configuration schema for MQTT connector."""
        return {
            "type": "object",
            "properties": {
                "broker": {
                    "type": "string",
                    "description": "MQTT broker hostname or IP address"
                },
                "port": {
                    "type": "integer",
                    "default": 1883,
                    "minimum": 1,
                    "maximum": 65535,
                    "description": "MQTT broker port"
                },
                "topics": {
                    "oneOf": [
                        {"type": "string"},
                        {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1
                        }
                    ],
                    "description": "MQTT topic(s) to subscribe to"
                },
                "username": {
                    "type": "string",
                    "description": "MQTT username (optional)"
                },
                "password": {
                    "type": "string",
                    "description": "MQTT password (optional)"
                }
            },
            "required": ["broker", "topics"]
        }
    
    @classmethod
    def get_display_info(cls) -> Dict[str, Any]:
        """Return display information for MQTT connector."""
        return {
            "name": "MQTT Broker",
            "description": "Connect to MQTT brokers for real-time IoT data ingestion",
            "icon": "📡",
            "category": "IoT",
            "supported_formats": ["JSON", "Plain Text"],
            "real_time": True
        }
