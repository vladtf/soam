"""
Simple in-memory buffer for edge devices.
Stores messages when MQTT is unavailable and replays when connected.
"""
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class BufferedMessage:
    """A buffered MQTT message."""
    topic: str
    payload: Dict[str, Any]


class EdgeBuffer:
    """
    In-memory FIFO buffer for offline tolerance.
    Messages are queued when MQTT is down and replayed when back online.
    """
    
    def __init__(self, sensor_id: str, max_size: int = 1000):
        self.sensor_id = sensor_id
        self._buffer: deque = deque(maxlen=max_size)
    
    def add(self, topic: str, payload: Dict[str, Any]) -> None:
        """Add a message to the buffer."""
        self._buffer.append(BufferedMessage(topic=topic, payload=payload))
        logger.info(f"[{self.sensor_id}] 📦 Buffered message ({len(self._buffer)} pending)")
    
    def pop(self) -> Optional[BufferedMessage]:
        """Remove and return the oldest message, or None if empty."""
        if self._buffer:
            return self._buffer.popleft()
        return None
    
    def has_pending(self) -> bool:
        """Check if there are pending messages."""
        return len(self._buffer) > 0
    
    def count(self) -> int:
        """Get number of buffered messages."""
        return len(self._buffer)
