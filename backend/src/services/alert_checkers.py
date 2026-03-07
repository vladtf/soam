"""
Alert checkers — each function checks for a specific condition and
returns a list of alert dicts. Register new checkers here.
"""
from typing import List, Dict, Any

from src.database.models import Device
from src.utils.logging import get_logger

logger = get_logger(__name__)


def check_unlinked_devices(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return alerts for sensors owned by the user that aren't linked to a building."""
    username = context["username"]
    db = context["db"]
    neo4j = context.get("neo4j")

    user_devices = db.query(Device).filter(Device.created_by == username).all()
    if not user_devices or not neo4j or not neo4j.driver:
        return []

    alerts: List[Dict[str, Any]] = []
    for device in user_devices:
        if not device.ingestion_id:
            continue
        with neo4j.driver.session() as session:
            result = session.run(
                "MATCH (s:Sensor {sensorId: $sid})-[:locatedIn]->(:Building) "
                "RETURN count(s) AS linked",
                sid=device.ingestion_id,
            )
            rec = result.single()
            if not rec or rec["linked"] == 0:
                alerts.append({
                    "id": f"unlinked-{device.ingestion_id}",
                    "message": f'"{device.name or device.ingestion_id}" is not linked to any building.',
                    "variant": "warning",
                    "link": "/ontology",
                    "linkText": "Link it now",
                    "dismissible": True,
                })
    return alerts


def register_all_alert_checkers(service) -> None:
    """Register all alert checkers with the alert service."""
    service.register("unlinked_devices", check_unlinked_devices)
