"""
Auto-registration of default / built-in data sources.

Declares a list of data sources that should exist on every fresh deployment.
On startup the registry checks each entry and creates + enables it if missing.

To add a new default data source, simply append to ``DEFAULT_DATA_SOURCES``.
"""
import logging
from typing import Any, Dict, List

from src.database.database import get_db
from src.database.models import DataSource
from src.services.data_source_service import DataSourceRegistry

logger = logging.getLogger(__name__)


# ── Declarative list of default data sources ─────────────────────────
# Each entry maps directly to DataSourceRegistry.create_data_source() args.

DEFAULT_DATA_SOURCES: List[Dict[str, Any]] = [
    {
        "name": "Local Simulators MQTT",
        "type_name": "mqtt",
        "config": {
            "broker": "mosquitto",
            "port": 1883,
            "topics": ["smartcity/sensors/#"],
        },
    },
    {
        "name": "CoAP Temperature Simulator",
        "type_name": "coap",
        "config": {
            "host": "coap-simulator",
            "port": 5683,
            "resources": ["/sensors/temperature"],
            "mode": "observe",
        },
    },
]


def auto_register_default_sources(registry: DataSourceRegistry) -> None:
    """
    Ensure every entry in ``DEFAULT_DATA_SOURCES`` exists and is enabled.

    Idempotent — safe to call on every startup.
    """
    existing_sources = registry.get_data_sources(enabled_only=False)

    for default in DEFAULT_DATA_SOURCES:
        name = default["name"]
        type_name = default["type_name"]

        already_exists = any(
            s.name == name and s.type_name == type_name for s in existing_sources
        )

        if already_exists:
            logger.info(f"ℹ️ Default data source already exists: {name}")
            continue

        try:
            logger.info(f"🔧 Auto-registering default data source: {name} ({type_name})...")
            source_id = registry.create_data_source(
                name=name,
                type_name=type_name,
                config=default["config"],
                created_by="system_auto_register",
            )
            logger.info(f"✅ Registered {name} with ID: {source_id}")

            _enable_source(source_id)
        except Exception as e:
            logger.error(f"⚠️ Failed to auto-register {name}: {e}")
            # Continue with remaining sources


def _enable_source(source_id: int) -> None:
    """Enable a data source by ID (best-effort)."""
    try:
        db = next(get_db())
        try:
            source = db.query(DataSource).filter(DataSource.id == source_id).first()
            if source:
                source.enabled = True
                db.commit()
                logger.info(f"✅ Auto-enabled data source ID {source_id}")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"⚠️ Could not auto-enable data source {source_id}: {e}")
