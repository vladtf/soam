"""
AoT (Array of Things) file-replay simulator.

Reads pre-extracted JSON data files and publishes messages via MQTT.
Loops continuously over the data so the simulator never stops.
Supports configurable publish rate and subsystem filtering.

Environment variables:
    MQTT_BROKER         - MQTT broker hostname (default: localhost)
    MQTT_PORT           - MQTT broker port (default: 1883)
    AOT_DATA_DIR        - Directory containing JSON data files (default: /data/aot)
    AOT_SUBSYSTEMS      - Comma-separated subsystems to replay, or "all" (default: all)
    AOT_RATE            - Target messages per second (default: 50)
    AOT_LOOP            - Whether to loop over data (default: true)
    SENSOR_ID           - Override sensor_id prefix (optional)
    EDGE_BUFFER_SIZE    - Max buffered messages when offline (default: 1000)
"""
import os
import json
import time
import glob
import logging
import random
from datetime import datetime, timezone
from .base import BaseSimulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class AotReplaySimulator(BaseSimulator):
    """Replays AoT JSON data files through MQTT, looping continuously."""

    def __init__(self):
        super().__init__("aot_replay", "smartcity/sensors/aot")

        self.data_dir = os.getenv("AOT_DATA_DIR", "/data/aot")
        self.target_rate = float(os.getenv("AOT_RATE", "50"))
        self.loop = os.getenv("AOT_LOOP", "true").lower() in ("true", "1", "yes")
        self.subsystem_filter = os.getenv("AOT_SUBSYSTEMS", "all")

        self.messages = []
        self._load_data()

    def _load_data(self):
        """Load JSON data files from the data directory."""
        if not os.path.isdir(self.data_dir):
            logger.error(f"❌ Data directory not found: {self.data_dir}")
            logger.info(f"🔍 Run extract_aot_data.py first to generate JSON files")
            return

        # Determine which files to load
        if self.subsystem_filter == "all":
            pattern = os.path.join(self.data_dir, "*.json")
            files = glob.glob(pattern)
        else:
            subsystems = [s.strip() for s in self.subsystem_filter.split(",")]
            files = []
            for sub in subsystems:
                path = os.path.join(self.data_dir, f"{sub}.json")
                if os.path.exists(path):
                    files.append(path)
                else:
                    logger.warning(f"⚠️ File not found for subsystem '{sub}': {path}")

        if not files:
            logger.error(f"❌ No JSON data files found in {self.data_dir}")
            return

        # Load all messages
        for filepath in sorted(files):
            filename = os.path.basename(filepath)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.messages.extend(data)
                logger.info(f"📂 Loaded {len(data):,} messages from {filename}")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"❌ Failed to load {filename}: {e}")

        logger.info(f"📊 Total messages loaded: {len(self.messages):,}")
        logger.info(f"🎯 Target rate: {self.target_rate} msg/s")
        logger.info(f"🔁 Loop mode: {self.loop}")

    def generate_payload(self):
        """Not used — run() is overridden for file replay."""
        return {}

    def run(self):
        """Replay messages from loaded data files at the configured rate."""
        if not self.messages:
            logger.error("❌ No messages to replay. Exiting.")
            return

        # Connect to MQTT
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        try:
            logger.info(f"[{self.sensor_id}] 🔌 Connecting to {self.broker}:{self.port}...")
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()

            # Wait for connection
            retries = 0
            while not self._connected and retries < 30:
                time.sleep(1)
                retries += 1

            if not self._connected:
                logger.error("❌ Could not connect to MQTT broker. Exiting.")
                return

            interval = 1.0 / self.target_rate if self.target_rate > 0 else 0.02
            loop_count = 0
            total_published = 0

            while True:
                loop_count += 1
                logger.info(f"🚀 Starting replay loop #{loop_count} ({len(self.messages):,} messages)")

                for i, msg in enumerate(self.messages):
                    topic = msg.get("topic", self.topic)
                    payload = msg.get("payload", msg)

                    # Update timestamp to current time for realistic ingestion
                    payload["timestamp"] = datetime.now(timezone.utc).isoformat()
                    # Keep original timestamp for reference
                    if "original_timestamp" not in payload:
                        payload["original_timestamp"] = msg.get("payload", {}).get("timestamp", "")

                    self._publish(topic, payload)
                    total_published += 1

                    # Rate limiting
                    time.sleep(interval)

                    # Progress logging every 10000 messages
                    if total_published % 10000 == 0:
                        logger.info(
                            f"📊 Progress: {total_published:,} published "
                            f"(loop {loop_count}, message {i+1}/{len(self.messages)})"
                        )

                logger.info(
                    f"✅ Loop #{loop_count} complete. "
                    f"Total published: {total_published:,}"
                )

                if not self.loop:
                    logger.info("🏁 Single-pass mode — stopping.")
                    break

                # Small pause between loops
                logger.info("🔁 Restarting from beginning...")
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info(f"[{self.sensor_id}] Replay stopped by user.")
        except Exception as e:
            logger.error(f"[{self.sensor_id}] ❌ Error: {e}")
        finally:
            pending = self._buffer.count()
            if pending > 0:
                logger.warning(f"[{self.sensor_id}] ⚠️ {pending} messages still buffered")
            logger.info(f"📊 Total messages published: {total_published:,}")
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == "__main__":
    simulator = AotReplaySimulator()
    simulator.run()
