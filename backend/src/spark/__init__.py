"""
Spark module for the SOAM smart city platform.

This module provides a modular Spark integration for real-time data processing,
including session management, streaming operations, data access, and diagnostics.
"""

from .spark_manager import SparkManager
from .config import SparkConfig, SparkSchemas
from .session import SparkSessionManager
from .streaming import StreamingManager
from .data_access import DataAccessManager
from .diagnostics import SparkDiagnostics
from .master_client import SparkMasterClient

__all__ = [
    "SparkManager",
    "SparkConfig",
    "SparkSchemas",
    "SparkSessionManager",
    "StreamingManager",
    "DataAccessManager",
    "SparkDiagnostics",
    "SparkMasterClient",
]
