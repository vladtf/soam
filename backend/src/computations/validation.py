"""Validation utilities for computation data."""
import re
import json
import logging
from src.api.response_utils import bad_request_error

logger = logging.getLogger(__name__)


def validate_dataset(ds: str) -> str:
    """Validate and normalize dataset name."""
    ds = ds.lower()
    allowed_datasets = {"bronze", "silver", "gold", "enriched", "alerts", "sensors", "gold_temp_avg", "gold_alerts"}
    if ds not in allowed_datasets:
        raise bad_request_error(f"Invalid dataset. Use {', '.join(sorted(allowed_datasets))}")
    return ds


def validate_username(username: str) -> str:
    """Validate username format and security."""
    username = username.strip()
    if not (3 <= len(username) <= 32):
        raise bad_request_error("Username must be 3-32 characters long")
    if not re.match(r"^[A-Za-z0-9_.-]+$", username):
        raise bad_request_error("Username contains invalid characters")
    
    # Additional sanitization to prevent SQL injection or unsafe characters
    if re.search(r"[;'\"]|--|\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE)\b", username, re.IGNORECASE):
        raise bad_request_error("Username contains unsafe characters or SQL keywords")
    
    return username


def validate_computation_definition(definition) -> dict:
    """Validate computation definition structure.
    
    Args:
        definition: Either a dict or JSON string containing the computation definition
        
    Returns:
        dict: Validation result with 'valid' and 'message' keys
    """
    try:
        # Handle JSON string input
        if isinstance(definition, str):
            import json
            try:
                definition = json.loads(definition)
            except json.JSONDecodeError as e:
                return {"valid": False, "message": f"Invalid JSON string: {str(e)}"}
        
        if not isinstance(definition, dict):
            return {"valid": False, "message": "Definition must be a JSON object or valid JSON string"}
        
        # Basic structure validation
        allowed_keys = {"select", "where", "orderBy", "limit", "groupBy"}
        invalid_keys = set(definition.keys()) - allowed_keys
        if invalid_keys:
            return {"valid": False, "message": f"Invalid definition keys: {', '.join(invalid_keys)}. Allowed: {', '.join(allowed_keys)}"}
        
        # Validate where conditions structure
        if "where" in definition:
            if not isinstance(definition["where"], list):
                return {"valid": False, "message": "'where' must be a list of conditions"}
            
            for i, cond in enumerate(definition["where"]):
                if not isinstance(cond, dict):
                    return {"valid": False, "message": f"where[{i}] must be an object"}
                
                # Check required keys based on operation type
                if "col" not in cond or "op" not in cond:
                    return {"valid": False, "message": f"where[{i}] must contain 'col' and 'op'"}
                
                # For null check operations, value is not required
                op = cond.get("op", "").upper()
                if op in ["IS NULL", "IS NOT NULL"]:
                    # These operations don't require a value
                    pass
                elif "value" not in cond:
                    return {"valid": False, "message": f"where[{i}] must contain 'value' for operation '{op}'"}
        
        # Validate orderBy structure
        if "orderBy" in definition:
            if not isinstance(definition["orderBy"], list):
                return {"valid": False, "message": "'orderBy' must be a list"}
            
            for i, order in enumerate(definition["orderBy"]):
                if not isinstance(order, dict):
                    return {"valid": False, "message": f"orderBy[{i}] must be an object"}
                if "col" not in order:
                    return {"valid": False, "message": f"orderBy[{i}] must contain 'col'"}
                if "dir" in order and order["dir"].lower() not in ["asc", "desc"]:
                    return {"valid": False, "message": f"orderBy[{i}].dir must be 'asc' or 'desc'"}
        
        # Validate limit
        if "limit" in definition:
            try:
                limit = int(definition["limit"])
                if limit <= 0 or limit > 10000:
                    return {"valid": False, "message": "limit must be between 1 and 10000"}
            except (ValueError, TypeError):
                return {"valid": False, "message": "limit must be a valid integer"}
        
        # Validate groupBy
        if "groupBy" in definition:
            if not isinstance(definition["groupBy"], list):
                return {"valid": False, "message": "'groupBy' must be a list of column names"}
            if not all(isinstance(col, str) for col in definition["groupBy"]):
                return {"valid": False, "message": "All groupBy columns must be strings"}
        
        return {"valid": True, "message": "Definition is valid"}
        
    except Exception as e:
        logger.error("Error validating computation definition: %s", e)
        return {"valid": False, "message": f"Validation error: {str(e)}"}
