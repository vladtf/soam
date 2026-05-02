#!/usr/bin/env python3
"""
MQTT Performance Test with Real AoT (Array of Things) Data.

Publishes real heterogeneous sensor data from the AoT Chicago dataset at a
configurable rate. Loops continuously over the data for sustained load testing.
Reports throughput statistics identical to perf_test_mqtt.py for comparison.

Usage:
    # Run locally (requires port-forward: kubectl port-forward svc/mosquitto 1883:1883)
    python tests/aot/perf_test_aot.py --rate 100 --duration 60 --data tests/aot/data/aot_slice.json

    # High throughput test with full extraction
    python tests/aot/perf_test_aot.py --rate 500 --duration 300 --data tests/aot/data

    # Run inside the cluster (data mounted at /data/aot)
    python /scripts/perf_test_aot.py --rate 500 --duration 300 --data /data/aot --broker mosquitto
"""
import time
import json
import glob
import os
import sys
import logging
import threading
import argparse
from datetime import datetime, timezone
from collections import deque, defaultdict

import paho.mqtt.client as mqttClient


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Global counters
message_count = 0
error_count = 0
count_lock = threading.Lock()
stop_event = threading.Event()

# Per-topic counters for heterogeneity reporting
topic_counts = defaultdict(int)
sensor_types_seen = set()
topic_lock = threading.Lock()


def load_data(data_path: str) -> list:
    """Load JSON data from a file or directory of files.

    Returns a list of {"topic": ..., "payload": ...} dicts.
    """
    messages = []

    if os.path.isfile(data_path):
        # Single file
        with open(data_path, "r", encoding="utf-8") as f:
            messages = json.load(f)
        logger.info(f"📂 Loaded {len(messages):,} messages from {os.path.basename(data_path)}")
    elif os.path.isdir(data_path):
        # Directory — load all JSON files
        files = sorted(glob.glob(os.path.join(data_path, "*.json")))
        if not files:
            logger.error(f"❌ No JSON files found in {data_path}")
            sys.exit(1)
        for filepath in files:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            messages.extend(data)
            logger.info(f"📂 Loaded {len(data):,} messages from {os.path.basename(filepath)}")
    else:
        logger.error(f"❌ Data path not found: {data_path}")
        sys.exit(1)

    if not messages:
        logger.error("❌ No messages loaded")
        sys.exit(1)

    # Analyze data diversity
    topics = set()
    subsystems = set()
    sensors = set()
    parameters = set()
    for m in messages:
        topics.add(m.get("topic", "unknown"))
        p = m.get("payload", {})
        subsystems.add(p.get("subsystem", "unknown"))
        sensors.add(f"{p.get('subsystem')}/{p.get('sensor')}")
        parameters.add(p.get("parameter", "unknown"))

    logger.info(f"📊 Data diversity: {len(topics)} topics, {len(subsystems)} subsystems, "
                f"{len(sensors)} sensors, {len(parameters)} parameters")

    return messages


class AotPublisher:
    """Rate-limited publisher that cycles through real AoT data."""

    def __init__(self, client, thread_id: int, messages: list,
                 messages_per_second: float, offset: int):
        self.client = client
        self.thread_id = thread_id
        self.messages = messages
        self.messages_per_second = messages_per_second
        self.interval = 1.0 / messages_per_second if messages_per_second > 0 else 0.02
        self.offset = offset  # Start position in data (each thread starts at a different point)
        self.local_count = 0
        self.local_errors = 0

    def run(self):
        """Publish messages at the configured rate, looping over data."""
        global message_count, error_count

        idx = self.offset
        total_msgs = len(self.messages)
        next_send_time = time.time()

        while not stop_event.is_set():
            now = time.time()

            if now < next_send_time:
                sleep_time = next_send_time - now
                if sleep_time > 0:
                    time.sleep(min(sleep_time, 0.1))
                continue

            try:
                msg = self.messages[idx % total_msgs]
                topic = msg.get("topic", "smartcity/sensors/aot")
                payload = dict(msg.get("payload", msg))

                # Stamp with current time for realistic ingestion
                payload["timestamp"] = datetime.now(timezone.utc).isoformat()
                payload["_thread"] = self.thread_id
                payload["_seq"] = self.local_count

                result = self.client.publish(topic, json.dumps(payload), qos=0)

                if result.rc == 0:
                    self.local_count += 1
                    with count_lock:
                        message_count += 1
                    with topic_lock:
                        topic_counts[topic] += 1
                        sensor_types_seen.add(
                            f"{payload.get('subsystem', '?')}/{payload.get('sensor', '?')}/{payload.get('parameter', '?')}"
                        )
                else:
                    self.local_errors += 1
                    with count_lock:
                        error_count += 1

            except Exception as e:
                self.local_errors += 1
                with count_lock:
                    error_count += 1
                logger.error(f"Thread {self.thread_id} error: {e}")

            idx += 1
            next_send_time += self.interval

            # If falling behind, reset
            if next_send_time < now - 1.0:
                next_send_time = now


