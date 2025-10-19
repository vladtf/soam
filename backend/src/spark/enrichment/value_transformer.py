"""
Value transformation processor for applying user-defined data transformations.
"""
import json
import logging
import re
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from sqlalchemy.orm import Session, sessionmaker
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StringType, IntegerType, FloatType, BooleanType, TimestampType

from src.database.database import engine
from src.database.models import ValueTransformationRule
from src.utils.logging import get_logger
from .union_schema import UnionSchemaTransformer

logger = get_logger(__name__)

# Create session maker
SessionLocal = sessionmaker(bind=engine)


class ValueTransformationProcessor:
    """Applies user-defined value transformations to data during enrichment."""
    
    def __init__(self):
        """Initialize the value transformation processor."""
        self.transformation_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.cache_timestamp = None
        
    def _load_transformation_rules(self, ingestion_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Load enabled transformation rules from the database.
        
        Priority order:
        1. Rules specific to the ingestion_id
        2. Global rules (ingestion_id is NULL) as fallback
        """
        cache_key = ingestion_id or "global"
        current_time = datetime.now()
        
        # Cache rules for 5 minutes to avoid excessive DB queries
        if (self.cache_timestamp and 
            (current_time - self.cache_timestamp).total_seconds() < 300 and
            cache_key in self.transformation_cache):
            return self.transformation_cache[cache_key]
        
        try:
            db: Session = SessionLocal()
            try:
                query = db.query(ValueTransformationRule).filter(ValueTransformationRule.enabled == True)
                
                if ingestion_id:
                    query = query.filter(
                        (ValueTransformationRule.ingestion_id == ingestion_id) |
                        (ValueTransformationRule.ingestion_id.is_(None))
                    )
                else:
                    query = query.filter(ValueTransformationRule.ingestion_id.is_(None))
                
                rules = query.order_by(
                    ValueTransformationRule.order_priority.asc(),
                    ValueTransformationRule.id.asc()
                ).all()
                
                # Convert to dict format for processing
                rule_list = []
                for rule in rules:
                    try:
                        config = json.loads(rule.transformation_config) if isinstance(rule.transformation_config, str) else rule.transformation_config
                        rule_list.append({
                            "id": rule.id,
                            "field_name": rule.field_name,
                            "transformation_type": rule.transformation_type,
                            "config": config,
                            "order_priority": rule.order_priority,
                            "ingestion_id": rule.ingestion_id
                        })
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning("⚠️ Invalid transformation config for rule %d: %s", rule.id, e)
                        continue
                
                # Update cache
                self.transformation_cache[cache_key] = rule_list
                self.cache_timestamp = current_time
                
                logger.debug("🔄 Loaded %d value transformation rules for ingestion_id='%s'", 
                           len(rule_list), ingestion_id or "global")
                
                return rule_list
                
            finally:
                db.close()
                
        except Exception as e:
            logger.warning("⚠️ Failed to load value transformation rules from DB: %s", e)
            return []
    
    def apply_transformations(self, df: DataFrame, ingestion_id: Optional[str] = None) -> DataFrame:
        """Apply value transformations to the DataFrame.
        
        Args:
            df: Input DataFrame
            ingestion_id: Source identifier for loading specific transformation rules
            
        Returns:
            DataFrame with transformations applied
        """
        rules = self._load_transformation_rules(ingestion_id)
        if not rules:
            logger.debug("🔍 No value transformation rules found for ingestion_id='%s'", ingestion_id or "global")
            return df
        
        logger.info("🔧 Applying %d value transformation rules for ingestion_id='%s'", 
                   len(rules), ingestion_id or "global")
        
        result_df = df
        applied_rules = []
        fields_to_update_in_normalized: Set[str] = set()
        
        # Group rules by field for efficient processing
        rules_by_field: Dict[str, List[Dict[str, Any]]] = {}
        for rule in rules:
            field_name = rule["field_name"]
            if field_name not in rules_by_field:
                rules_by_field[field_name] = []
            rules_by_field[field_name].append(rule)
        
        # Apply transformations field by field
        available_columns = result_df.columns
        logger.debug("🔍 Available DataFrame columns: %s", available_columns)
        
        for field_name, field_rules in rules_by_field.items():
            logger.debug("🔍 Looking for field '%s' in DataFrame columns", field_name)
            
            # Check if field exists as top-level column
            if field_name in result_df.columns:
                logger.debug("✅ Found field '%s' - Processing with %d rules", field_name, len(field_rules))
                
                for rule in field_rules:
                    try:
                        result_df = self._apply_single_transformation(result_df, field_name, rule)
                        applied_rules.append(rule["id"])
                        logger.debug("✅ Applied transformation rule %d to field '%s'", rule["id"], field_name)
                    except Exception as e:
                        logger.warning("⚠️ Failed to apply transformation rule %d to field '%s': %s", 
                                     rule["id"], field_name, e)
            
            # Extract field from union schema (sensor_data/normalized_data) and then apply transformations
            else:
                try:
                    logger.debug("🔄 Extracting field '%s' from union schema", field_name)
                    # Extract the field from nested data using union schema transformer
                    result_df = UnionSchemaTransformer.extract_column_from_union(result_df, field_name, prefer_normalized=True)
                    
                    # Now check if the extraction was successful (field has non-null values)
                    if field_name in result_df.columns:
                        # Check if the extracted column has any non-null values
                        non_null_count = result_df.filter(F.col(field_name).isNotNull()).count()
                        if non_null_count > 0:
                            logger.debug("✅ Successfully extracted field '%s' with %d non-null values - Processing with %d rules", 
                                       field_name, non_null_count, len(field_rules))
                            
                            for rule in field_rules:
                                try:
                                    result_df = self._apply_single_transformation(result_df, field_name, rule)
                                    applied_rules.append(rule["id"])
                                    fields_to_update_in_normalized.add(field_name)
                                    logger.debug("✅ Applied transformation rule %d to extracted field '%s'", rule["id"], field_name)
                                except Exception as e:
                                    logger.warning("⚠️ Failed to apply transformation rule %d to extracted field '%s': %s", 
                                                 rule["id"], field_name, e)
                        else:
                            logger.warning("⚠️ Field '%s' extracted but contains only null values", field_name)
                    else:
                        logger.warning("❌ Failed to extract field '%s' from union schema", field_name)
                
                except Exception as e:
                    logger.warning("❌ Error extracting field '%s' from union schema: %s", field_name, e)
        
        # Update transformed fields back into normalized_data map
        if fields_to_update_in_normalized:
            result_df = self._update_normalized_data_map(result_df, fields_to_update_in_normalized)
        
        # Update rule usage statistics (non-blocking)
        if applied_rules:
            self._increment_rule_usage(applied_rules)
        
        logger.info("✅ Applied %d value transformation rules successfully", len(applied_rules))
        return result_df
    
    def _apply_single_transformation(self, df: DataFrame, field_name: str, rule: Dict[str, Any]) -> DataFrame:
        """Apply a single transformation rule to a field."""
        transformation_type = rule["transformation_type"]
        config = rule["config"]
        
        if transformation_type == "filter":
            return self._apply_filter_transformation(df, field_name, config)
        elif transformation_type == "aggregate":
            return self._apply_aggregate_transformation(df, field_name, config)
        elif transformation_type == "convert":
            return self._apply_convert_transformation(df, field_name, config)
        elif transformation_type == "validate":
            return self._apply_validate_transformation(df, field_name, config)
        else:
            logger.warning("⚠️ Unknown transformation type: %s", transformation_type)
            return df
    
    def _apply_filter_transformation(self, df: DataFrame, field_name: str, config: Dict[str, Any]) -> DataFrame:
        """Apply filter transformation to remove rows based on conditions."""
        operator = config.get("operator")
        value = config.get("value")
        case_sensitive = config.get("case_sensitive", False)
        
        field_col = F.col(field_name)
        
        if operator == ">":
            condition = field_col > value
        elif operator == ">=":
            condition = field_col >= value
        elif operator == "<":
            condition = field_col < value
        elif operator == "<=":
            condition = field_col <= value
        elif operator == "==":
            condition = field_col == value
        elif operator == "!=":
            condition = field_col != value
        elif operator == "contains":
            if case_sensitive:
                condition = field_col.contains(str(value))
            else:
                condition = F.lower(field_col).contains(str(value).lower())
        elif operator == "regex":
            condition = field_col.rlike(str(value))
        else:
            logger.warning("⚠️ Unknown filter operator: %s", operator)
            return df
        
        return df.filter(condition)
    
    def _apply_aggregate_transformation(self, df: DataFrame, field_name: str, config: Dict[str, Any]) -> DataFrame:
        """Apply aggregation transformation (window-based aggregation)."""
        function = config.get("function")
        window = config.get("window")
        group_by = config.get("group_by", [])
        
        # Note: For streaming aggregations, this would require watermarks and time windows
        # For batch processing, we can do simple aggregations
        logger.info("🔧 Aggregation transformations are best applied in streaming context")
        
        # For now, we'll add a flag to indicate this field should be aggregated
        return df.withColumn(f"{field_name}_agg_pending", F.lit(f"{function}_{window}"))
    
    def _apply_convert_transformation(self, df: DataFrame, field_name: str, config: Dict[str, Any]) -> DataFrame:
        """Apply conversion transformation (type conversion or mathematical operations)."""
        operation = config.get("operation", "type_conversion")  # Default to backward compatibility
        
        if operation == "mathematical":
            return self._apply_mathematical_operation(df, field_name, config)
        else:
            return self._apply_type_conversion(df, field_name, config)
    
    def _apply_type_conversion(self, df: DataFrame, field_name: str, config: Dict[str, Any]) -> DataFrame:
        """Apply type conversion transformation."""
        target_type = config.get("target_type")
        format_str = config.get("format")
        default_value = config.get("default_value")
        
        field_col = F.col(field_name)
        
        try:
            if target_type == "string":
                converted_col = field_col.cast(StringType())
            elif target_type == "int":
                converted_col = field_col.cast(IntegerType())
            elif target_type == "float":
                converted_col = field_col.cast(FloatType())
            elif target_type == "boolean":
                # Handle common boolean representations
                converted_col = F.when(
                    F.lower(field_col).isin(["true", "1", "yes", "on"]), True
                ).when(
                    F.lower(field_col).isin(["false", "0", "no", "off"]), False
                ).otherwise(None).cast(BooleanType())
            elif target_type == "datetime":
                if format_str:
                    converted_col = F.to_timestamp(field_col, format_str)
                else:
                    converted_col = F.to_timestamp(field_col)
            else:
                logger.warning("⚠️ Unknown target type: %s", target_type)
                return df
            
            # Apply default value if conversion fails
            if default_value is not None:
                converted_col = F.coalesce(converted_col, F.lit(default_value))
            
            return df.withColumn(field_name, converted_col)
            
        except Exception as e:
            logger.warning("⚠️ Type conversion failed for field %s: %s", field_name, e)
            return df
    
    def _apply_mathematical_operation(self, df: DataFrame, field_name: str, config: Dict[str, Any]) -> DataFrame:
        """Apply mathematical operations to field values."""
        math_operation = config.get("math_operation")
        operand = config.get("operand")
        operand_field = config.get("operand_field")
        
        field_col = F.col(field_name)
        
        try:
            # Determine operand source (constant value or another field)
            if operand_field:
                operand_col = F.col(operand_field)
            elif operand is not None:
                operand_col = F.lit(operand)
            else:
                logger.warning("⚠️ No operand specified for mathematical operation")
                return df
            
            # Apply mathematical operation
            if math_operation == "add":
                result_col = field_col + operand_col
            elif math_operation == "subtract":
                result_col = field_col - operand_col
            elif math_operation == "multiply":
                result_col = field_col * operand_col
            elif math_operation == "divide":
                # Handle division by zero
                result_col = F.when(operand_col != 0, field_col / operand_col).otherwise(None)
            elif math_operation == "modulo":
                result_col = field_col % operand_col
            elif math_operation == "power":
                result_col = F.pow(field_col, operand_col)
            else:
                logger.warning("⚠️ Unknown mathematical operation: %s", math_operation)
                return df
            
            return df.withColumn(field_name, result_col)
            
        except Exception as e:
            logger.warning("⚠️ Mathematical operation failed for field %s: %s", field_name, e)
            return df
    
    def _apply_validate_transformation(self, df: DataFrame, field_name: str, config: Dict[str, Any]) -> DataFrame:
        """Apply validation transformation."""
        validation_rules = config.get("validation_rules", [])
        on_fail = config.get("on_fail", "flag")
        
        field_col = F.col(field_name)
        validation_conditions = []
        
        for rule in validation_rules:
            rule_type = rule.get("rule")
            params = rule.get("params", {})
            
            if rule_type == "range":
                min_val = params.get("min")
                max_val = params.get("max")
                if min_val is not None and max_val is not None:
                    validation_conditions.append(
                        (field_col >= min_val) & (field_col <= max_val)
                    )
                elif min_val is not None:
                    validation_conditions.append(field_col >= min_val)
                elif max_val is not None:
                    validation_conditions.append(field_col <= max_val)
            elif rule_type == "regex":
                pattern = params.get("pattern")
                if pattern:
                    validation_conditions.append(field_col.rlike(pattern))
            elif rule_type == "enum":
                allowed_values = params.get("values", [])
                if allowed_values:
                    validation_conditions.append(field_col.isin(allowed_values))
            elif rule_type == "not_null":
                validation_conditions.append(field_col.isNotNull())
        
        if validation_conditions:
            # Combine all validation conditions with AND
            combined_condition = validation_conditions[0]
            for condition in validation_conditions[1:]:
                combined_condition = combined_condition & condition
            
            if on_fail == "drop":
                # Drop rows that fail validation
                return df.filter(combined_condition)
            elif on_fail == "flag":
                # Add a validation flag column
                return df.withColumn(f"{field_name}_valid", combined_condition)
            elif on_fail == "default":
                # Set field to null for invalid values
                return df.withColumn(
                    field_name,
                    F.when(combined_condition, field_col).otherwise(None)
                )
        
        return df

    def _increment_rule_usage(self, rule_ids: List[int]) -> None:
        """Increment usage count for applied rules (non-blocking)."""
        try:
            db: Session = SessionLocal()
            try:
                current_time = datetime.now()
                for rule_id in rule_ids:
                    rule = db.query(ValueTransformationRule).filter(ValueTransformationRule.id == rule_id).first()
                    if rule:
                        rule.applied_count = (rule.applied_count or 0) + 1
                        rule.last_applied_at = current_time
                
                db.commit()
                logger.debug("📊 Updated usage statistics for %d transformation rules", len(rule_ids))
            finally:
                db.close()
        except Exception as e:
            logger.debug("⚠️ Failed to update rule usage statistics: %s", e)
    
    def _update_normalized_data_map(self, df: DataFrame, field_names: Set[str]) -> DataFrame:
        """Update the normalized_data map with transformed field values.
        
        This method takes transformed fields that were extracted to top-level columns
        and updates their values in the normalized_data map, then removes the top-level columns.
        
        Args:
            df: DataFrame with transformed top-level columns
            field_names: Set of field names that were transformed
            
        Returns:
            DataFrame with updated normalized_data map
        """
        if not field_names or "normalized_data" not in df.columns:
            logger.warning("⚠️ Cannot update normalized_data: fields=%s, has_normalized_data=%s", 
                         field_names, "normalized_data" in df.columns)
            return df
        
        logger.debug("🔄 Updating normalized_data map with %d transformed fields: %s", 
                    len(field_names), field_names)
        
        result_df = df
        
        # Update normalized_data map with transformed values
        for field_name in field_names:
            if field_name in result_df.columns:
                # Update the value in normalized_data map
                result_df = result_df.withColumn(
                    "normalized_data",
                    F.when(
                        F.col(field_name).isNotNull(),
                        # Update the specific key in the map with the transformed value
                        F.map_concat(
                            F.col("normalized_data"),
                            F.create_map(F.lit(field_name), F.col(field_name))
                        )
                    ).otherwise(F.col("normalized_data"))
                )
                
                # Drop the temporary top-level column
                result_df = result_df.drop(field_name)
                logger.debug("✅ Updated '%s' in normalized_data map and removed top-level column", field_name)
        
        logger.info("✅ Updated %d fields in normalized_data map", len(field_names))
        return result_df
    
    def clear_cache(self) -> None:
        """Clear the transformation rules cache."""
        self.transformation_cache.clear()
        self.cache_timestamp = None
        logger.debug("🗑️ Cleared value transformation rules cache")