"""
Utilities for handling union schema transformations.

This module provides functions to convert between legacy sensor data formats
and the new union schema approach that stores raw data as JSON strings and
normalized data as typed values.
"""
import logging
from typing import Dict, Any, Optional, List
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, TimestampType, MapType, DoubleType
import json

logger = logging.getLogger(__name__)


class UnionSchemaTransformer:
    """Handles transformations between legacy and union schema formats."""

    @staticmethod
    def legacy_to_union(df: DataFrame, ingestion_id_col: str = "ingestion_id") -> DataFrame:
        """Convert legacy sensor DataFrame to union schema format.
        
        Args:
            df: Legacy DataFrame with direct columns (sensorId, temperature, etc.)
            ingestion_id_col: Name of the ingestion_id column
            
        Returns:
            DataFrame with union schema structure
        """
        # Ensure ingestion_id exists
        if ingestion_id_col not in df.columns:
            logger.warning("ingestion_id column not found, using 'unknown'")
            df = df.withColumn(ingestion_id_col, F.lit("unknown"))

        # Log the columns being processed
        logger.info(f"Legacy to union transformation: processing {len(df.columns)} columns: {df.columns}")

        # Extract timestamp and convert to proper timestamp type
        timestamp_col = F.coalesce(
            F.to_timestamp(F.col("timestamp")),
            F.to_timestamp(F.col("timestamp"), "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"),
            F.to_timestamp(F.col("timestamp"), "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"),
            F.to_timestamp(F.col("timestamp"), "yyyy-MM-dd'T'HH:mm:ssXXX"),
            F.to_timestamp(F.col("timestamp"), "yyyy-MM-dd'T'HH:mm:ss"),
            F.to_timestamp(F.regexp_replace(F.col("timestamp"), 'T', ' '), "yyyy-MM-dd HH:mm:ss.SSSSSS"),
            F.to_timestamp(F.regexp_replace(F.col("timestamp"), 'T', ' '), "yyyy-MM-dd HH:mm:ss.SSS"),
            F.to_timestamp(F.regexp_replace(F.col("timestamp"), 'T', ' '), "yyyy-MM-dd HH:mm:ss"),
            F.current_timestamp()  # fallback
        )

        # Create sensor_data map (all original columns as strings)
        sensor_data_cols = []
        for col_name in df.columns:
            if col_name not in [ingestion_id_col, "timestamp"]:
                sensor_data_cols.append(F.lit(col_name))
                sensor_data_cols.append(F.col(col_name).cast("string"))

        # Log debug info about sensor data creation
        sensor_cols_for_map = [col for col in df.columns if col not in [ingestion_id_col, "timestamp"]]
        logger.info(f"Legacy to union: creating sensor_data map from columns: {sensor_cols_for_map}")

        sensor_data_map = F.create_map(*sensor_data_cols) if sensor_data_cols else F.lit(None).cast(MapType(StringType(), StringType()))

        # Create normalized_data map (numeric columns only)
        normalized_data_cols = []
        numeric_columns = []
        for col_name in df.columns:
            if col_name not in [ingestion_id_col, "timestamp"]:
                # Try to cast to double, use null if not numeric
                numeric_value = F.when(
                    F.col(col_name).rlike(r"^-?\d+\.?\d*$"), 
                    F.col(col_name).cast("double")
                ).otherwise(F.lit(None).cast("double"))
                
                # Only add to map if the column could contain numeric data
                if col_name in ["temperature", "humidity", "pressure", "voltage", "current"] or col_name.endswith("_value"):
                    normalized_data_cols.append(F.lit(col_name))
                    normalized_data_cols.append(numeric_value)
                    numeric_columns.append(col_name)
                    
                    # Special logging for temperature field
                    if col_name == "temperature":
                        logger.info("Temperature field found in legacy-to-union transformation: column='%s'", col_name)

        logger.info(f"Legacy to union: created normalized_data for columns: {numeric_columns}")
        normalized_data_map = F.create_map(*normalized_data_cols) if normalized_data_cols else F.lit(None).cast(MapType(StringType(), DoubleType()))

        # Build union schema DataFrame
        return df.select(
            F.col(ingestion_id_col).alias("ingestion_id"),
            timestamp_col.alias("timestamp"),
            sensor_data_map.alias("sensor_data"),
            normalized_data_map.alias("normalized_data")
        )

    @staticmethod
    def union_to_legacy(df: DataFrame, extract_columns: Optional[List[str]] = None) -> DataFrame:
        """Convert union schema DataFrame back to legacy format.
        
        Args:
            df: Union schema DataFrame
            extract_columns: Specific columns to extract, if None extracts common ones
            
        Returns:
            DataFrame with legacy schema structure
        """
        if extract_columns is None:
            extract_columns = ["sensorId", "temperature", "humidity", "pressure"]

        # Start with base columns
        result_df = df.select("ingestion_id", "timestamp")

        # Extract specific columns from sensor_data map
        for col_name in extract_columns:
            result_df = result_df.withColumn(
                col_name,
                df.sensor_data.getItem(col_name)
            )

        # Extract numeric values from normalized_data map (preferred over string values)
        for col_name in extract_columns:
            if col_name in ["temperature", "humidity", "pressure", "voltage", "current"]:
                result_df = result_df.withColumn(
                    col_name,
                    F.coalesce(
                        df.normalized_data.getItem(col_name),
                        F.col(col_name).cast("double")
                    )
                )

        return result_df

    @staticmethod
    def apply_normalization_to_union(df: DataFrame, normalization_rules: Dict[str, str]) -> DataFrame:
        """Apply normalization rules to union schema DataFrame.
        
        Args:
            df: Union schema DataFrame
            normalization_rules: Dict mapping raw keys to canonical keys
            
        Returns:
            DataFrame with normalized keys in both sensor_data and normalized_data maps
        """
        # Group normalization rules by canonical key to avoid duplicates
        canonical_to_raw_keys = {}
        for raw_key, canonical_key in normalization_rules.items():
            if canonical_key not in canonical_to_raw_keys:
                canonical_to_raw_keys[canonical_key] = []
            canonical_to_raw_keys[canonical_key].append(raw_key)

        logger.info(
            "Union normalization: applying %d raw keys -> %d canonical keys",
            len(normalization_rules),
            len(canonical_to_raw_keys)
        )
        
        # Log the specific normalization mappings
        for canonical_key, raw_keys in canonical_to_raw_keys.items():
            logger.info(f"Union normalization: {raw_keys} -> '{canonical_key}'")

        # Create new sensor_data map with normalized keys (no duplicates)
        sensor_data_cols = []
        normalized_data_cols = []

        # Process each canonical key only once
        for canonical_key, raw_keys in canonical_to_raw_keys.items():
            # Create coalesce expression for all raw key variants
            raw_key_options = [df.sensor_data.getItem(raw_key) for raw_key in raw_keys]
            raw_key_options.append(df.sensor_data.getItem(canonical_key))  # include canonical key itself
            
            # Update sensor_data map
            sensor_data_cols.extend([
                F.lit(canonical_key),
                F.coalesce(*raw_key_options)
            ])

            # Update normalized_data map for numeric columns
            if canonical_key in ["temperature", "humidity", "pressure", "voltage", "current"]:
                # Try to convert any of the raw key variants to numeric
                numeric_options = []
                for raw_key in raw_keys:
                    numeric_options.append(
                        F.when(
                            df.sensor_data.getItem(raw_key).rlike(r"^-?\d+\.?\d*$"),
                            df.sensor_data.getItem(raw_key).cast("double")
                        )
                    )
                # Also include existing normalized value as fallback
                numeric_options.append(df.normalized_data.getItem(canonical_key))
                
                # Special logging for temperature
                if canonical_key == "temperature":
                    logger.info(f"Union normalization: processing temperature field from raw keys: {raw_keys}")
                
                normalized_data_cols.extend([
                    F.lit(canonical_key),
                    F.coalesce(*numeric_options)
                ])

        # Rebuild maps with normalized keys
        new_sensor_data = F.create_map(*sensor_data_cols) if sensor_data_cols else df.sensor_data
        new_normalized_data = F.create_map(*normalized_data_cols) if normalized_data_cols else df.normalized_data

        return df.select(
            "ingestion_id",
            "timestamp",
            new_sensor_data.alias("sensor_data"),
            new_normalized_data.alias("normalized_data")
        )

    @staticmethod
    def extract_column_from_union(df: DataFrame, column_name: str, prefer_normalized: bool = True) -> DataFrame:
        """Extract a specific column from union schema DataFrame.
        
        Args:
            df: Union schema DataFrame
            column_name: Name of column to extract
            prefer_normalized: If True, prefer normalized_data over sensor_data
            
        Returns:
            DataFrame with the extracted column added
        """
        if prefer_normalized:
            extracted_value = F.coalesce(
                df.normalized_data.getItem(column_name),
                df.sensor_data.getItem(column_name).cast("double")
            )
        else:
            extracted_value = F.coalesce(
                df.sensor_data.getItem(column_name),
                df.normalized_data.getItem(column_name).cast("string")
            )

        return df.withColumn(column_name, extracted_value)

    @staticmethod
    def merge_sensor_data(df: DataFrame, additional_data: Dict[str, Any]) -> DataFrame:
        """Merge additional sensor data into existing union schema DataFrame.
        
        Args:
            df: Union schema DataFrame
            additional_data: Dict of key-value pairs to add to sensor_data
            
        Returns:
            DataFrame with merged sensor_data
        """
        # Convert additional_data to map format
        additional_cols = []
        for key, value in additional_data.items():
            additional_cols.extend([F.lit(key), F.lit(str(value))])

        if additional_cols:
            additional_map = F.create_map(*additional_cols)
            # Merge with existing sensor_data
            # Use when to handle null sensor_data gracefully
            merged_sensor_data = F.when(
                F.col("sensor_data").isNotNull(),
                F.map_concat(F.col("sensor_data"), additional_map)
            ).otherwise(additional_map)
        else:
            merged_sensor_data = df.sensor_data

        return df.withColumn("sensor_data", merged_sensor_data)

    @staticmethod
    def validate_union_schema(df: DataFrame) -> bool:
        """Validate that DataFrame conforms to union schema.
        
        Args:
            df: DataFrame to validate
            
        Returns:
            True if valid, False otherwise
        """
        required_cols = {"ingestion_id", "timestamp", "sensor_data", "normalized_data"}
        actual_cols = set(df.columns)
        
        if not required_cols.issubset(actual_cols):
            missing = required_cols - actual_cols
            logger.error(f"Missing required columns for union schema: {missing}")
            return False

        # TODO: Add more detailed schema validation (data types, etc.)
        return True


def create_empty_union_dataframe(spark_session) -> DataFrame:
    """Create an empty DataFrame with union schema structure.
    
    Args:
        spark_session: Active Spark session
        
    Returns:
        Empty DataFrame with union schema
    """
    from ..config import SparkSchemas
    
    schema = SparkSchemas.get_union_schema()
    return spark_session.createDataFrame([], schema)


def create_empty_enriched_union_dataframe(spark_session) -> DataFrame:
    """Create an empty DataFrame with enriched union schema structure.
    
    Args:
        spark_session: Active Spark session
        
    Returns:
        Empty DataFrame with enriched union schema
    """
    from ..config import SparkSchemas
    
    schema = SparkSchemas.get_enriched_union_schema()
    return spark_session.createDataFrame([], schema)
