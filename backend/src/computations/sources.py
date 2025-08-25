"""Data source detection and schema inference utilities."""
import logging
from typing import List, Dict
from src.api.dependencies import ConfigDep, MinioClientDep
from src.spark.spark_manager import SparkManager

logger = logging.getLogger(__name__)


def has_any_objects(client, bucket: str, prefix: str) -> bool:
    """Check if any objects exist in the given MinIO bucket prefix."""
    try:
        for obj in client.list_objects(bucket, prefix=prefix, recursive=True):
            if not getattr(obj, 'is_dir', False):
                return True
    except Exception as e:
        logger.warning(f"Error checking objects in {bucket}/{prefix}: {e}")
        return False
    return False


def detect_available_sources(config: ConfigDep, client: MinioClientDep) -> List[str]:
    """Detect available data sources from MinIO storage."""
    from src.spark.config import SparkConfig
    sources: List[str] = []
    
    try:
        source_configs = [
            ("gold_temp_avg", SparkConfig.GOLD_TEMP_AVG_PATH),
            ("gold_alerts", SparkConfig.GOLD_ALERTS_PATH), 
            ("enriched", SparkConfig.ENRICHED_PATH),
            ("bronze", SparkConfig.BRONZE_PATH)
        ]
        
        for source_name, path in source_configs:
            if has_any_objects(client, config.minio_bucket, path):
                sources.append(source_name)
                logger.debug(f"Found data source: {source_name}")
            
    except Exception as e:
        logger.error(f"Error detecting sources: {e}")
        # On error, return empty to let frontend decide any fallback
        return []
    
    return sources


def infer_schemas(sources: List[str], spark: SparkManager) -> Dict[str, List[Dict[str, str]]]:
    """Infer column schemas for available data sources using Spark."""
    schemas: Dict[str, List[Dict[str, str]]] = {}
    
    # Ensure Spark session available
    session = spark.session_manager
    if not session.is_connected() and not session.reconnect():
        logger.warning("Spark session not available for schema inference")
        return schemas

    from src.spark.config import SparkConfig
    bucket = spark.streaming_manager.minio_bucket

    for source in sources:
        try:
            # Determine path and load DataFrame based on source type
            if source == "gold_temp_avg":
                path = f"s3a://{bucket}/{SparkConfig.GOLD_TEMP_AVG_PATH}"
                df = session.spark.read.format("delta").load(path)
            elif source == "gold_alerts":
                path = f"s3a://{bucket}/{SparkConfig.GOLD_ALERTS_PATH}"
                df = session.spark.read.format("delta").load(path)
            elif source == "enriched":
                path = f"s3a://{bucket}/{SparkConfig.ENRICHED_PATH}"
                df = session.spark.read.format("delta").load(path)
            elif source == "bronze":
                base = f"s3a://{bucket}/{SparkConfig.BRONZE_PATH}"
                # Use partitioned pattern if present; fallback to base path
                try:
                    df = session.spark.read.option("basePath", base).parquet(f"{base}date=*/hour=*")
                except Exception:
                    df = session.spark.read.parquet(base)
            else:
                logger.warning(f"Unknown source type: {source}")
                continue

            # Extract schema information
            fields = []
            for field in df.schema.fields:
                try:
                    dtype = field.dataType.simpleString()
                except Exception:
                    dtype = str(field.dataType)
                fields.append({"name": field.name, "type": dtype})
            
            schemas[source] = fields
            logger.debug(f"Inferred schema for {source}: {len(fields)} fields")
            
        except Exception as e:
            logger.warning(f"Failed to infer schema for {source}: {e}")
            # Skip if path not present or unreadable
            continue

    return schemas


def get_source_aliases() -> Dict[str, Dict[str, str]]:
    """Get column alias mappings for backward compatibility."""
    return {
        "silver": {
            "temperature": "avg_temp",
            "ts": "time_start",
            "timestamp": "time_start",
        },
        "gold": {
            # Map to gold_temp_avg structure - no aliasing needed as columns match
        },
        "gold_temp_avg": {
            # No aliasing needed - columns are already correct
        },
        "sensors": {
            "timestamp": "ts",
        },
        "alerts": {
            "timestamp": "ts",
        },
        "bronze": {
            # No aliasing needed - use actual bronze column names
        },
    }