def calculate_threads_needed(target_rate: int, max_rate_per_thread: int = 200) -> int:
    """Calculate number of threads needed for target rate."""
    threads = max(1, (target_rate + max_rate_per_thread - 1) // max_rate_per_thread)
    return min(threads, 50)


def print_stats(duration: int, target_rate: int):
    """Print statistics periodically."""
    start_time = time.time()
    last_count = 0
    last_time = start_time

    while not stop_event.is_set():
        time.sleep(5)
        now = time.time()
        elapsed = now - start_time
        current_count = message_count

        total_rate = current_count / elapsed if elapsed > 0 else 0
        interval_count = current_count - last_count
        interval_time = now - last_time
        interval_rate = interval_count / interval_time if interval_time > 0 else 0

        last_count = current_count
        last_time = now

        remaining = max(0, duration - elapsed)
        rate_accuracy = (interval_rate / target_rate * 100) if target_rate > 0 else 0

        status = "✅" if 90 <= rate_accuracy <= 110 else "⚠️" if rate_accuracy > 0 else "❌"

        logger.info(
            f"📊 Stats: {current_count:,} msgs | "
            f"Rate: {interval_rate:.1f}/{target_rate} msg/s ({rate_accuracy:.0f}%) {status} | "
            f"Avg: {total_rate:.1f} msg/s | "
            f"Errors: {error_count} | "
            f"Topics: {len(topic_counts)} | "
            f"Sensors: {len(sensor_types_seen)} | "
            f"Remaining: {remaining:.0f}s"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="MQTT Performance Test with Real AoT Data"
    )
    parser.add_argument("--rate", type=int, default=100, help="Target messages per second")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--broker", type=str, default=None, help="MQTT broker hostname")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--threads", type=int, default=None, help="Override thread count")
    parser.add_argument("--data", type=str, required=True,
                        help="Path to JSON file or directory of JSON files")
    args = parser.parse_args()

    broker = args.broker or os.getenv("MQTT_BROKER", "mosquitto")
    port = args.port
    target_rate = args.rate
    duration = args.duration

    # Load data
    messages = load_data(args.data)

    # Calculate threads
    if args.threads:
        num_threads = args.threads
    else:
        num_threads = calculate_threads_needed(target_rate)
    messages_per_thread = target_rate / num_threads

    logger.info(f"")
    logger.info(f"🚀 MQTT Performance Test — Real AoT Data")
    logger.info(f"{'='*60}")
    logger.info(f"   Broker: {broker}:{port}")
    logger.info(f"   Data: {args.data} ({len(messages):,} messages)")
    logger.info(f"   Target Rate: {target_rate} msg/s")
    logger.info(f"   Duration: {duration}s")
    logger.info(f"   Threads: {num_threads}" +
                (" (auto)" if not args.threads else " (manual)"))
    logger.info(f"   Rate per Thread: {messages_per_thread:.1f} msg/s")
    logger.info(f"   Expected Total: ~{target_rate * duration:,} messages")
    logger.info(f"   Data loops: ~{(target_rate * duration) / len(messages):.1f}x")
    logger.info(f"{'='*60}")
    logger.info(f"")

    # Connect
    logger.info(f"Connecting to MQTT broker: {broker}:{port}")
    client = mqttClient.Client(mqttClient.CallbackAPIVersion.VERSION2)

    try:
        client.connect(broker, port, 60)
        client.loop_start()
    except Exception as e:
        logger.error(f"❌ Failed to connect to MQTT broker: {e}")
        sys.exit(1)

    logger.info(f"✅ Connected to MQTT broker")
    logger.info(f"")

    # Start stats thread
    stats_thread = threading.Thread(
        target=print_stats, args=(duration, target_rate), daemon=True
    )
    stats_thread.start()

    # Start publisher threads, each offset into the data
    start_time = time.time()
    threads_list = []
    chunk_size = len(messages) // num_threads

    for i in range(num_threads):
        publisher = AotPublisher(
            client, i, messages, messages_per_thread,
            offset=i * chunk_size
        )
        thread = threading.Thread(target=publisher.run, daemon=True)
        threads_list.append(thread)
        thread.start()

    # Wait for duration
    try:
        time.sleep(duration)
    except KeyboardInterrupt:
        logger.info("\n⚠️ Interrupted by user")

    stop_event.set()
    time.sleep(0.5)

    # Final results
    elapsed = time.time() - start_time
    final_rate = message_count / elapsed if elapsed > 0 else 0
    rate_accuracy = (final_rate / target_rate * 100) if target_rate > 0 else 0

    logger.info(f"")
    logger.info(f"{'='*60}")
    logger.info(f"📊 FINAL RESULTS")
    logger.info(f"{'='*60}")
    logger.info(f"   Target Rate: {target_rate} msg/s")
    logger.info(f"   Achieved Rate: {final_rate:.2f} msg/s ({rate_accuracy:.1f}% of target)")
    logger.info(f"   Total Messages Sent: {message_count:,}")
    logger.info(f"   Expected Messages: ~{target_rate * duration:,}")
    logger.info(f"   Total Errors: {error_count:,}")
    logger.info(f"   Duration: {elapsed:.2f}s")
    logger.info(f"   Threads Used: {num_threads}")
    logger.info(f"{'='*60}")
    logger.info(f"")
    logger.info(f"📊 DATA HETEROGENEITY")
    logger.info(f"{'='*60}")
    logger.info(f"   MQTT Topics: {len(topic_counts)}")
    for t, c in sorted(topic_counts.items()):
        logger.info(f"     {t}: {c:,} msgs")
    logger.info(f"   Unique sensor types: {len(sensor_types_seen)}")
    for s in sorted(sensor_types_seen):
        logger.info(f"     {s}")
    logger.info(f"{'='*60}")
    logger.info(f"")

    if rate_accuracy >= 95:
        logger.info(f"✅ SUCCESS: Achieved target rate!")
    elif rate_accuracy >= 80:
        logger.info(f"⚠️ PARTIAL: Achieved {rate_accuracy:.0f}% of target rate")
        logger.info(f"   Tip: Try increasing threads with --threads {num_threads + 5}")
    else:
        logger.info(f"❌ BELOW TARGET: Only achieved {rate_accuracy:.0f}% of target rate")
        logger.info(f"   Tip: Network or broker may be bottleneck")

    client.loop_stop()
    client.disconnect()
    logger.info(f"")
    logger.info(f"✅ Test complete!")
