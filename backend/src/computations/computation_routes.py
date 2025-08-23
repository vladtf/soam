"""Routers for user-defined computations."""
import json
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.models import ComputationCreate, ComputationUpdate, ComputationResponse, ApiResponse, ApiListResponse
from src.api.response_utils import success_response, list_response, not_found_error, bad_request_error, internal_server_error, conflict_error
from src.database.database import get_db
from src.database.models import Computation
from src.api.dependencies import get_spark_manager, ConfigDep, MinioClientDep
from src.spark.spark_manager import SparkManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["computations"])


def _validate_dataset(ds: str) -> str:
    ds = ds.lower()
    allowed_datasets = {"bronze", "silver", "gold"}
    if ds not in allowed_datasets:
        bad_request_error(f"Invalid dataset. Use {', '.join(allowed_datasets)}")
    return ds


def _validate_username(username: str) -> str:
    import re
    username = username.strip()
    if not (3 <= len(username) <= 32):
        bad_request_error("Username must be 3-32 characters long")
    if not re.match(r"^[A-Za-z0-9_.-]+$", username):
        bad_request_error("Username contains invalid characters")
    return username


# Example definitions to guide frontend users (datasets are validated separately)
EXAMPLE_DEFINITIONS: list[dict[str, Any]] = [
    {
        "id": "hot-temps",
        "title": "Top hot temperatures (silver)",
        "description": "Find readings with avg_temp > 25, sorted by avg_temp desc.",
        "dataset": "silver",
        "definition": {
            "select": ["sensorId", "avg_temp", "time_start"],
            "where": [
                {"col": "avg_temp", "op": ">", "value": 25}
            ],
            "orderBy": [
                {"col": "avg_temp", "dir": "desc"}
            ],
            "limit": 50
        }
    },
    {
        "id": "alerts-keyword",
        "title": "Alerts containing 'overheat' (alerts)",
        "description": "Filter alerts where message contains keyword.",
        "dataset": "alerts",
        "definition": {
            "select": ["id", "level", "message", "ts"],
            "where": [
                {"col": "message", "op": "contains", "value": "overheat"}
            ],
            "orderBy": [
                {"col": "ts", "dir": "desc"}
            ],
            "limit": 20
        }
    },
    {
        "id": "below-zero",
        "title": "Negative temperature metrics (sensors)",
        "description": "Metric == temperature and value < 0.",
        "dataset": "sensors",
        "definition": {
            "where": [
                {"col": "metric", "op": "==", "value": "temperature"},
                {"col": "value", "op": "<", "value": 0}
            ],
            "orderBy": [
                {"col": "ts", "dir": "desc"}
            ],
            "limit": 100
        }
    }
]


def _has_any_objects(client, bucket: str, prefix: str) -> bool:
    try:
        for obj in client.list_objects(bucket, prefix=prefix, recursive=True):
            if not getattr(obj, 'is_dir', False):
                return True
    except Exception:
        return False
    return False


def _detect_available_sources(config: ConfigDep, client: MinioClientDep) -> list[str]:
    from src.spark.config import SparkConfig
    sources: list[str] = []
    try:
        if _has_any_objects(client, config.minio_bucket, SparkConfig.GOLD_TEMP_AVG_PATH):
            sources.append("gold_temp_avg")
        if _has_any_objects(client, config.minio_bucket, SparkConfig.GOLD_ALERTS_PATH):
            sources.append("gold_alerts")
        if _has_any_objects(client, config.minio_bucket, SparkConfig.ENRICHED_PATH):
            sources.append("enriched")
        if _has_any_objects(client, config.minio_bucket, SparkConfig.BRONZE_PATH):
            sources.append("bronze")
    except Exception:
        # On error, return empty to let frontend decide any fallback
        return []
    return sources


@router.get("/computations/examples", response_model=ApiResponse)
def get_examples(config: ConfigDep, client: MinioClientDep):
    """Return suggested examples and available sources (datasets) discovered from MinIO."""
    sources = _detect_available_sources(config, client)
    data = {
        "sources": sources,
        "examples": EXAMPLE_DEFINITIONS,
        "dsl": {
            "keys": ["select", "where", "orderBy", "limit"],
            "ops": [">", ">=", "<", "<=", "==", "!=", "contains"],
            "notes": "All where conditions are ANDed. Dataset is chosen separately as 'silver' | 'alerts' | 'sensors'."
        }
    }
    return success_response(data, "Examples retrieved successfully")


@router.get("/computations/sources", response_model=ApiResponse)
def get_sources(config: ConfigDep, client: MinioClientDep):
    sources = _detect_available_sources(config, client)
    return success_response({"sources": sources}, "Sources retrieved successfully")


