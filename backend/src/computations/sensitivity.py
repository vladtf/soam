"""Sensitivity calculation utilities for computations."""
import re
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from src.database.models import Device, DataSensitivity
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Sensitivity levels ordered from lowest to highest
SENSITIVITY_ORDER = [
    DataSensitivity.PUBLIC,
    DataSensitivity.INTERNAL,
    DataSensitivity.CONFIDENTIAL,
    DataSensitivity.RESTRICTED,
]

# Map user roles to maximum allowed sensitivity level
ROLE_SENSITIVITY_ACCESS = {
    "viewer": DataSensitivity.PUBLIC,
    "user": DataSensitivity.INTERNAL,
    "admin": DataSensitivity.RESTRICTED,  # Admins can access all
}


def get_sensitivity_level(sensitivity: DataSensitivity) -> int:
    """Get numeric level for sensitivity (higher = more sensitive)."""
    try:
        return SENSITIVITY_ORDER.index(sensitivity)
    except (ValueError, TypeError):
        return 0  # Default to PUBLIC level


def get_highest_sensitivity(sensitivities: List[DataSensitivity]) -> DataSensitivity:
    """Get the highest sensitivity level from a list."""
    if not sensitivities:
        return DataSensitivity.PUBLIC
    
    max_level = 0
    for sens in sensitivities:
        level = get_sensitivity_level(sens)
        if level > max_level:
            max_level = level
    
    return SENSITIVITY_ORDER[max_level] if max_level < len(SENSITIVITY_ORDER) else DataSensitivity.RESTRICTED


def can_access_sensitivity(user_roles: List[str], sensitivity: DataSensitivity) -> bool:
    """Check if user with given roles can access data with given sensitivity."""
    if not user_roles:
        return sensitivity == DataSensitivity.PUBLIC
    
    # Get the highest access level from user's roles
    max_access_level = 0
    for role in user_roles:
        role_lower = role.lower()
        if role_lower in ROLE_SENSITIVITY_ACCESS:
            access_sensitivity = ROLE_SENSITIVITY_ACCESS[role_lower]
            access_level = get_sensitivity_level(access_sensitivity)
            if access_level > max_access_level:
                max_access_level = access_level
    
    # User can access if their max access level >= sensitivity level
    sensitivity_level = get_sensitivity_level(sensitivity)
    return max_access_level >= sensitivity_level


def get_restriction_message(sensitivity: DataSensitivity, user_roles: List[str]) -> str:
    """Generate a user-friendly restriction message."""
    sensitivity_labels = {
        DataSensitivity.PUBLIC: "Public",
        DataSensitivity.INTERNAL: "Internal",
        DataSensitivity.CONFIDENTIAL: "Confidential",
        DataSensitivity.RESTRICTED: "Restricted",
    }
    
    required_role = "admin"
    if sensitivity == DataSensitivity.INTERNAL:
        required_role = "user or admin"
    elif sensitivity == DataSensitivity.CONFIDENTIAL:
        required_role = "admin"
    elif sensitivity == DataSensitivity.RESTRICTED:
        required_role = "admin with audit access"
    
    label = sensitivity_labels.get(sensitivity, "Unknown")
    
    # Format user's current roles for display
    if user_roles:
        current_roles = ", ".join(user_roles)
        return f"This tile contains {label} data. Required role: {required_role}. Your current roles: [{current_roles}]."
    else:
        return f"This tile contains {label} data. Required role: {required_role}. You are not authenticated."


def extract_device_references_from_definition(definition: dict) -> List[str]:
    """
    Extract potential device/ingestion_id references from a computation definition.
    
    Looks for patterns in WHERE conditions like:
    - {"col": "ingestion_id", "op": "==", "value": "xxx"}
    - {"col": "sensor_id", "op": "==", "value": "xxx"}
    - References in select statements to specific devices
    """
    references = set()
    
    if not definition:
        return []
    
    # Check WHERE conditions
    where_clauses = definition.get("where", [])
    if isinstance(where_clauses, list):
        for clause in where_clauses:
            if isinstance(clause, dict):
                col = str(clause.get("col", "")).lower()
                value = clause.get("value")
                
                # Check if the column is a device identifier
                if col in ["ingestion_id", "sensor_id", "device_id", "sensorid"]:
                    if isinstance(value, str) and value:
                        references.add(value)
                    elif isinstance(value, list):
                        # Handle IN-like conditions
                        for v in value:
                            if isinstance(v, str) and v:
                                references.add(v)
    
    # Check SELECT for explicit device references
    select_clauses = definition.get("select", [])
    if isinstance(select_clauses, list):
        for clause in select_clauses:
            if isinstance(clause, str):
                # Look for patterns like "device_xxx" or explicit device references
                clause_lower = clause.lower()
                if 'ingestion_id' in clause_lower or 'sensor_id' in clause_lower:
                    # Try to extract value after = sign
                    import re
                    matches = re.findall(r"['\"]([^'\"]+)['\"]", clause)
                    references.update(matches)
    
    return list(references)


def calculate_computation_sensitivity(
    db: Session,
    definition: dict
) -> Tuple[DataSensitivity, List[str]]:
    """
    Calculate the sensitivity level for a computation based on referenced devices.
    
    Returns:
        Tuple of (highest_sensitivity, list_of_source_device_ids)
    """
    source_devices = []
    sensitivities = []
    
    # Find device references from definition (DSL format)
    device_refs = extract_device_references_from_definition(definition)
    
    if device_refs:
        # Look up devices by ingestion_id
        devices = db.query(Device).filter(Device.ingestion_id.in_(device_refs)).all()
        
        for device in devices:
            source_devices.append(device.ingestion_id)
            if device.sensitivity:
                sensitivities.append(device.sensitivity)
    
    # If no specific devices found, check if the query accesses all data
    # (no device filter in WHERE clause)
    if not source_devices:
        where_clauses = definition.get("where", [])
        has_device_filter = False
        
        if isinstance(where_clauses, list):
            for clause in where_clauses:
                if isinstance(clause, dict):
                    col = str(clause.get("col", "")).lower()
                    if col in ["ingestion_id", "sensor_id", "device_id", "sensorid"]:
                        has_device_filter = True
                        break
        
        if not has_device_filter:
            # Query potentially accesses all devices - get highest sensitivity from all
            all_devices = db.query(Device).filter(Device.enabled == True).all()
            for device in all_devices:
                source_devices.append(device.ingestion_id)
                if device.sensitivity:
                    sensitivities.append(device.sensitivity)
    
    # Calculate highest sensitivity
    highest_sensitivity = get_highest_sensitivity(sensitivities)
    
    logger.debug("🔍 Computed sensitivity for definition: %s devices, sensitivity=%s", 
                len(source_devices), highest_sensitivity.value)
    
    return highest_sensitivity, source_devices
