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
from pyspark.sql.types import StringType, MapType, DoubleType, StructType

logger = logging.getLogger(__name__)


class UnionSchemaTransformer:
    """Handles transformations between legacy and union schema formats."""

    @staticmethod
    def legacy_to_union(df: DataFrame, ingestion_id_col: str = "ingestion_id", schema: Optional[StructType] = None) -> DataFrame:
        """Convert legacy sensor DataFrame to union schema format.
        
        Args:
            df: Legacy DataFrame with direct columns (sensorId, temperature, etc.)
            ingestion_id_col: Name of the ingestion_id column.
            schema: Optional schema from inference (for type optimization). If provided, this schema will be used to optimize type conversions, especially for numeric fields, improving performance and accuracy. If not provided, type inference will be performed at runtime.
            
        Returns:
            DataFrame with union schema structure.
        """
        # Ensure required columns exist
        df = UnionSchemaTransformer._ensure_required_columns(df, ingestion_id_col)
        
        # Log transformation info
        logger.info(f"Legacy to union transformation: processing {len(df.columns)} columns: {df.columns}")
        
        # Create components
        timestamp_col = UnionSchemaTransformer._create_timestamp_column(df)
        sensor_data_map = UnionSchemaTransformer._create_sensor_data_map(df, ingestion_id_col)
        normalized_data_map = UnionSchemaTransformer._create_normalized_data_map(df, ingestion_id_col, schema)
        
        # Build union schema DataFrame
        # Handle ingestion_id column carefully to avoid duplicate column warnings
        if ingestion_id_col == "ingestion_id":
            # Column is already named correctly, no alias needed
            ingestion_id_selection = F.col("ingestion_id")
        else:
            # Column needs to be renamed to ingestion_id
            ingestion_id_selection = F.col(ingestion_id_col).alias("ingestion_id")
        
        return df.select(
            ingestion_id_selection,
            timestamp_col.alias("timestamp"),
            sensor_data_map.alias("sensor_data"),
            normalized_data_map.alias("normalized_data")
        )

    @staticmethod
    def _ensure_required_columns(df: DataFrame, ingestion_id_col: str) -> DataFrame:
        """Ensure required columns exist in the DataFrame."""
        if ingestion_id_col not in df.columns:
            logger.warning("ingestion_id column not found, using 'unknown'")
            df = df.withColumn(ingestion_id_col, F.lit("unknown"))
        return df

    @staticmethod
    def _create_timestamp_column(df: DataFrame):
        """Create a properly formatted timestamp column with multiple format fallbacks."""
        return F.coalesce(
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

    @staticmethod
    def _create_sensor_data_map(df: DataFrame, ingestion_id_col: str):
        """Create sensor_data map with all columns as strings."""
        sensor_data_cols: List = []
        sensor_cols_for_map: List[str] = []
        
        for col_name in df.columns:
            if col_name not in [ingestion_id_col, "timestamp"]:
                sensor_data_cols.append(F.lit(col_name))
                sensor_data_cols.append(F.col(col_name).cast("string"))
                sensor_cols_for_map.append(col_name)
        
        logger.info(f"Legacy to union: creating sensor_data map from columns: {sensor_cols_for_map}")
        
        return F.create_map(*sensor_data_cols) if sensor_data_cols else F.lit(None).cast(MapType(StringType(), StringType()))

    @staticmethod
    def _create_normalized_data_map(df: DataFrame, ingestion_id_col: str, schema: Optional[StructType] = None):
        """Create normalized_data map with numeric values, using schema optimization when available."""
        normalized_data_cols: List = []
        numeric_columns: List[str] = []
        
        for col_name in df.columns:
            if col_name not in [ingestion_id_col, "timestamp"]:
                # Determine numeric conversion strategy
                numeric_value = UnionSchemaTransformer._get_numeric_value(col_name, schema)
                
                # Include in normalized_data map
                normalized_data_cols.append(F.lit(col_name))
                normalized_data_cols.append(numeric_value)
                numeric_columns.append(col_name)
        
        logger.info(f"Legacy to union: created normalized_data for {len(numeric_columns)} columns: {numeric_columns}")
        
        return F.create_map(*normalized_data_cols) if normalized_data_cols else F.lit(None).cast(MapType(StringType(), DoubleType()))

    @staticmethod
    def _get_numeric_value(col_name: str, schema: Optional[StructType] = None):
        """Get numeric value for a column using schema optimization when available."""
        # Check if schema indicates this field is numeric
        if schema and UnionSchemaTransformer._is_numeric_by_schema(col_name, schema):
            logger.debug(f"Schema indicates '{col_name}' is numeric - using direct cast")
            return F.col(col_name).cast("double")
        else:
            # Fallback to runtime pattern matching (device-agnostic)
            return F.when(
                F.col(col_name).rlike(r"^-?\d+\.?\d*$"), 
                F.col(col_name).cast("double")
            ).otherwise(F.lit(None).cast("double"))

    @staticmethod
    def _is_numeric_by_schema(col_name: str, schema: StructType) -> bool:
        """Check if a column is numeric according to the schema."""
        try:
            field = next((f for f in schema.fields if f.name == col_name), None)
            if field:
                field_type: str = field.dataType.simpleString().lower()
                is_numeric: bool = any(numeric_type in field_type for numeric_type in 
                               ['double', 'float', 'int', 'long', 'decimal', 'number'])
                return is_numeric
        except Exception as e:
            logger.debug(f"Could not check schema for column '{col_name}': {e}")
        return False

    @staticmethod
    def union_to_legacy(df: DataFrame, extract_columns: Optional[List[str]] = None) -> DataFrame:
        """Convert union schema DataFrame back to legacy format.
        
        Args:
            df: Union schema DataFrame
            extract_columns: Specific columns to extract, if None extracts all available columns
            
        Returns:
            DataFrame with legacy schema structure
        """
        # Device-agnostic: if no specific columns requested, extract all available columns
        if extract_columns is None:
            # Get all keys from sensor_data map in the first row (if available)
            # This is device-agnostic - works with any sensor type
            try:
                # Try to get column names from the first non-null sensor_data
                sample_row = df.filter(F.col("sensor_data").isNotNull()).first()
                if sample_row and sample_row.sensor_data:
                    extract_columns = list(sample_row.sensor_data.keys())
                    logger.info(f"Union to legacy: auto-detected columns: {extract_columns}")
                else:
                    extract_columns = []
                    logger.info("Union to legacy: no sensor_data found, extracting base columns only")
            except Exception as e:
                logger.warning(f"Union to legacy: could not auto-detect columns: {e}")
                extract_columns = []

        # Start with base columns
        result_df: DataFrame = df.select("ingestion_id", "timestamp")

        # Extract specific columns from sensor_data map
        for col_name in extract_columns:
            result_df = result_df.withColumn(
                col_name,
                df.sensor_data.getItem(col_name)
            )

        # Device-agnostic: Extract numeric values from normalized_data map (preferred over string values)
        # Try to get numeric versions for any column that might have numeric data
        for col_name in extract_columns:
            # For any column, prefer the normalized (numeric) version if available
            result_df = result_df.withColumn(
                col_name,
                F.coalesce(
                    df.normalized_data.getItem(col_name),  # Try normalized first
                    F.col(col_name).cast("double")         # Fallback to casting string value
                )
            )

        return result_df

    @staticmethod
    def apply_normalization_to_union(df: DataFrame, normalization_rules: Dict[str, str], schema: Optional[StructType] = None) -> DataFrame:
        """Apply normalization rules to union schema DataFrame.
        
        Args:
            df: Union schema DataFrame
            normalization_rules: Dict mapping raw keys to canonical keys
            schema: Optional schema from inference (for type optimization)
            
        Returns:
            DataFrame with normalized keys in both sensor_data and normalized_data maps
        """
        # Group normalization rules by canonical key to avoid duplicates
        canonical_to_raw_keys: Dict[str, List[str]] = {}
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
        sensor_data_cols: List = []
        normalized_data_cols: List = []

        # Process each canonical key only once
        for canonical_key, raw_keys in canonical_to_raw_keys.items():
            # Create coalesce expression for all raw key variants
            raw_key_options: List = [df.sensor_data.getItem(raw_key) for raw_key in raw_keys]
            raw_key_options.append(df.sensor_data.getItem(canonical_key))  # include canonical key itself
            
            # Update sensor_data map
            sensor_data_cols.extend([
                F.lit(canonical_key),
                F.coalesce(*raw_key_options)
            ])

            # Create normalized_data map using schema optimization when available
            numeric_value = UnionSchemaTransformer._get_normalized_numeric_value(
                canonical_key, raw_keys, df, schema
            )
            
            normalized_data_cols.extend([
                F.lit(canonical_key),
                numeric_value
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
    def _get_normalized_numeric_value(canonical_key: str, raw_keys: List[str], df: DataFrame, schema: Optional[StructType] = None):
        """Get normalized numeric value using schema optimization when available."""
        # Check if schema indicates this canonical key should be numeric
        if schema and UnionSchemaTransformer._is_numeric_by_schema(canonical_key, schema):
            logger.debug(f"Schema indicates '{canonical_key}' is numeric - using optimized conversion")
            
            # For schema-identified numeric fields, try direct casting first
            numeric_options = []
            
            # Try existing normalized value first (it's already numeric)
            numeric_options.append(df.normalized_data.getItem(canonical_key))
            
            # Then try direct casting of raw key variants (they should be numeric strings)
            for raw_key in raw_keys:
                numeric_options.append(df.sensor_data.getItem(raw_key).cast("double"))
            
            return F.coalesce(*numeric_options)
        else:
            # Fallback to runtime pattern matching (device-agnostic)
            numeric_options = []
            
            # Include existing normalized value as fallback
            numeric_options.append(df.normalized_data.getItem(canonical_key))
            
            # Try to convert raw key variants using pattern matching
            for raw_key in raw_keys:
                numeric_options.append(
                    F.when(
                        df.sensor_data.getItem(raw_key).rlike(r"^-?\d+\.?\d*$"),
                        df.sensor_data.getItem(raw_key).cast("double")
                    )
                )
            
            return F.coalesce(*numeric_options)

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
    def get_available_sensor_fields(df: DataFrame) -> List[str]:
        """Get all available sensor field names from union schema DataFrame.
        
        This is device-agnostic - works with any sensor type.
        
        Args:
            df: Union schema DataFrame
            
        Returns:
            List of available sensor field names
        """
        try:
            # Get all keys from sensor_data map in the first row (if available)
            sample_row = df.filter(F.col("sensor_data").isNotNull()).first()
            if sample_row and sample_row.sensor_data:
                fields = list(sample_row.sensor_data.keys())
                logger.info(f"Available sensor fields: {fields}")
                return fields
            else:
                logger.info("No sensor_data found in DataFrame")
                return []
        except Exception as e:
            logger.warning(f"Could not extract sensor fields: {e}")
            return []

    @staticmethod
    def extract_all_available_columns(df: DataFrame, prefer_normalized: bool = True) -> DataFrame:
        """Extract all available columns from union schema DataFrame.
        
        This is device-agnostic - extracts whatever fields are available.
        
        Args:
            df: Union schema DataFrame
            prefer_normalized: If True, prefer normalized_data over sensor_data
            
        Returns:
            DataFrame with all available sensor columns extracted
        """
        available_fields = UnionSchemaTransformer.get_available_sensor_fields(df)
        
        result_df = df
        for field_name in available_fields:
            result_df = UnionSchemaTransformer.extract_column_from_union(
                result_df, field_name, prefer_normalized
            )
        
        return result_df

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