@router.get("/computations/schemas", response_model=ApiResponse)
def get_schemas(config: ConfigDep, client: MinioClientDep, spark: SparkManager = Depends(get_spark_manager)):
    """Return detected sources plus inferred column schemas for each source using Spark."""
    sources = _detect_available_sources(config, client)
    schemas: Dict[str, list[Dict[str, str]]] = {}

    # Ensure Spark session available
    session = spark.session_manager
    if not session.is_connected() and not session.reconnect():
        return success_response({"sources": sources, "schemas": schemas}, "Schemas retrieved (Spark unavailable)")

    from src.spark.config import SparkConfig

    for src in sources:
        try:
            if src == "gold_temp_avg":
                path = f"s3a://{spark.streaming_manager.minio_bucket}/{SparkConfig.GOLD_TEMP_AVG_PATH}"
                df = session.spark.read.format("delta").load(path)
            elif src == "gold_alerts":
                path = f"s3a://{spark.streaming_manager.minio_bucket}/{SparkConfig.GOLD_ALERTS_PATH}"
                df = session.spark.read.format("delta").load(path)
            elif src == "enriched":
                path = f"s3a://{spark.streaming_manager.minio_bucket}/{SparkConfig.ENRICHED_PATH}"
                df = session.spark.read.format("delta").load(path)
            else:  # bronze
                base = f"s3a://{spark.streaming_manager.minio_bucket}/{SparkConfig.BRONZE_PATH}"
                # Use partitioned pattern if present; fallback to base path
                try:
                    df = session.spark.read.option("basePath", base).parquet(f"{base}date=*/hour=*")
                except Exception:
                    df = session.spark.read.parquet(base)

            fields = []
            for f in df.schema.fields:
                try:
                    dtype = f.dataType.simpleString()
                except Exception:
                    dtype = str(f.dataType)
                fields.append({"name": f.name, "type": dtype})
            schemas[src] = fields
        except Exception:
            # Skip if path not present or unreadable
            continue

    return success_response({"sources": sources, "schemas": schemas}, "Schemas retrieved successfully")


@router.get("/computations", response_model=ApiListResponse[ComputationResponse])
def list_computations(db: Session = Depends(get_db)):
    try:
        rows = db.query(Computation).order_by(Computation.created_at.desc()).all()
        computations = [ComputationResponse(**r.to_dict()) for r in rows]
        return list_response(computations, message="Computations retrieved successfully")
    except Exception as e:
        logger.error("Error listing computations: %s", e)
        internal_server_error("Failed to retrieve computations", str(e))


