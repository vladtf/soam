#!/usr/bin/env python3
"""
MQTT Performance Test Script for SOAM Ingestor Throughput Testing.

Sends MQTT messages at a configurable rate to measure ingestor throughput capacity.

Usage:
    # Run locally (requires port-forward: kubectl port-forward svc/mosquitto 1883:1883)
    python tests/perf_test_mqtt.py --rate 100 --duration 30

    # High throughput test
    python tests/perf_test_mqtt.py --rate 500 --duration 60

    # Run inside the cluster
    kubectl cp tests/perf_test_mqtt.py <pod>:/tmp/perf_test_mqtt.py
    kubectl exec -it <pod> -- python /tmp/perf_test_mqtt.py --rate 1000 --duration 60
"""
import time
import json
import random
import paho.mqtt.client as mqttClient
import os
import logging
import threading
from datetime import datetime
import argparse
from collections import deque


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Configuration from environment or defaults
broker = os.getenv("MQTT_BROKER", "mosquitto")
sensor_id = os.getenv("SENSOR_ID", "perf_test_sensor")
port = 1883
topic = "smartcity/sensors/perf_test"

# Global counters for statistics
message_count = 0
error_count = 0
count_lock = threading.Lock()
stop_event = threading.Event()

# Rate limiting
target_rate = 100  # messages per second (will be set from args)
rate_window = deque(maxlen=1000)  # Track recent message timestamps


class RateLimitedPublisher:
    """Publisher that maintains a target message rate."""
    
    def __init__(self, client, thread_id: int, messages_per_thread: float):
        self.client = client
        self.thread_id = thread_id
        self.messages_per_second = messages_per_thread
        self.interval = 1.0 / self.messages_per_second if self.messages_per_second > 0 else 0.1
        self.local_count = 0
        self.local_errors = 0
        
    def run(self):
        """Publish messages at the configured rate."""
        global message_count, error_count
        
        next_send_time = time.time()
        
        while not stop_event.is_set():
            now = time.time()
            
            # Wait until it's time to send
            if now < next_send_time:
                sleep_time = next_send_time - now
                if sleep_time > 0:
                    time.sleep(min(sleep_time, 0.1))  # Max 100ms sleep to check stop_event
                continue
            
            # Send message
            try:
                payload = {
                    "temperature": round(random.uniform(10.0, 35.0), 2),
                    "humidity": round(random.uniform(20, 70), 2),
                    "timestamp": datetime.now().isoformat(),
                    "sensor_id": f"{sensor_id}_{self.thread_id}",
                    "thread_id": self.thread_id,
                    "sequence": self.local_count,
                }
                result = self.client.publish(topic, json.dumps(payload), qos=0)
                
                if result.rc == 0:
                    self.local_count += 1
                    with count_lock:
                        message_count += 1
                else:
                    self.local_errors += 1
                    with count_lock:
                        error_count += 1
                        
            except Exception as e:
                self.local_errors += 1
                with count_lock:
                    error_count += 1
                logger.error(f"Thread {self.thread_id} error: {e}")
            
            # Schedule next send
            next_send_time += self.interval
            
            # If we're falling behind, reset to now (don't try to catch up)
            if next_send_time < now - 1.0:
                next_send_time = now


def calculate_threads_needed(target_rate: int, max_rate_per_thread: int = 200) -> int:
    """Calculate the number of threads needed to achieve target rate.
    
    Args:
        target_rate: Target messages per second
        max_rate_per_thread: Maximum sustainable rate per thread (conservative estimate)
    
    Returns:
        Number of threads needed
    """
    threads = max(1, (target_rate + max_rate_per_thread - 1) // max_rate_per_thread)
    return min(threads, 50)  # Cap at 50 threads


def print_stats(duration: int, target_rate: int):
    """Print statistics periodically."""
    start_time = time.time()
    last_count = 0
    last_time = start_time
    
    while not stop_event.is_set():
        time.sleep(5)  # Print every 5 seconds
        now = time.time()
        elapsed = now - start_time
        current_count = message_count
        
        # Calculate rates
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
            f"Remaining: {remaining:.0f}s"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MQTT Performance Test with Rate Limiting")
    parser.add_argument("--rate", type=int, default=100, help="Target messages per second")
    parser.add_argument("--duration", type=int, default=30, help="Test duration in seconds")
    parser.add_argument("--broker", type=str, default=None, help="MQTT broker hostname")
    parser.add_argument("--threads", type=int, default=None, help="Override auto-calculated thread count")
    args = parser.parse_args()

    if args.broker:
        broker = args.broker

    target_rate = args.rate
    duration = args.duration
    
    # Calculate threads needed (or use override)
    if args.threads:
        num_threads = args.threads
    else:
        num_threads = calculate_threads_needed(target_rate)
    
    messages_per_thread = target_rate / num_threads

    logger.info(f"")
    logger.info(f"🚀 MQTT Performance Test with Rate Limiting")
    logger.info(f"{'='*60}")
    logger.info(f"   Broker: {broker}:{port}")
    logger.info(f"   Topic: {topic}")
    logger.info(f"   Target Rate: {target_rate} msg/s")
    logger.info(f"   Duration: {duration}s")
    logger.info(f"   Threads: {num_threads} (auto-calculated)" if not args.threads else f"   Threads: {num_threads} (manual)")
    logger.info(f"   Rate per Thread: {messages_per_thread:.1f} msg/s")
    logger.info(f"   Expected Total: ~{target_rate * duration:,} messages")
    logger.info(f"{'='*60}")
    logger.info(f"")

    # Connect to MQTT broker
    logger.info(f"Connecting to MQTT broker: {broker}:{port}")
    client = mqttClient.Client(mqttClient.CallbackAPIVersion.VERSION2)
    
    try:
        client.connect(broker, port, 60)
        client.loop_start()
    except Exception as e:
        logger.error(f"❌ Failed to connect to MQTT broker: {e}")
        exit(1)

    logger.info(f"✅ Connected to MQTT broker")
    logger.info(f"")

    # Start statistics thread
    stats_thread = threading.Thread(target=print_stats, args=(duration, target_rate), daemon=True)
    stats_thread.start()

    # Create and start worker threads
    start_time = time.time()
    threads = []
    publishers = []
    
    for i in range(num_threads):
        publisher = RateLimitedPublisher(client, i, messages_per_thread)
        publishers.append(publisher)
        thread = threading.Thread(target=publisher.run, daemon=True)
        threads.append(thread)
        thread.start()

    # Wait for duration
    try:
        time.sleep(duration)
    except KeyboardInterrupt:
        logger.info("\n⚠️ Interrupted by user")

    # Signal threads to stop
    stop_event.set()
    time.sleep(0.5)  # Give threads time to finish

    # Calculate final statistics
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
    
    if rate_accuracy >= 95:
        logger.info(f"✅ SUCCESS: Achieved target rate!")
    elif rate_accuracy >= 80:
        logger.info(f"⚠️ PARTIAL: Achieved {rate_accuracy:.0f}% of target rate")
        logger.info(f"   Tip: Try increasing threads with --threads {num_threads + 5}")
    else:
        logger.info(f"❌ BELOW TARGET: Only achieved {rate_accuracy:.0f}% of target rate")
        logger.info(f"   Tip: Network or broker may be bottleneck")

    # Cleanup
    client.loop_stop()
    client.disconnect()
    logger.info(f"")
    logger.info(f"✅ Test complete!")

