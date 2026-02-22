"""
Data connectors for various source types.

Auto-discovery: All *_connector.py modules in this package are imported
automatically, triggering their @ConnectorRegistry.register() decorators.
To add a new connector, just create a new file (e.g., coap_connector.py)
and decorate the class — no other changes needed.
"""
import importlib
import pkgutil
import logging
from pathlib import Path

from .base import (
    BaseDataConnector, 
    DataMessage, 
    ConnectorStatus, 
    ConnectorHealthResponse,
    ConnectorRegistry
)

logger = logging.getLogger(__name__)


def _auto_discover_connectors():
    """Auto-import all *_connector.py modules in this package to trigger registration."""
    package_dir = Path(__file__).parent
    for module_info in pkgutil.iter_modules([str(package_dir)]):
        module_name = module_info.name
        if module_name.endswith("_connector"):
            try:
                importlib.import_module(f".{module_name}", package=__name__)
                logger.debug(f"🔌 Auto-imported connector module: {module_name}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to import connector module {module_name}: {e}")


# Run auto-discovery on package import
_auto_discover_connectors()


__all__ = [
    'BaseDataConnector',
    'DataMessage', 
    'ConnectorStatus',
    'ConnectorHealthResponse',
    'ConnectorRegistry',
]