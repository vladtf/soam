import os
from dataclasses import dataclass

@dataclass
class ConnectionConfig:
    """Class to represent connection configuration."""
    id: int
    broker: str
    port: int
    topic: str
    connectionType: str = "mqtt"
