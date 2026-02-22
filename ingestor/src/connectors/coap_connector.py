"""
CoAP (Constrained Application Protocol) data source connector.

Supports two ingestion modes:
  - **Observe mode** (default): Uses CoAP observe (RFC 7641) to subscribe to resource
    changes, similar to MQTT subscriptions. The server pushes updates automatically.
  - **Polling mode**: Periodically sends GET requests to CoAP resources, similar to
    the REST API connector.

CoAP is a lightweight UDP-based protocol designed for constrained IoT devices (RFC 7252).
It supports multicast discovery, observe/subscribe, and DTLS security.

Python library: aiocoap (async, well-maintained)
"""
import asyncio
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import logging

from .base import BaseDataConnector, DataMessage, ConnectorStatus, ConnectorHealthResponse, ConnectorRegistry
from ..utils.timestamp_utils import extract_timestamp

logger = logging.getLogger(__name__)


@ConnectorRegistry.register("coap")
class CoapConnector(BaseDataConnector):
    """
    CoAP data source connector with observe and polling support.

    Modes:
      - observe (default): Subscribe to resource changes via CoAP observe option.
      - poll: Periodically GET resources at a configurable interval.
    """

    def __init__(self, source_id: str, config: Dict[str, Any], data_handler):
        super().__init__(source_id, config, data_handler)
        self._context = None  # aiocoap.Context
        self._observations: List[Any] = []  # Active observation handles
        self._poll_interval: int = config.get("poll_interval", 60)
        self._mode: str = config.get("mode", "observe")
        self._last_success: Optional[str] = None
        self._message_count: int = 0

    # ── Lifecycle ────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Create a CoAP client context."""
        try:
            import aiocoap
            self._context = await aiocoap.Context.create_client_context()
            self.logger.info("✅ CoAP client context created")
            self.last_error = None
            return True
        except ImportError:
            error_msg = "aiocoap package is not installed. Run: pipenv install aiocoap"
            self.logger.error(f"❌ {error_msg}")
            self.last_error = error_msg
            return False
        except Exception as e:
            error_msg = f"Failed to create CoAP context: {e}"
            self.logger.error(f"❌ {error_msg}")
            self.last_error = error_msg
            return False

    async def disconnect(self) -> None:
        """Tear down CoAP observations and context."""
        # Cancel active observations
        for obs in self._observations:
            try:
                obs.observation.cancel()
            except Exception:
                pass
        self._observations.clear()

        if self._context:
            try:
                await self._context.shutdown()
            except Exception:
                pass
            self._context = None
            self.logger.info("🔌 CoAP client context shut down")

    async def start_ingestion(self) -> None:
        """Start data ingestion in configured mode."""
        if self._mode == "observe":
            await self._run_observe()
        else:
            await self._run_poll()

    async def stop_ingestion(self) -> None:
        """Stop ingestion — handled by disconnect / task cancellation."""
        pass

    # ── Observe mode ─────────────────────────────────────────────────

    async def _run_observe(self) -> None:
        """Subscribe to CoAP resources using the observe option (RFC 7641)."""
        import aiocoap

        resources = self._get_resource_uris()
        self.logger.info(f"👁️ Starting CoAP observe on {len(resources)} resource(s)")

        for uri in resources:
            request = aiocoap.Message(code=aiocoap.GET, uri=uri, observe=0)
            try:
                observation = self._context.request(request)
                # First response confirms observe registration
                first_response = await asyncio.wait_for(observation.response, timeout=15.0)
                self._process_response(first_response, uri)
                self._observations.append(observation)
                self.logger.info(f"👁️ Observing resource: {uri}")

                # Spawn a task to continuously receive notifications
                asyncio.create_task(self._observe_loop(observation, uri))
            except asyncio.TimeoutError:
                self.logger.error(f"⏱️ Observe timeout for {uri}")
                self.last_error = f"Observe timeout for {uri}"
            except Exception as e:
                self.logger.error(f"❌ Failed to observe {uri}: {e}")
                self.last_error = str(e)

        # Keep alive while observations are active
        while self._running:
            await asyncio.sleep(1)

    async def _observe_loop(self, observation, uri: str) -> None:
        """Continuously receive observe notifications for a single resource."""
        try:
            async for response in observation.observation:
                if not self._running:
                    break
                self._process_response(response, uri)
        except asyncio.CancelledError:
            self.logger.debug(f"🔍 Observe loop cancelled for {uri}")
        except Exception as e:
            self.logger.error(f"❌ Observe error for {uri}: {e}")
            self.last_error = str(e)

    # ── Polling mode ─────────────────────────────────────────────────

    async def _run_poll(self) -> None:
        """Periodically GET CoAP resources."""
        import aiocoap

        resources = self._get_resource_uris()
        self.logger.info(
            f"🔄 Starting CoAP polling on {len(resources)} resource(s) "
            f"(interval: {self._poll_interval}s)"
        )

        while self._running:
            for uri in resources:
                try:
                    request = aiocoap.Message(code=aiocoap.GET, uri=uri)
                    response = await asyncio.wait_for(
                        self._context.request(request).response,
                        timeout=15.0,
                    )
                    self._process_response(response, uri)
                except asyncio.TimeoutError:
                    self.logger.warning(f"⏱️ Poll timeout for {uri}")
                except asyncio.CancelledError:
                    return
                except Exception as e:
                    self.logger.error(f"❌ Poll error for {uri}: {e}")
                    self.last_error = str(e)

            try:
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                return

    # ── Payload processing ───────────────────────────────────────────

    def _process_response(self, response, uri: str) -> None:
        """Convert a CoAP response into a DataMessage and emit it."""
        try:
            raw_payload = response.payload.decode("utf-8")

            # Attempt JSON parse; fall back to plain text
            try:
                data = json.loads(raw_payload)
            except (json.JSONDecodeError, ValueError):
                data = {"content": raw_payload, "raw": True}

            # Build a path-based sub-source ID (like MQTT topic → source ID)
            path = self._extract_path(uri)
            path_safe = path.replace("/", "_").lstrip("_")
            source_id = f"{self.source_id}_{path_safe}" if path_safe else self.source_id

            timestamp = (
                extract_timestamp(data.get("timestamp"))
                if isinstance(data, dict) and "timestamp" in data
                else datetime.now(timezone.utc).isoformat()
            )

            message = DataMessage(
                data=data,
                metadata={
                    "resource_uri": uri,
                    "coap_code": str(response.code),
                    "content_format": str(getattr(response.opt, "content_format", "unknown")),
                    "source_type": "coap",
                    "mode": self._mode,
                    "original_source_id": self.source_id,
                    "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
                },
                source_id=source_id,
                timestamp=timestamp,
                raw_payload=raw_payload,
            )

            self._emit_data(message)
            self._message_count += 1
            self._last_success = datetime.now(timezone.utc).isoformat()
            self.logger.debug(f"📥 Processed CoAP response from {uri}")

        except Exception as e:
            self.logger.error(f"❌ Error processing CoAP response from {uri}: {e}")

    # ── Health check ─────────────────────────────────────────────────

    async def health_check(self) -> ConnectorHealthResponse:
        """CoAP connector health check with standardized response."""
        resources = self._get_resource_uris()
        is_running = self._running
        healthy = is_running and self._context is not None and self.status == ConnectorStatus.ACTIVE

        connection_details: Dict[str, Any] = {
            "host": self.config.get("host"),
            "port": self.config.get("port", 5683),
            "mode": self._mode,
            "resources": resources,
            "active_observations": len(self._observations),
            "messages_received": self._message_count,
        }

        if self._mode == "poll":
            connection_details["poll_interval"] = self._poll_interval

        return ConnectorHealthResponse(
            status=self.status.value,
            healthy=healthy,
            running=is_running,
            last_successful_operation=self._last_success,
            error=self.last_error,
            connection_details=connection_details,
        )

    # ── Configuration & display info ─────────────────────────────────

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        """Return JSON schema for CoAP connector configuration."""
        return {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "CoAP server hostname or IP address",
                },
                "port": {
                    "type": "integer",
                    "default": 5683,
                    "minimum": 1,
                    "maximum": 65535,
                    "description": "CoAP server port (default: 5683)",
                },
                "resources": {
                    "oneOf": [
                        {"type": "string"},
                        {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                        },
                    ],
                    "description": "CoAP resource path(s) to observe or poll (e.g., /sensors/temperature)",
                },
                "mode": {
                    "type": "string",
                    "enum": ["observe", "poll"],
                    "default": "observe",
                    "description": "Ingestion mode: 'observe' for push notifications (recommended) or 'poll' for periodic GET requests",
                },
                "poll_interval": {
                    "type": "integer",
                    "minimum": 5,
                    "maximum": 3600,
                    "default": 60,
                    "description": "Polling interval in seconds (only used in poll mode)",
                },
                "scheme": {
                    "type": "string",
                    "enum": ["coap", "coaps"],
                    "default": "coap",
                    "description": "URI scheme: 'coap' (UDP) or 'coaps' (DTLS-secured)",
                },
            },
            "required": ["host", "resources"],
        }

    @classmethod
    def get_display_info(cls) -> Dict[str, Any]:
        """Return display information for the CoAP connector."""
        return {
            "name": "CoAP Server",
            "description": "Connect to CoAP servers for lightweight IoT data ingestion (UDP-based, observe/poll)",
            "icon": "📶",
            "category": "IoT",
            "supported_formats": ["JSON", "CBOR", "Plain Text"],
            "real_time": True,
        }

    # ── Helpers ───────────────────────────────────────────────────────

    def _get_resource_uris(self) -> List[str]:
        """Build full CoAP URIs from config."""
        host = self.config["host"]
        port = self.config.get("port", 5683)
        scheme = self.config.get("scheme", "coap")
        resources = self.config.get("resources", [])

        if isinstance(resources, str):
            resources = [resources]

        uris = []
        for resource in resources:
            # Ensure leading slash
            path = resource if resource.startswith("/") else f"/{resource}"
            uris.append(f"{scheme}://{host}:{port}{path}")
        return uris

    @staticmethod
    def _extract_path(uri: str) -> str:
        """Extract the path portion from a CoAP URI."""
        try:
            # coap://host:port/path/to/resource → /path/to/resource
            from urllib.parse import urlparse
            return urlparse(uri).path
        except Exception:
            return ""
