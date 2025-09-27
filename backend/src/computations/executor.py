"""Computation DSL execution engine using Spark DataFrames."""
import logging
from typing import Dict, Any, List
from difflib import get_close_matches
from pyspark.sql import functions as F
from src.spark.spark_manager import SparkManager
from src.computations.sources import get_source_aliases

logger = logging.getLogger(__name__)


class ComputationExecutor:
    """Executes computation definitions using Spark DataFrames."""
    
    def __init__(self, spark: SparkManager):
        self.spark = spark
        self.alias_maps = get_source_aliases()
    
    def execute_definition(self, definition: Dict[str, Any], dataset: str) -> List[dict]:
        """Execute a computation definition against the specified dataset.
        
        Args:
            definition: Computation definition with select, where, orderBy, limit, groupBy
            dataset: Target dataset (gold_temp_avg, enriched, bronze, etc.)
            
        Returns:
            List of result dictionaries
            
        Raises:
            RuntimeError: If Spark session is not available
            ValueError: If columns are missing or operations are unsupported
        """
        logger.info(f"Executing computation on dataset: {dataset}")
        
        # Load DataFrame for the dataset
        df = self._load_dataset(dataset)
        
        # Apply column aliases for backward compatibility
        normalized_def = self._normalize_definition(definition, dataset)
        
        # Validate referenced columns
        self._validate_columns(normalized_def, df)
        
        # Apply filters
        df = self._apply_filters(df, normalized_def.get("where", []))
        
        # Apply groupBy and aggregation
        if group_cols := normalized_def.get("groupBy"):
            df = self._apply_groupby(df, group_cols, normalized_def.get("select", []))
        else:
            # Apply select without grouping
            df = self._apply_select(df, normalized_def.get("select"))
        
        # Apply ordering
        df = self._apply_ordering(df, normalized_def.get("orderBy", []))
        
        # Apply limit and collect results
        limit = int(normalized_def.get("limit", 100))
        rows = df.limit(limit).collect()
        
        result = [r.asDict(recursive=True) for r in rows]
        logger.info(f"Computation returned {len(result)} rows")
        
        return result
    
    def _load_dataset(self, dataset: str):
        """Load DataFrame for the specified dataset."""
        session = self.spark.session_manager
        if not session.is_connected() and not session.reconnect():
            raise RuntimeError("Spark session not available")

        bucket = self.spark.streaming_manager.minio_bucket
        from src.spark.config import SparkConfig
        
        if dataset == "gold_temp_avg":
            path = f"s3a://{bucket}/{SparkConfig.GOLD_TEMP_AVG_PATH}"
            return session.spark.read.format("delta").load(path)
        elif dataset == "gold_alerts":
            path = f"s3a://{bucket}/{SparkConfig.GOLD_ALERTS_PATH}"
            return session.spark.read.format("delta").load(path)
        elif dataset == "enriched":
            path = f"s3a://{bucket}/{SparkConfig.ENRICHED_PATH}"
            return session.spark.read.format("delta").load(path)
        else:  # bronze and others
            base = f"s3a://{bucket}/{SparkConfig.BRONZE_PATH}"
            try:
                return session.spark.read.option("basePath", base).parquet(f"{base}date=*/hour=*")
            except Exception:
                return session.spark.read.parquet(base)
    
    def _normalize_definition(self, definition: Dict[str, Any], dataset: str) -> Dict[str, Any]:
        """Apply column aliases for backward compatibility."""
        alias_map = self.alias_maps.get(dataset, {})
        
        def apply_alias(col_name: str) -> str:
            return alias_map.get(col_name, col_name)
        
        normalized = {**definition}
        
        # Normalize select columns
        if definition.get("select"):
            normalized["select"] = [apply_alias(c) for c in definition["select"]]
        
        # Normalize where conditions
        if definition.get("where"):
            normalized["where"] = [
                {**w, "col": apply_alias(w.get("col"))} for w in definition["where"]
            ]
        
        # Normalize orderBy
        if definition.get("orderBy"):
            normalized["orderBy"] = [
                {**o, "col": apply_alias(o.get("col"))} for o in definition["orderBy"]
            ]
        
        return normalized
    
    def _validate_columns(self, definition: Dict[str, Any], df) -> None:
        """Validate that referenced columns exist in the DataFrame."""
        referenced_cols = set()
        
        # Collect column references from select (excluding aggregate functions and aliases)
        if definition.get("select"):
            for col_expr in definition["select"]:
                if isinstance(col_expr, str):
                    if " as " in col_expr:
                        # Extract source column from "column as alias" format
                        source_col = col_expr.split(" as ")[0].strip()
                        # Skip aggregate functions and window functions in validation
                        if not any(func in source_col.upper() for func in ["COUNT(", "AVG(", "MIN(", "MAX(", "SUM(", "WINDOW("]):
                            referenced_cols.add(source_col)
                    elif any(func in col_expr.upper() for func in ["COUNT(", "AVG(", "MIN(", "MAX(", "SUM(", "WINDOW("]):
                        # Skip aggregate functions and window functions for validation - they're handled during execution
                        continue
                    else:
                        referenced_cols.add(col_expr)
        
        # Collect references from where
        referenced_cols.update(w.get("col") for w in definition.get("where", []) if w.get("col"))
        
        # Collect references from groupBy (excluding window functions)
        if definition.get("groupBy"):
            for group_col in definition["groupBy"]:
                if not group_col.upper().startswith("WINDOW("):
                    referenced_cols.add(group_col)
        
        # For orderBy, we need to be more careful - skip columns that are aliases from aggregation
        if definition.get("orderBy"):
            # Get list of aliases created in SELECT clause
            select_aliases = set()
            if definition.get("select"):
                for col_expr in definition["select"]:
                    if isinstance(col_expr, str) and " as " in col_expr:
                        alias = col_expr.split(" as ")[1].strip()
                        select_aliases.add(alias)
            
            # Only validate orderBy columns that aren't select aliases
            for order_spec in definition.get("orderBy", []):
                col_name = order_spec.get("col")
                if col_name and col_name not in select_aliases:
                    referenced_cols.add(col_name)
        
        # Validate columns exist in DataFrame
        df_cols = set(df.columns)
        missing = []
        
        for col in referenced_cols:
            if not col:
                continue
                
            # Handle nested column references (e.g., "normalized_data.temperature")
            if "." in col:
                # For nested columns, check if the parent column exists
                parent_col = col.split(".")[0]
                if parent_col not in df_cols:
                    missing.append(col)
            else:
                # For simple column references
                if col not in df_cols:
                    missing.append(col)
        
        if missing:
            suggestions = {m: get_close_matches(m, list(df_cols), n=3, cutoff=0.5) for m in missing}
            error_msg = (
                f"Unknown column(s): {', '.join(missing)}. "
                f"Available: {', '.join(sorted(df_cols))}. "
                f"Suggestions: {'; '.join(f'{k} -> {v}' for k, v in suggestions.items())}"
            )
            raise ValueError(error_msg)
    
    def _apply_filters(self, df, where_conditions: List[Dict[str, Any]]):
        """Apply where conditions to the DataFrame."""
        for cond in where_conditions:
            col, op, val = cond.get("col"), cond.get("op"), cond.get("value")
            
            if op == ">":
                df = df.filter(F.col(col) > val)
            elif op == ">=":
                df = df.filter(F.col(col) >= val)
            elif op == "<":
                df = df.filter(F.col(col) < val)
            elif op == "<=":
                df = df.filter(F.col(col) <= val)
            elif op == "==":
                df = df.filter(F.col(col) == val)
            elif op == "!=":
                df = df.filter(F.col(col) != val)
            elif op == "contains":
                df = df.filter(F.col(col).contains(str(val)))
            elif op == "IS NOT NULL":
                df = df.filter(F.col(col).isNotNull())
            elif op == "IS NULL":
                df = df.filter(F.col(col).isNull())
            else:
                raise ValueError(f"Unsupported operator: {op}")
        
        return df
    
    def _apply_groupby(self, df, group_cols: List[str], select_cols: List[str]):
        """Apply groupBy with aggregation."""
        # Handle window functions in group_cols
        processed_group_cols = []
        for group_col in group_cols:
            if group_col.upper().startswith("WINDOW("):
                # For window functions, we need to parse and apply them
                processed_group_cols.append(self._parse_window_function(group_col))
            else:
                processed_group_cols.append(group_col)
        
        df_grouped = df.groupBy(*processed_group_cols)
        
        # Process select with aggregations
        agg_exprs = []
        for col_expr in select_cols:
            if isinstance(col_expr, str):
                if "(" in col_expr and ")" in col_expr:
                    # Check if it's a window function or aggregate function
                    if col_expr.upper().startswith("WINDOW("):
                        # Handle window function expressions
                        agg_expr = self._parse_window_function_select(col_expr)
                        agg_exprs.append(agg_expr)
                    else:
                        # Handle aggregate functions
                        agg_expr = self._parse_aggregate_function(col_expr)
                        agg_exprs.append(agg_expr)
                else:
                    # Regular column - check if it's in groupBy or needs aggregation
                    if " as " in col_expr:
                        # Handle column aliasing like "sensor_data.sensorId as sensor_id"
                        parts = col_expr.split(" as ")
                        original_col = parts[0].strip()
                        alias = parts[1].strip()
                        
                        # Check if this column is in the groupBy
                        if original_col in group_cols:
                            agg_exprs.append(F.col(original_col).alias(alias))
                        else:
                            # Use first() for non-grouped columns (they should be the same within each group)
                            agg_exprs.append(F.first(original_col).alias(alias))
                    else:
                        # Simple column reference
                        if col_expr in group_cols:
                            agg_exprs.append(F.col(col_expr))
                        else:
                            # Use first() for non-grouped columns
                            agg_exprs.append(F.first(col_expr))
            else:
                col_str = str(col_expr)
                if col_str in group_cols:
                    agg_exprs.append(F.col(col_str))
                else:
                    agg_exprs.append(F.first(col_str))
        
        return df_grouped.agg(*agg_exprs)
    
    def _parse_aggregate_function(self, col_expr: str):
        """Parse aggregate function expressions."""
        # Handle aliasing in aggregate functions
        alias_name = None
        if " as " in col_expr:
            parts = col_expr.split(" as ")
            col_expr = parts[0].strip()
            alias_name = parts[1].strip()
        
        if col_expr.startswith("COUNT("):
            if "COUNT(*)" in col_expr:
                result_alias = alias_name or "reading_count"
                return F.count("*").alias(result_alias)
            else:
                col_name = col_expr[6:-1]  # Remove COUNT( and )
                result_alias = alias_name or f"count_{col_name.split('.')[-1]}"
                return F.count(col_name).alias(result_alias)
        elif col_expr.startswith("AVG("):
            col_name = col_expr[4:-1]  # Remove AVG( and )
            result_alias = alias_name or f"avg_{col_name.split('.')[-1]}"
            return F.avg(col_name).alias(result_alias)
        elif col_expr.startswith("MIN("):
            col_name = col_expr[4:-1]  # Remove MIN( and )
            result_alias = alias_name or f"min_{col_name.split('.')[-1]}"
            return F.min(col_name).alias(result_alias)
        elif col_expr.startswith("MAX("):
            col_name = col_expr[4:-1]  # Remove MAX( and )
            result_alias = alias_name or f"max_{col_name.split('.')[-1]}"
            return F.max(col_name).alias(result_alias)
        elif col_expr.startswith("SUM("):
            col_name = col_expr[4:-1]  # Remove SUM( and )
            result_alias = alias_name or f"sum_{col_name.split('.')[-1]}"
            return F.sum(col_name).alias(result_alias)
        else:
            raise ValueError(f"Unsupported aggregate function: {col_expr}")
    
    def _parse_window_function(self, col_expr: str):
        """Parse window function for groupBy clause."""
        # Expected format: window(ingest_ts, '1 minute')
        if col_expr.upper().startswith("WINDOW("):
            # Extract parameters from window(column, duration)
            content = col_expr[7:-1]  # Remove WINDOW( and )
            parts = content.split(',')
            if len(parts) >= 2:
                time_col = parts[0].strip()
                duration = parts[1].strip().strip("'\"")
                return F.window(F.col(time_col), duration)
        raise ValueError(f"Unsupported window function format: {col_expr}")
    
    def _parse_window_function_select(self, col_expr: str):
        """Parse window function expressions in SELECT clause."""
        # Handle aliasing in window functions
        alias_name = None
        if " as " in col_expr:
            parts = col_expr.split(" as ")
            col_expr = parts[0].strip()
            alias_name = parts[1].strip()
        
        # Expected formats: 
        # - window(ingest_ts, '1 minute').start
        # - window(ingest_ts, '1 minute').end
        if ".start" in col_expr:
            window_expr = col_expr.replace(".start", "")
            window_func = self._parse_window_function(window_expr)
            result_alias = alias_name or "time_start"
            return window_func.start.alias(result_alias)
        elif ".end" in col_expr:
            window_expr = col_expr.replace(".end", "")
            window_func = self._parse_window_function(window_expr)
            result_alias = alias_name or "time_end"
            return window_func.end.alias(result_alias)
        else:
            raise ValueError(f"Unsupported window function select format: {col_expr}")
    
    def _apply_select(self, df, select_cols):
        """Apply select without grouping."""
        if not select_cols:
            return df
        
        select_exprs = []
        for col_expr in select_cols:
            if isinstance(col_expr, str):
                if " as " in col_expr:
                    # Handle column aliasing like "sensor_data.sensorId as sensor_id"
                    parts = col_expr.split(" as ")
                    original_col = parts[0].strip()
                    alias = parts[1].strip()
                    select_exprs.append(F.col(original_col).alias(alias))
                else:
                    select_exprs.append(F.col(col_expr))
            else:
                select_exprs.append(F.col(str(col_expr)))
        
        return df.select(*select_exprs)
    
    def _apply_ordering(self, df, order_by: List[Dict[str, str]]):
        """Apply orderBy to the DataFrame."""
        if not order_by:
            return df
        
        sort_cols = []
        for order_spec in order_by:
            col_name = order_spec["col"]
            direction = order_spec.get("dir", "asc").lower()
            
            if direction == "desc":
                sort_cols.append(F.col(col_name).desc())
            else:
                sort_cols.append(F.col(col_name).asc())
        
        return df.orderBy(*sort_cols) if sort_cols else df
