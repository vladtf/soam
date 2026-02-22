"""
MQTT data source connector.
Refactored version of the existing MQTT client using the new connector architecture.

Supports MQTT v5 Shared Subscriptions for horizontal scaling:
- When multiple ingestor pods subscribe to the same shared subscription group,
  the broker distributes messages among them (load balancing).
- This prevents message duplication when scaling out.
- Shared subscriptions use the format: $share/<group-name>/<topic>
"""
import asyncio
import json
import os
from typing import Dict, Any
import paho.mqtt.client as mqtt
from datetime import datetime, timezone
from .base import BaseDataConnector, DataMessage, ConnectorStatus, ConnectorHealthResponse, ConnectorRegistry
from ..utils.timestamp_utils import extract_timestamp

# Default shared subscription group name for load balancing across ingestor pods
# All ingestor pods with the same group name will share messages (round-robin)
DEFAULT_SHARED_GROUP = os.environ.get("MQTT_SHARED_GROUP", "ingestor-group")


@ConnectorRegistry.register("mqtt")
class MQTTConnector(BaseDataConnector):
    """
    MQTT data source connector with shared subscription support.
    
    Shared Subscriptions (MQTT v5):
    - Multiple subscribers in the same group share messages (load balancing)
    - Topic format: $share/<group-name>/<original-topic>
    - Enable via config: "use_shared_subscription": true
    - Group name via config: "shared_group": "my-group" or env MQTT_SHARED_GROUP
    """
    
    def __init__(self, source_id: str, config: Dict[str, Any], data_handler):
        super().__init__(source_id, config, data_handler)
        self.client = None
        self.connected = asyncio.Event()
        
        # Shared subscription configuration
        self.use_shared_subscription = config.get("use_shared_subscription", True)  # Default to True for scaling
        self.shared_group = config.get("shared_group", DEFAULT_SHARED_GROUP)
    
    async def connect(self) -> bool:
        """Connect to MQTT broker using MQTT v5 protocol for shared subscriptions."""
        try:
            # Use MQTT v5 protocol for shared subscription support
            self.client = mqtt.Client(
                protocol=mqtt.MQTTv5,
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2
            )
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect
            
            broker = self.config["broker"]
            port = self.config.get("port", 1883)
            username = self.config.get("username")
            password = self.config.get("password")
            
            if username and password:
                self.client.username_pw_set(username, password)
            
            pod_name = os.environ.get("POD_NAME", "unknown")
            self.logger.info(f"🔌 Connecting to MQTT broker {broker}:{port} (pod: {pod_name})")
            if self.use_shared_subscription:
                self.logger.info(f"📊 Shared subscription enabled, group: {self.shared_group}")
            
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
    
    async def health_check(self) -> ConnectorHealthResponse:
        """MQTT connector health check with standardized response."""
        is_connected = self.client and self.client.is_connected() if self.client else False
        is_running = self._running
        
        # Calculate overall health status (includes connectivity)
        healthy = is_connected and is_running and self.status == ConnectorStatus.ACTIVE
        
        # Prepare connection-specific details
        connection_details = {
            "broker": self.config.get("broker"),
            "port": self.config.get("port", 1883),
            "topics": self.config.get("topics", []),
            "use_shared_subscription": self.use_shared_subscription,
            "shared_group": self.shared_group if self.use_shared_subscription else None,
            "pod_name": os.environ.get("POD_NAME", "unknown")
        }
        
        return ConnectorHealthResponse(
            status=self.status.value,
            healthy=healthy,
            running=is_running,
            connection_details=connection_details,
            error=self.last_error
        )
    
    def _convert_to_shared_topic(self, topic: str) -> str:
        """
        Convert a regular topic to shared subscription format.
        
        MQTT v5 shared subscription format: $share/<group-name>/<topic>
        Example: smartcity/sensors/+ -> $share/ingestor-group/smartcity/sensors/+
        
        This allows multiple subscribers in the same group to share messages,
        enabling horizontal scaling without message duplication.
        """
        if not self.use_shared_subscription:
            return topic
            
        # Don't convert if already a shared subscription
        if topic.startswith("$share/"):
            return topic
            
        shared_topic = f"$share/{self.shared_group}/{topic}"
        return shared_topic
    
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        """MQTT v5 connection callback."""
        if reason_code == 0 or reason_code.is_failure == False:
            pod_name = os.environ.get("POD_NAME", "unknown")
            self.logger.info(f"✅ MQTT connected successfully (pod: {pod_name})")
            topics = self.config.get("topics", [])
            
            if isinstance(topics, str):
                topics = [topics]  # Handle single topic as string
                
            for topic in topics:
                # Convert to shared subscription if enabled
                subscribe_topic = self._convert_to_shared_topic(topic)
                client.subscribe(subscribe_topic)
                
                if self.use_shared_subscription:
                    self.logger.info(f"📩 Subscribed to shared topic: {subscribe_topic} (original: {topic})")
                else:
                    self.logger.info(f"📩 Subscribed to topic: {subscribe_topic}")
            
            self.connected.set()
        else:
            self.logger.error(f"❌ MQTT connection failed with reason code {reason_code}")
    
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
                timestamp=extract_timestamp(data.get("timestamp")) if isinstance(data, dict) else datetime.now(timezone.utc).isoformat(),
                raw_payload=raw_payload
            )
            
            # Emit to data handler
            self._emit_data(message)
            self.logger.debug(f"🔍 Processed message from topic: {msg.topic} -> {topic_specific_source_id}")
            
        except Exception as e:
            self.logger.error(f"❌ Error processing MQTT message: {e}")
    
    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        """MQTT v5 disconnect callback."""
        pod_name = os.environ.get("POD_NAME", "unknown")
        if reason_code != 0:
            self.logger.warning(f"⚠️ MQTT disconnected unexpectedly with code {reason_code} (pod: {pod_name})")
        else:
            self.logger.info(f"📡 MQTT disconnected cleanly (pod: {pod_name})")
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
                },
                "use_shared_subscription": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable MQTT v5 shared subscriptions for horizontal scaling. When enabled, multiple ingestor pods share messages (load balancing) instead of each receiving all messages."
                },
                "shared_group": {
                    "type": "string",
                    "default": "ingestor-group",
                    "description": "Shared subscription group name. All pods with the same group share messages. Default: 'ingestor-group' or MQTT_SHARED_GROUP env var."
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
