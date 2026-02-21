"""
Value transformation routes for managing data value transformation rules.
"""
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

# API models and response utilities
from src.api.models import ApiResponse, ApiListResponse, ValueTransformationRuleCreate, ValueTransformationRuleUpdate, ValueTransformationRuleResponse
from src.api.response_utils import success_response, list_response, not_found_error, bad_request_error, internal_server_error

# Dependencies
from src.database.database import get_db
from src.database.models import ValueTransformationRule

# Utilities
from src.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["value_transformation"])


def _rule_to_response(rule: ValueTransformationRule) -> ValueTransformationRuleResponse:
    """Convert a ValueTransformationRule ORM model to a ValueTransformationRuleResponse."""
    return ValueTransformationRuleResponse(
        id=rule.id,
        ingestion_id=rule.ingestion_id,
        field_name=rule.field_name,
        transformation_type=rule.transformation_type,
        transformation_config=rule.transformation_config,
        order_priority=rule.order_priority,
        enabled=rule.enabled,
        applied_count=getattr(rule, "applied_count", 0),
        last_applied_at=rule.last_applied_at.isoformat() if getattr(rule, "last_applied_at", None) else None,
        created_by=rule.created_by,
        updated_by=rule.updated_by,
        created_at=rule.created_at.isoformat() if rule.created_at else None,
        updated_at=rule.updated_at.isoformat() if rule.updated_at else None,
    )


def _validate_transformation_config(transformation_type: str, config: dict) -> None:
    """Validate transformation config fields based on transformation type.
    
    Raises bad_request_error if validation fails.
    """
    valid_types = ["filter", "aggregate", "convert", "validate"]
    if transformation_type not in valid_types:
        raise bad_request_error(f"Invalid transformation type. Must be one of: {', '.join(valid_types)}")
    
    # Determine required fields based on type
    required_fields_map = {
        "filter": ["operator", "value"],
        "aggregate": ["function", "window"],
        "convert": ["operation"],
        "validate": ["validation_rules"],
    }
    required_fields = required_fields_map.get(transformation_type, [])
    
    for field in required_fields:
        if field not in config:
            raise bad_request_error(f"Missing required config field '{field}' for transformation type '{transformation_type}'")
    
    # Special validation for convert type based on operation
    if transformation_type == "convert":
        operation = config.get("operation")
        if operation == "type_conversion":
            if "target_type" not in config:
                raise bad_request_error("Missing required config field 'target_type' for convert operation 'type_conversion'")
        elif operation == "mathematical":
            if "math_operation" not in config:
                raise bad_request_error("Missing required config field 'math_operation' for convert operation 'mathematical'")
            if "operand" not in config and "operand_field" not in config:
                raise bad_request_error("Missing required config field 'operand' or 'operand_field' for convert operation 'mathematical'")
        else:
            raise bad_request_error(f"Invalid convert operation '{operation}'. Must be 'type_conversion' or 'mathematical'")


@router.get("/value-transformations", response_model=ApiListResponse[ValueTransformationRuleResponse])
def list_value_transformation_rules(db: Session = Depends(get_db)):
    """List all value transformation rules."""
    try:
        rules = db.query(ValueTransformationRule).order_by(
            ValueTransformationRule.ingestion_id.asc().nullsfirst(),
            ValueTransformationRule.field_name.asc(),
            ValueTransformationRule.order_priority.asc()
        ).all()
        
        rule_responses = []
        for rule in rules:
            # Parse transformation_config from JSON string to dict
            try:
                parsed_config = json.loads(rule.transformation_config)
            except (json.JSONDecodeError, TypeError):
                logger.warning("⚠️ Invalid JSON in transformation_config for rule %s", rule.id)
                parsed_config = {}
            
            rule_responses.append(_rule_to_response(rule))
        
        return list_response(
            data=rule_responses,
            total=len(rule_responses),
            message="Value transformation rules retrieved successfully"
        )
    except Exception as e:
        logger.error("❌ Error listing value transformation rules: %s", e)
        raise internal_server_error("Failed to retrieve value transformation rules", str(e))


