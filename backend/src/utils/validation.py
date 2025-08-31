"""
Common validation utilities for API requests and data processing.
"""
from typing import Any, Dict, List, Optional, Union
from fastapi import HTTPException

from src.utils.logging import get_logger

logger = get_logger(__name__)


def validate_required_fields(data: Dict[str, Any], required_fields: List[str], operation: str = "operation") -> None:
    """
    Validate that required fields are present in data.
    
    Args:
        data: Data dictionary to validate
        required_fields: List of required field names
        operation: Operation name for error messages
        
    Raises:
        HTTPException: If validation fails
    """
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid data format for {operation}: expected object, got {type(data).__name__}"
        )
    
    missing_fields = []
    empty_fields = []
    
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
        elif data[field] is None or (isinstance(data[field], str) and data[field].strip() == ""):
            empty_fields.append(field)
    
    error_parts = []
    if missing_fields:
        error_parts.append(f"Missing required fields: {', '.join(missing_fields)}")
    if empty_fields:
        error_parts.append(f"Empty required fields: {', '.join(empty_fields)}")
    
    if error_parts:
        error_message = f"Validation failed for {operation}: {'; '.join(error_parts)}"
        logger.warning(f"⚠️ {error_message}")
        raise HTTPException(status_code=400, detail=error_message)


def validate_field_types(data: Dict[str, Any], field_types: Dict[str, type], operation: str = "operation") -> None:
    """
    Validate field types in data.
    
    Args:
        data: Data dictionary to validate
        field_types: Dictionary mapping field names to expected types
        operation: Operation name for error messages
        
    Raises:
        HTTPException: If validation fails
    """
    type_errors = []
    
    for field, expected_type in field_types.items():
        if field in data and data[field] is not None:
            if not isinstance(data[field], expected_type):
                type_errors.append(
                    f"{field} should be {expected_type.__name__}, got {type(data[field]).__name__}"
                )
    
    if type_errors:
        error_message = f"Type validation failed for {operation}: {'; '.join(type_errors)}"
        logger.warning(f"⚠️ {error_message}")
        raise HTTPException(status_code=400, detail=error_message)


def validate_string_length(
    data: Dict[str, Any], 
    field_limits: Dict[str, Dict[str, int]], 
    operation: str = "operation"
) -> None:
    """
    Validate string field lengths.
    
    Args:
        data: Data dictionary to validate
        field_limits: Dictionary mapping field names to {'min': min_len, 'max': max_len}
        operation: Operation name for error messages
        
    Raises:
        HTTPException: If validation fails
    """
    length_errors = []
    
    for field, limits in field_limits.items():
        if field in data and isinstance(data[field], str):
            field_len = len(data[field].strip())
            min_len = limits.get('min', 0)
            max_len = limits.get('max', float('inf'))
            
            if field_len < min_len:
                length_errors.append(f"{field} must be at least {min_len} characters long")
            elif field_len > max_len:
                length_errors.append(f"{field} must be no more than {max_len} characters long")
    
    if length_errors:
        error_message = f"Length validation failed for {operation}: {'; '.join(length_errors)}"
        logger.warning(f"⚠️ {error_message}")
        raise HTTPException(status_code=400, detail=error_message)


def validate_numeric_range(
    data: Dict[str, Any], 
    field_ranges: Dict[str, Dict[str, Union[int, float]]], 
    operation: str = "operation"
) -> None:
    """
    Validate numeric field ranges.
    
    Args:
        data: Data dictionary to validate
        field_ranges: Dictionary mapping field names to {'min': min_val, 'max': max_val}
        operation: Operation name for error messages
        
    Raises:
        HTTPException: If validation fails
    """
    range_errors = []
    
    for field, ranges in field_ranges.items():
        if field in data and isinstance(data[field], (int, float)):
            field_val = data[field]
            min_val = ranges.get('min', float('-inf'))
            max_val = ranges.get('max', float('inf'))
            
            if field_val < min_val:
                range_errors.append(f"{field} must be at least {min_val}")
            elif field_val > max_val:
                range_errors.append(f"{field} must be no more than {max_val}")
    
    if range_errors:
        error_message = f"Range validation failed for {operation}: {'; '.join(range_errors)}"
        logger.warning(f"⚠️ {error_message}")
        raise HTTPException(status_code=400, detail=error_message)


def validate_enum_values(
    data: Dict[str, Any], 
    field_enums: Dict[str, List[Any]], 
    operation: str = "operation"
) -> None:
    """
    Validate that field values are in allowed enums.
    
    Args:
        data: Data dictionary to validate
        field_enums: Dictionary mapping field names to list of allowed values
        operation: Operation name for error messages
        
    Raises:
        HTTPException: If validation fails
    """
    enum_errors = []
    
    for field, allowed_values in field_enums.items():
        if field in data and data[field] is not None:
            if data[field] not in allowed_values:
                enum_errors.append(
                    f"{field} must be one of: {', '.join(map(str, allowed_values))}, got '{data[field]}'"
                )
    
    if enum_errors:
        error_message = f"Enum validation failed for {operation}: {'; '.join(enum_errors)}"
        logger.warning(f"⚠️ {error_message}")
        raise HTTPException(status_code=400, detail=error_message)


def sanitize_string_fields(data: Dict[str, Any], string_fields: List[str]) -> Dict[str, Any]:
    """
    Sanitize string fields by trimming whitespace.
    
    Args:
        data: Data dictionary to sanitize
        string_fields: List of string field names to sanitize
        
    Returns:
        Sanitized data dictionary
    """
    sanitized = data.copy()
    
    for field in string_fields:
        if field in sanitized and isinstance(sanitized[field], str):
            sanitized[field] = sanitized[field].strip()
    
    return sanitized


class ValidationChain:
    """
    Fluent validation chain for complex validation scenarios.
    
    Usage:
        ValidationChain(data, "create user") \
            .require_fields(["name", "email"]) \
            .validate_types({"age": int, "email": str}) \
            .validate_string_lengths({"name": {"min": 2, "max": 50}}) \
            .sanitize(["name", "email"]) \
            .execute()
    """
    
    def __init__(self, data: Dict[str, Any], operation: str = "operation"):
        self.data = data
        self.operation = operation
        self._sanitized = False
    
    def require_fields(self, fields: List[str]) -> 'ValidationChain':
        """Add required fields validation."""
        validate_required_fields(self.data, fields, self.operation)
        return self
    
    def validate_types(self, field_types: Dict[str, type]) -> 'ValidationChain':
        """Add type validation."""
        validate_field_types(self.data, field_types, self.operation)
        return self
    
    def validate_string_lengths(self, field_limits: Dict[str, Dict[str, int]]) -> 'ValidationChain':
        """Add string length validation."""
        validate_string_length(self.data, field_limits, self.operation)
        return self
    
    def validate_ranges(self, field_ranges: Dict[str, Dict[str, Union[int, float]]]) -> 'ValidationChain':
        """Add numeric range validation."""
        validate_numeric_range(self.data, field_ranges, self.operation)
        return self
    
    def validate_enums(self, field_enums: Dict[str, List[Any]]) -> 'ValidationChain':
        """Add enum validation."""
        validate_enum_values(self.data, field_enums, self.operation)
        return self
    
    def sanitize(self, string_fields: List[str]) -> 'ValidationChain':
        """Sanitize string fields."""
        self.data = sanitize_string_fields(self.data, string_fields)
        self._sanitized = True
        return self
    
    def execute(self) -> Dict[str, Any]:
        """Execute the validation chain and return the data."""
        logger.info(f"✅ Validation completed successfully for {self.operation}")
        return self.data
