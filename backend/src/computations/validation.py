"""Validation utilities for computation data."""
import re
import logging
from src.api.response_utils import bad_request_error

logger = logging.getLogger(__name__)


def validate_dataset(ds: str) -> str:
    """Validate and normalize dataset name."""
    ds = ds.lower()
    allowed_datasets = {"bronze", "silver", "gold", "enriched", "alerts", "sensors", "gold_temp_avg", "gold_alerts"}
    if ds not in allowed_datasets:
        bad_request_error(f"Invalid dataset. Use {', '.join(sorted(allowed_datasets))}")
    return ds


def validate_username(username: str) -> str:
    """Validate username format and security."""
    username = username.strip()
    if not (3 <= len(username) <= 32):
        bad_request_error("Username must be 3-32 characters long")
    if not re.match(r"^[A-Za-z0-9_.-]+$", username):
        bad_request_error("Username contains invalid characters")
    
    # Additional sanitization to prevent SQL injection or unsafe characters
    if re.search(r"[;'\"]|--|\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE)\b", username, re.IGNORECASE):
        bad_request_error("Username contains unsafe characters or SQL keywords")
    
    return username


def validate_computation_definition(definition: dict) -> None:
    """Validate computation definition structure."""
    if not isinstance(definition, dict):
        bad_request_error("Definition must be a JSON object")
    
    # Basic structure validation
    allowed_keys = {"select", "where", "orderBy", "limit", "groupBy"}
    invalid_keys = set(definition.keys()) - allowed_keys
    if invalid_keys:
        bad_request_error(f"Invalid definition keys: {', '.join(invalid_keys)}. Allowed: {', '.join(allowed_keys)}")
    
    # Validate where conditions structure
    if "where" in definition:
        if not isinstance(definition["where"], list):
            bad_request_error("'where' must be a list of conditions")
        
        for i, cond in enumerate(definition["where"]):
            if not isinstance(cond, dict):
                bad_request_error(f"where[{i}] must be an object")
            required_keys = {"col", "op", "value"}
            if not all(key in cond for key in required_keys):
                bad_request_error(f"where[{i}] must contain: {', '.join(required_keys)}")
    
    # Validate orderBy structure
    if "orderBy" in definition:
        if not isinstance(definition["orderBy"], list):
            bad_request_error("'orderBy' must be a list")
        
        for i, order in enumerate(definition["orderBy"]):
            if not isinstance(order, dict):
                bad_request_error(f"orderBy[{i}] must be an object")
            if "col" not in order:
                bad_request_error(f"orderBy[{i}] must contain 'col'")
            if "dir" in order and order["dir"].lower() not in ["asc", "desc"]:
                bad_request_error(f"orderBy[{i}].dir must be 'asc' or 'desc'")
    
    # Validate limit
    if "limit" in definition:
        try:
            limit = int(definition["limit"])
            if limit <= 0 or limit > 10000:
                bad_request_error("limit must be between 1 and 10000")
        except (ValueError, TypeError):
            bad_request_error("limit must be a valid integer")
    
    # Validate groupBy
    if "groupBy" in definition:
        if not isinstance(definition["groupBy"], list):
            bad_request_error("'groupBy' must be a list of column names")
        if not all(isinstance(col, str) for col in definition["groupBy"]):
            bad_request_error("All groupBy columns must be strings")