@router.post("/computations", response_model=ApiResponse[ComputationResponse])
def create_computation(payload: ComputationCreate, db: Session = Depends(get_db)):
    # Validate user is provided
    if not payload.created_by or not payload.created_by.strip():
        bad_request_error("User information required (created_by)")

    _ = _validate_dataset(payload.dataset)

    payload.created_by = _validate_username(payload.created_by)
    # Additional sanitization to prevent SQL injection or unsafe characters
    import re
    if re.search(r"[;'\"]|--|\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE)\b", payload.created_by, re.IGNORECASE):
        bad_request_error("Username contains unsafe characters or SQL keywords")

    # Unique name check
    if db.query(Computation).filter(Computation.name == payload.name).first():
        conflict_error("Computation name already exists")
    row = Computation(
        name=payload.name,
        description=payload.description,
        dataset=payload.dataset.lower(),
        definition=json.dumps(payload.definition),
        enabled=payload.enabled,
        created_by=payload.created_by.strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("Computation created by '%s': %s (%s)",
                payload.created_by, row.name, row.dataset)
    return success_response(
        ComputationResponse(**row.to_dict()),
        "Computation created successfully"
    )


@router.patch("/computations/{comp_id}", response_model=ApiResponse[ComputationResponse])
def update_computation(comp_id: int, payload: ComputationUpdate, db: Session = Depends(get_db)):
    # Validate user is provided
    if not payload.updated_by or not payload.updated_by.strip():
        bad_request_error("User information required (updated_by)")

    row = db.get(Computation, comp_id)
    if not row:
        not_found_error("Not found")

    changes = []
    if payload.description is not None and payload.description != row.description:
        changes.append(f"description: '{row.description or ''}' -> '{payload.description}'")
        row.description = payload.description
    if payload.dataset is not None and payload.dataset != row.dataset:
        new_dataset = _validate_dataset(payload.dataset)
        changes.append(f"dataset: '{row.dataset}' -> '{new_dataset}'")
        row.dataset = new_dataset
    if payload.definition is not None:
        import hashlib
        old_def = json.loads(row.definition) if row.definition else {}

        def _json_hash(obj):
            return hashlib.md5(json.dumps(obj, sort_keys=True).encode('utf-8')).hexdigest()
        if _json_hash(payload.definition) != _json_hash(old_def):
            changes.append("definition updated")
            row.definition = json.dumps(payload.definition)
    if payload.enabled is not None and payload.enabled != row.enabled:
        changes.append(f"enabled: {row.enabled} -> {payload.enabled}")
        row.enabled = payload.enabled

    row.updated_by = payload.updated_by.strip()

    db.add(row)
    db.commit()
    db.refresh(row)

    if changes:
        logger.info("Computation %d updated by '%s': %s",
                    row.id, payload.updated_by, "; ".join(changes))
    else:
        logger.info("Computation %d touched by '%s' (no changes)",
                    row.id, payload.updated_by)

    return success_response(
        ComputationResponse(**row.to_dict()),
        "Computation updated successfully"
    )


@router.delete("/computations/{comp_id}", response_model=ApiResponse)
def delete_computation(comp_id: int, db: Session = Depends(get_db)):
    row = db.get(Computation, comp_id)
    if not row:
        not_found_error("Not found")
    db.delete(row)
    db.commit()
    return success_response(message="Computation deleted successfully")


@router.post("/computations/{comp_id}/preview", response_model=ApiResponse)
def preview_computation(comp_id: int, db: Session = Depends(get_db), spark: SparkManager = Depends(get_spark_manager)):
    row = db.get(Computation, comp_id)
    if not row:
        not_found_error("Not found")
    try:
        definition = json.loads(row.definition)
    except Exception:
        bad_request_error("Invalid JSON definition")

    # Execute a minimal set of operations using Spark
    try:
        result = _execute_definition(definition, row.dataset, spark)
        return success_response(result, "Computation preview executed successfully")
    except Exception as e:
        logger.exception("Computation preview failed")
        bad_request_error(str(e))


def _execute_definition(defn: Dict[str, Any], dataset: str, spark: SparkManager) -> list[dict]:
    """Very small DSL executor over Spark DataFrames.

    defn example:
    {
      "source": "silver",
      "select": ["sensorId", "avg_temp"],
      "where": [{"col": "avg_temp", "op": ">", "value": 25}],
      "limit": 50,
      "orderBy": [{"col": "avg_temp", "dir": "desc"}]
    }
    """
    from pyspark.sql import functions as F

    # Resolve path based on dataset
    session = spark.session_manager
    if not session.is_connected() and not session.reconnect():
        raise RuntimeError("Spark session not available")

    bucket = spark.streaming_manager.minio_bucket
    from src.spark.config import SparkConfig
    if dataset == "gold_temp_avg":
        path = f"s3a://{bucket}/{SparkConfig.GOLD_TEMP_AVG_PATH}"
        df = session.spark.read.format("delta").load(path)
    elif dataset == "gold_alerts":
        path = f"s3a://{bucket}/{SparkConfig.GOLD_ALERTS_PATH}"
        df = session.spark.read.format("delta").load(path)
    elif dataset == "enriched":
        path = f"s3a://{bucket}/{SparkConfig.ENRICHED_PATH}"
        df = session.spark.read.format("delta").load(path)
    else:
        base = f"s3a://{bucket}/{SparkConfig.BRONZE_PATH}"
        try:
            df = session.spark.read.option("basePath", base).parquet(f"{base}date=*/hour=*")
        except Exception:
            df = session.spark.read.parquet(base)

    # Provide friendly aliases for common column names per dataset (backward compatibility)
    alias_map_all = {
        "silver": {
            "temperature": "avg_temp",
            "ts": "time_start",
            "timestamp": "time_start",
        },
        "sensors": {
            "timestamp": "ts",
        },
        "alerts": {
            "timestamp": "ts",
        },
    }

    alias_map = alias_map_all.get(dataset, {})

    # Helper to apply alias if target exists in the DataFrame
    def _apply_alias(col_name: str) -> str:
        target = alias_map.get(col_name, col_name)
        return target

    # Normalize definition column references using alias map
    normalized = {
        **defn,
        "select": [
            _apply_alias(c) for c in defn.get("select", [])
        ] if defn.get("select") else defn.get("select"),
        "where": [
            {**w, "col": _apply_alias(w.get("col"))} for w in defn.get("where", [])
        ],
        "orderBy": [
            {**o, "col": _apply_alias(o.get("col"))} for o in defn.get("orderBy", [])
        ],
    }

    # Validate referenced columns exist, with suggestions
    from difflib import get_close_matches

    referenced_cols = set()
    if normalized.get("select"):
        referenced_cols.update(normalized["select"])
    referenced_cols.update(w.get("col") for w in normalized.get("where", []) if w.get("col"))
    referenced_cols.update(o.get("col") for o in normalized.get("orderBy", []) if o.get("col"))

    df_cols = set(df.columns)
    missing = [c for c in referenced_cols if c not in df_cols]
    if missing:
        suggestions: dict[str, list[str]] = {m: get_close_matches(m, list(df_cols), n=3, cutoff=0.5) for m in missing}
        raise ValueError(
            "Unknown column(s): "
            + ", ".join(missing)
            + ". Available: "
            + ", ".join(sorted(df_cols))
            + ". Suggestions: "
            + "; ".join(f"{k} -> {v}" for k, v in suggestions.items())
        )

    # select
    if cols := normalized.get("select"):
        df = df.select(*cols)

    # where (AND combination)
    for cond in normalized.get("where", []):
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
        else:
            raise ValueError(f"Unsupported op: {op}")

    # orderBy
    if order := normalized.get("orderBy"):
        sort_cols = []
        for c in order:
            if c.get("dir", "asc").lower() == "desc":
                sort_cols.append(F.col(c["col"]).desc())
            else:
                sort_cols.append(F.col(c["col"]).asc())
        if sort_cols:
            df = df.orderBy(*sort_cols)

    # limit
    limit = int(normalized.get("limit", 100))
    rows = df.limit(limit).collect()
    return [r.asDict(recursive=True) for r in rows]
