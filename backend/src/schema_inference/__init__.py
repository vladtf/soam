"""
Schema inference package for SOAM backend.

This package provides async schema inference capabilities for processing
bronze layer data and maintaining schema information.
"""

from .async_stream import AsyncSchemaInferenceStream
from .manager import SchemaInferenceManager
from .models import SchemaInfo, SchemaInferenceLog
from .service import SchemaService

__all__ = [
    "AsyncSchemaInferenceStream",
    "SchemaInferenceManager", 
    "SchemaInfo",
    "SchemaInferenceLog",
    "SchemaService"
]
