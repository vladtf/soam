"""
Alert Service — decoupled alert registry.

Features register alert checker functions at startup. The alert endpoint
runs all checkers for the current user and returns aggregated results.
"""
from typing import Callable, List, Dict, Any
from src.utils.logging import get_logger

logger = get_logger(__name__)


class AlertService:
    """Singleton registry for alert checker functions.

    Each checker receives a context dict (with 'username', 'db', 'neo4j',
    etc.) and returns a list of alert dicts.
    """

    def __init__(self) -> None:
        self._checkers: List[Dict[str, Any]] = []

    def register(self, name: str, checker: Callable[..., List[Dict[str, Any]]]) -> None:
        """Register a named alert checker function."""
        self._checkers.append({"name": name, "fn": checker})
        logger.info("📋 Registered alert checker: %s", name)

    def collect(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run all registered checkers and return aggregated alerts."""
        alerts: List[Dict[str, Any]] = []
        for entry in self._checkers:
            try:
                result = entry["fn"](context)
                alerts.extend(result)
            except Exception as e:
                logger.warning("⚠️ Alert checker '%s' failed: %s", entry["name"], e)
        return alerts


# Module-level singleton
alert_service = AlertService()
