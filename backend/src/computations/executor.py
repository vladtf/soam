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
        
        # Collect column references from select
        if definition.get("select"):
            for col_expr in definition["select"]:
                if isinstance(col_expr, str):
                    if " as " in col_expr:
                        # Extract source column from "column as alias" format
                        source_col = col_expr.split(" as ")[0].strip()
                        referenced_cols.add(source_col)
                    elif "(" in col_expr and ")" in col_expr:
                        # Skip aggregate functions for validation
                        continue
                    else:
                        referenced_cols.add(col_expr)
        
        # Collect references from where, orderBy, groupBy
        referenced_cols.update(w.get("col") for w in definition.get("where", []) if w.get("col"))
        referenced_cols.update(o.get("col") for o in definition.get("orderBy", []) if o.get("col"))
        if definition.get("groupBy"):
            referenced_cols.update(definition["groupBy"])
        
        # Filter out complex expressions and check simple column references
        df_cols = set(df.columns)
        simple_refs = {c for c in referenced_cols if c and not c.startswith(("normalized_data.", "sensor_data."))}
        missing = [c for c in simple_refs if c not in df_cols]
        
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
        df_grouped = df.groupBy(*group_cols)
        
        # Process select with aggregations
        agg_exprs = []
        for col_expr in select_cols:
            if isinstance(col_expr, str):
                if "(" in col_expr and ")" in col_expr:
                    # Handle aggregate functions
                    agg_expr = self._parse_aggregate_function(col_expr)
                    agg_exprs.append(agg_expr)
                else:
                    # Regular column (should be in groupBy)
                    agg_exprs.append(F.col(col_expr))
            else:
                agg_exprs.append(F.col(str(col_expr)))
        
        return df_grouped.agg(*agg_exprs)
    
    def _parse_aggregate_function(self, col_expr: str):
        """Parse aggregate function expressions."""
        if col_expr.startswith("COUNT("):
            if "COUNT(*)" in col_expr:
                return F.count("*").alias("reading_count")
            else:
                col_name = col_expr[6:-1]  # Remove COUNT( and )
                return F.count(col_name).alias(f"count_{col_name}")
        elif col_expr.startswith("AVG("):
            col_name = col_expr[4:-1]  # Remove AVG( and )
            alias_name = f"avg_{col_name.split('.')[-1]}"  # Handle nested columns
            return F.avg(col_name).alias(alias_name)
        elif col_expr.startswith("MIN("):
            col_name = col_expr[4:-1]  # Remove MIN( and )
            alias_name = f"min_{col_name.split('.')[-1]}"
            return F.min(col_name).alias(alias_name)
        elif col_expr.startswith("MAX("):
            col_name = col_expr[4:-1]  # Remove MAX( and )
            alias_name = f"max_{col_name.split('.')[-1]}"
            return F.max(col_name).alias(alias_name)
        elif col_expr.startswith("SUM("):
            col_name = col_expr[4:-1]  # Remove SUM( and )
            alias_name = f"sum_{col_name.split('.')[-1]}"
            return F.sum(col_name).alias(alias_name)
        else:
            raise ValueError(f"Unsupported aggregate function: {col_expr}")
    
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
