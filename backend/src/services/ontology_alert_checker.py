"""
Ontology Alert Checker — detects sensor fields not recognized by the OWL ontology.

Compares field names from the ingestor metadata against properties defined
in the ontology. Returns alerts for any unrecognized fields so operators
can update the ontology or investigate unexpected data.
"""
import json
from typing import List, Dict, Any, Set

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Fields that are structural (not sensor data) and should be ignored
_STRUCTURAL_FIELDS = frozenset({
    "ingestion_id", "timestamp", "device_id", "sensor_type",
    "raw_json", "source_protocol", "date", "hour",
})


def _get_ingestor_field_names() -> Set[str]:
    """Fetch all known field names from the ingestor metadata.

    Uses a synchronous HTTP call — lightweight and bounded.
    """
    from src.services.ingestor_schema_client import IngestorSchemaClient

    client = IngestorSchemaClient()
    datasets = client.get_schema_info_sync()

    # The ingestor API wraps the list: {"datasets": [...], "total": N}
    # get_schema_info_sync() may return that wrapper dict or a plain list
    if isinstance(datasets, dict):
        datasets = datasets.get("datasets", [])

    field_names: Set[str] = set()
    for dataset in datasets:
        schema_fields = dataset.get("schema_fields", [])
        if isinstance(schema_fields, str):
            try:
                schema_fields = json.loads(schema_fields)
            except (json.JSONDecodeError, TypeError):
                continue
        for field in schema_fields:
            name = field.get("name")
            if name:
                field_names.add(name)
    return field_names


def _normalize_field_names(field_names: Set[str]) -> Set[str]:
    """Apply normalization rules to map raw field names to their canonical forms.

    Reuses the same DB-backed rules that DataCleaner applies during enrichment,
    so fields that will be renamed at processing time are not flagged as unknown.
    """
    from src.spark.enrichment.cleaner import DataCleaner

    cleaner = DataCleaner()
    rules = cleaner._load_dynamic_rules()  # global rules (raw_key_lower → canonical_key)

    normalized: Set[str] = set()
    for name in field_names:
        canonical = rules.get(name.lower(), name)
        normalized.add(canonical)
    return normalized


def check_ontology_fields(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return alerts for sensor fields not defined in the OWL ontology."""
    try:
        from src.neo4j.ontology_service import get_ontology_service
        ontology = get_ontology_service()
    except FileNotFoundError:
        logger.warning("⚠️ Ontology file not found — skipping ontology alert check")
        return []

    try:
        ingestor_fields = _get_ingestor_field_names()
    except Exception as e:
        logger.warning("⚠️ Could not fetch ingestor fields for ontology check: %s", e)
        return []

    # Sensor data fields = all fields minus structural ones
    sensor_fields = ingestor_fields - _STRUCTURAL_FIELDS

    # Apply normalization rules so fields that will be renamed during
    # enrichment (e.g. "temp" → "temperature") are checked by their
    # canonical name, not the raw name.
    sensor_fields = _normalize_field_names(sensor_fields)
    # Re-filter structural fields that may appear after normalization
    sensor_fields -= _STRUCTURAL_FIELDS

    canonical_props = set(ontology.get_canonical_property_names())
    unrecognized = sorted(sensor_fields - canonical_props)

    if not unrecognized:
        return []

    logger.info(
        "🔍 Ontology check: %d unrecognized field(s) out of %d sensor fields: %s",
        len(unrecognized), len(sensor_fields), unrecognized,
    )

    alerts: List[Dict[str, Any]] = []
    for field_name in unrecognized:
        alerts.append({
            "id": f"ontology-unknown-{field_name}",
            "message": (
                f'Sensor field "{field_name}" is not defined in the ontology. '
                "Consider updating the ontology or reviewing the data source."
            ),
            "variant": "info",
            "link": "/ontology",
            "linkText": "View Ontology",
            "dismissible": True,
        })

    return alerts


def register_ontology_alert_checker(service) -> None:
    """Register the ontology field checker with the alert service."""
    service.register("ontology_fields", check_ontology_fields)