@router.post("/value-transformations", response_model=ApiResponse[ValueTransformationRuleResponse])
def create_value_transformation_rule(payload: ValueTransformationRuleCreate, db: Session = Depends(get_db)):
    """Create a new value transformation rule."""
    try:
        # Validate transformation type and config
        _validate_transformation_config(payload.transformation_type, payload.transformation_config)
        
        # Convert transformation_config dict to JSON string for database storage
        import json
        transformation_config_str = json.dumps(payload.transformation_config)
        
        rule = ValueTransformationRule(
            ingestion_id=payload.ingestion_id,
            field_name=payload.field_name.strip(),
            transformation_type=payload.transformation_type,
            transformation_config=transformation_config_str,
            order_priority=payload.order_priority,
            enabled=payload.enabled,
            created_by=payload.created_by.strip(),
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        
        logger.info("✅ Value transformation rule created by '%s': %s -> %s (%s)", 
                   payload.created_by, rule.field_name, rule.transformation_type, rule.ingestion_id or "global")
        
        return success_response(_rule_to_response(rule), "Value transformation rule created successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Error creating value transformation rule: %s", e)
        db.rollback()
        raise internal_server_error("Failed to create value transformation rule", str(e))


@router.patch("/value-transformations/{rule_id}", response_model=ApiResponse[ValueTransformationRuleResponse])
def update_value_transformation_rule(rule_id: int, payload: ValueTransformationRuleUpdate, db: Session = Depends(get_db)):
    """Update an existing value transformation rule."""
    try:
        rule = db.query(ValueTransformationRule).filter(ValueTransformationRule.id == rule_id).first()
        if not rule:
            raise not_found_error("Value transformation rule not found")

        changes = []
        if payload.field_name is not None and payload.field_name.strip() != rule.field_name:
            changes.append(f"field_name: '{rule.field_name}' -> '{payload.field_name.strip()}'")
            rule.field_name = payload.field_name.strip()
            
        if payload.transformation_type is not None and payload.transformation_type != rule.transformation_type:
            changes.append(f"transformation_type: '{rule.transformation_type}' -> '{payload.transformation_type}'")
            rule.transformation_type = payload.transformation_type
            
        if payload.transformation_config is not None:
            # Validate the new config if provided
            transformation_type = payload.transformation_type if payload.transformation_type is not None else rule.transformation_type
            _validate_transformation_config(transformation_type, payload.transformation_config)
            
            changes.append("transformation_config updated")
            rule.transformation_config = json.dumps(payload.transformation_config)
            
        if payload.order_priority is not None and payload.order_priority != rule.order_priority:
            changes.append(f"order_priority: {rule.order_priority} -> {payload.order_priority}")
            rule.order_priority = payload.order_priority
            
        if payload.enabled is not None and payload.enabled != rule.enabled:
            changes.append(f"enabled: {rule.enabled} -> {payload.enabled}")
            rule.enabled = payload.enabled

        rule.updated_by = payload.updated_by.strip()
        
        db.commit()
        db.refresh(rule)
        
        if changes:
            logger.info("✅ Value transformation rule %d updated by '%s': %s", 
                       rule_id, payload.updated_by, "; ".join(changes))
        
        return success_response(_rule_to_response(rule), "Value transformation rule updated successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Error updating value transformation rule: %s", e)
        db.rollback()
        raise internal_server_error("Failed to update value transformation rule", str(e))


@router.delete("/value-transformations/{rule_id}", response_model=ApiResponse)
def delete_value_transformation_rule(rule_id: int, db: Session = Depends(get_db)):
    """Delete a value transformation rule."""
    try:
        rule = db.query(ValueTransformationRule).filter(ValueTransformationRule.id == rule_id).first()
        if not rule:
            raise not_found_error("Value transformation rule not found")

        rule_name = f"{rule.field_name} ({rule.transformation_type})"
        db.delete(rule)
        db.commit()
        
        logger.info("✅ Value transformation rule deleted: %s", rule_name)
        return success_response(None, "Value transformation rule deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Error deleting value transformation rule: %s", e)
        db.rollback()
        raise internal_server_error("Failed to delete value transformation rule", str(e))


@router.patch("/value-transformations/{rule_id}/toggle", response_model=ApiResponse[ValueTransformationRuleResponse])
def toggle_value_transformation_rule(rule_id: int, db: Session = Depends(get_db)):
    """Toggle the enabled/disabled state of a value transformation rule."""
    try:
        rule = db.query(ValueTransformationRule).filter(ValueTransformationRule.id == rule_id).first()
        if not rule:
            raise not_found_error("Value transformation rule not found")

        # Toggle the enabled state
        old_state = rule.enabled
        rule.enabled = not rule.enabled
        
        db.commit()
        db.refresh(rule)
        
        logger.info("✅ Value transformation rule %d toggled: %s -> %s (%s)", 
                   rule_id, old_state, rule.enabled, rule.field_name)
        
        return success_response(_rule_to_response(rule), f"Rule {'enabled' if rule.enabled else 'disabled'} successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Error toggling value transformation rule: %s", e)
        db.rollback()
        raise internal_server_error("Failed to toggle value transformation rule", str(e))


@router.get("/value-transformations/types", response_model=ApiResponse)
def get_transformation_types():
    """Get available transformation types and their configuration schema."""
    try:
        transformation_types = {
            "filter": {
                "description": "Filter data based on conditions",
                "config_schema": {
                    "operator": {"type": "string", "enum": [">", ">=", "<", "<=", "==", "!=", "contains", "regex"], "required": True},
                    "value": {"type": "any", "description": "Value to compare against", "required": True},
                    "case_sensitive": {"type": "boolean", "default": False, "description": "For string operations"}
                },
                "examples": [
                    {
                        "name": "Temperature Above Threshold",
                        "description": "Keep only temperature readings above 25 degrees",
                        "config": {"operator": ">", "value": 25}
                    },
                    {
                        "name": "Error Log Filter",
                        "description": "Keep only messages containing 'error' (case insensitive)",
                        "config": {"operator": "contains", "value": "error", "case_sensitive": False}
                    },
                    {
                        "name": "Sensor ID Pattern",
                        "description": "Keep only sensor IDs matching pattern (e.g., AB123, XY456)",
                        "config": {"operator": "regex", "value": "^[A-Z]{2,3}[0-9]+$"}
                    }
                ]
            },
            "aggregate": {
                "description": "Aggregate values over time windows",
                "config_schema": {
                    "function": {"type": "string", "enum": ["avg", "sum", "min", "max", "count", "stddev"], "required": True},
                    "window": {"type": "string", "description": "Time window (e.g., '5 minutes', '1 hour')", "required": True},
                    "group_by": {"type": "array", "items": {"type": "string"}, "description": "Fields to group by"}
                },
                "examples": [
                    {
                        "name": "Average Temperature",
                        "description": "Calculate average temperature over 5-minute windows",
                        "config": {"function": "avg", "window": "5 minutes"}
                    },
                    {
                        "name": "Sensor Sum by Group",
                        "description": "Sum values hourly, grouped by sensor ID",
                        "config": {"function": "sum", "window": "1 hour", "group_by": ["sensorId"]}
                    },
                    {
                        "name": "Event Count",
                        "description": "Count events in 15-minute windows",
                        "config": {"function": "count", "window": "15 minutes"}
                    }
                ]
            },
            "convert": {
                "description": "Convert data types, formats, or perform mathematical operations",
                "config_schema": {
                    "operation": {"type": "string", "enum": ["type_conversion", "mathematical"], "required": True},
                    "target_type": {"type": "string", "enum": ["string", "int", "float", "boolean", "datetime"], "description": "For type_conversion operations"},
                    "format": {"type": "string", "description": "Format string for conversions (e.g., datetime format)"},
                    "default_value": {"type": "any", "description": "Default value if conversion fails"},
                    "math_operation": {"type": "string", "enum": ["add", "subtract", "multiply", "divide", "modulo", "power"], "description": "For mathematical operations"},
                    "operand": {"type": "number", "description": "Number to use in mathematical operation"},
                    "operand_field": {"type": "string", "description": "Field name to use as operand (alternative to operand)"}
                },
                "examples": [
                    {
                        "name": "String to Float",
                        "description": "Convert temperature strings to float with default 0.0",
                        "config": {"operation": "type_conversion", "target_type": "float", "default_value": 0.0}
                    },
                    {
                        "name": "Parse Timestamp",
                        "description": "Convert timestamp strings to datetime objects",
                        "config": {"operation": "type_conversion", "target_type": "datetime", "format": "%Y-%m-%d %H:%M:%S"}
                    },
                    {
                        "name": "Boolean Conversion",
                        "description": "Convert values to boolean (0/1, true/false, yes/no)",
                        "config": {"operation": "type_conversion", "target_type": "boolean"}
                    },
                    {
                        "name": "Add Offset",
                        "description": "Add a constant value to temperature readings (e.g., calibration offset)",
                        "config": {"operation": "mathematical", "math_operation": "add", "operand": 2.5}
                    },
                    {
                        "name": "Subtract Baseline",
                        "description": "Subtract baseline value from sensor readings",
                        "config": {"operation": "mathematical", "math_operation": "subtract", "operand": 10.0}
                    },
                    {
                        "name": "Convert to Fahrenheit",
                        "description": "Convert Celsius to Fahrenheit: multiply by 1.8 then add 32",
                        "config": {"operation": "mathematical", "math_operation": "multiply", "operand": 1.8}
                    },
                    {
                        "name": "Scale Down",
                        "description": "Divide values by scaling factor (e.g., convert millivolts to volts)",
                        "config": {"operation": "mathematical", "math_operation": "divide", "operand": 1000}
                    },
                    {
                        "name": "Calculate Difference",
                        "description": "Subtract one field from another (use operand_field for field-to-field operations)",
                        "config": {"operation": "mathematical", "math_operation": "subtract", "operand_field": "baseline_temperature"}
                    }
                ]
            },
            "validate": {
                "description": "Validate data against rules",
                "config_schema": {
                    "validation_rules": {
                        "type": "array", 
                        "items": {
                            "type": "object",
                            "properties": {
                                "rule": {"type": "string", "enum": ["range", "regex", "enum", "not_null"]},
                                "params": {"type": "object"}
                            }
                        },
                        "required": True
                    },
                    "on_fail": {"type": "string", "enum": ["drop", "flag", "default"], "default": "flag"}
                },
                "examples": [
                    {
                        "name": "Range and Null Validation",
                        "description": "Validate data is between 0-100 and not null, flag invalid entries",
                        "config": {
                            "validation_rules": [
                                {"rule": "range", "params": {"min": 0, "max": 100}},
                                {"rule": "not_null", "params": {}}
                            ],
                            "on_fail": "flag"
                        }
                    },
                    {
                        "name": "Enum Validation",
                        "description": "Validate sensor status is one of allowed values",
                        "config": {
                            "validation_rules": [
                                {"rule": "enum", "params": {"values": ["online", "offline", "maintenance"]}}
                            ],
                            "on_fail": "drop"
                        }
                    },
                    {
                        "name": "Pattern Validation",
                        "description": "Validate device ID follows specific pattern",
                        "config": {
                            "validation_rules": [
                                {"rule": "regex", "params": {"pattern": "^DEV-[0-9]{4}$"}}
                            ],
                            "on_fail": "flag"
                        }
                    }
                ]
            }
        }
        
        return success_response(transformation_types, "Transformation types retrieved successfully")
    except Exception as e:
        logger.error("❌ Error getting transformation types: %s", e)
        raise internal_server_error("Failed to retrieve transformation types", str(e))