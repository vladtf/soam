"""
CoAP Sensor Simulator for SOAM Smart City Platform.

Runs a CoAP server that exposes observable resources simulating IoT sensors.
The ingestor's CoAP connector can OBSERVE these resources to receive push
notifications whenever new readings are generated.

Resources exposed:
  /sensors/temperature  - Temperature & humidity sensor (observe + poll)
  /.well-known/core     - CoAP resource discovery (RFC 6690)

Each resource updates on a configurable interval and notifies all observers
automatically via aiocoap's ObservableResource support.
"""
import asyncio
import json
import logging
import os
import random
import signal
from datetime import datetime, timezone

import aiocoap
import aiocoap.resource as resource

# ── Configuration ────────────────────────────────────────────────────
UPDATE_INTERVAL = int(os.getenv("COAP_UPDATE_INTERVAL", "10"))  # seconds between readings
COAP_PORT = int(os.getenv("COAP_PORT", "5683"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ── Sensor Data Generators ──────────────────────────────────────────

def generate_temperature_data() -> dict:
    """Generate temperature & humidity sensor data.
    
    Mimics the MQTT temperature simulator with time-of-day variation.
    """
    current_hour = datetime.now().hour

    if 0 <= current_hour < 6:       # Night
        base_temp = random.uniform(5.0, 15.0)
        humidity = random.uniform(60, 90)
    elif 6 <= current_hour < 12:    # Morning
        base_temp = random.uniform(15.0, 25.0)
        humidity = random.uniform(50, 80)
    elif 12 <= current_hour < 18:   # Afternoon
        base_temp = random.uniform(25.0, 35.0)
        humidity = random.uniform(30, 60)
    else:                           # Evening
        base_temp = random.uniform(15.0, 25.0)
        humidity = random.uniform(50, 80)

    return {
        "sensor_id": "coap_temp_sensor",
        "temperature": round(base_temp + random.uniform(-1, 1), 2),
        "humidity": round(humidity + random.uniform(-5, 5), 2),
    }


# ── Observable CoAP Resources ───────────────────────────────────────

class SensorResource(resource.ObservableResource):
    """
    Generic observable CoAP resource backed by a data-generation function.

    Observers are notified every ``interval`` seconds with fresh sensor data.
    GET requests without the observe option return the latest reading.
    """

    def __init__(self, name: str, generator, interval: int = UPDATE_INTERVAL):
        super().__init__()
        self.name = name
        self._generator = generator
        self._interval = interval
        self._latest: bytes = b""
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start the periodic update loop."""
        self._task = asyncio.create_task(self._update_loop())
        logger.info(f"📡 Resource /{self.name} started (interval={self._interval}s)")

    async def _update_loop(self):
        """Generate new data at fixed intervals and notify observers."""
        while True:
            try:
                payload = self._generator()
                payload["timestamp"] = datetime.now(timezone.utc).isoformat()
                self._latest = json.dumps(payload).encode("utf-8")
                self.updated_state()  # notifies all observers
                logger.info(f"📤 /{self.name}: {payload}")
            except Exception as e:
                logger.error(f"❌ /{self.name} update error: {e}")
            await asyncio.sleep(self._interval)

    async def render_get(self, request):
        """Handle GET (and observe) requests."""
        if not self._latest:
            # Generate an initial reading if none exists yet
            payload = self._generator()
            payload["timestamp"] = datetime.now(timezone.utc).isoformat()
            self._latest = json.dumps(payload).encode("utf-8")

        return aiocoap.Message(
            payload=self._latest,
            content_format=aiocoap.numbers.media_types_rev["application/json"],
        )


# ── Server Setup ─────────────────────────────────────────────────────

async def main():
    logger.info(f"🚀 CoAP Sensor Simulator starting on port {COAP_PORT}")
    logger.info(f"   Update interval: {UPDATE_INTERVAL}s")

    root = resource.Site()

    # Register sensor resources
    temperature = SensorResource("sensors/temperature", generate_temperature_data)

    root.add_resource(["sensors", "temperature"], temperature)
    root.add_resource(
        [".well-known", "core"],
        resource.WKCResource(root.get_resources_as_linkheader),
    )

    # Bind server
    context = await aiocoap.Context.create_server_context(root, bind=("::", COAP_PORT))

    # Start data generation loops
    await temperature.start()

    logger.info(f"✅ CoAP server listening on port {COAP_PORT}")
    logger.info("   Resources: /sensors/temperature, /.well-known/core")

    # Run until terminated
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown_event.set)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    try:
        await shutdown_event.wait()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("🛑 Shutting down CoAP simulator...")
        await context.shutdown()
        logger.info("✅ CoAP simulator stopped")


if __name__ == "__main__":
    asyncio.run(main())
