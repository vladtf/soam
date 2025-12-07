"""
Client service for fetching schema information from the ingestor API.
"""
import asyncio
import httpx
import time
from typing import Dict, List, Any, Optional
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, LongType,
    DoubleType, FloatType, BooleanType, TimestampType, DateType
)
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Type mapping from ingestor schema types to Spark types
# Note: All numeric types map to DoubleType because the ingestor writes
# all numerics as float64 in Parquet for schema consistency.
# Timestamps are mapped to StringType because they're stored as ISO strings.
INGESTOR_TO_SPARK_TYPE = {
    "string": StringType(),
    "str": StringType(),
    "int": DoubleType(),        # Stored as double in Parquet
    "integer": DoubleType(),    # Stored as double in Parquet
    "long": DoubleType(),       # Stored as double in Parquet
    "bigint": DoubleType(),     # Stored as double in Parquet
    "float": DoubleType(),      # Widened to double for consistency
    "double": DoubleType(),
    "number": DoubleType(),
    "bool": BooleanType(),
    "boolean": BooleanType(),
    "timestamp": StringType(),  # Stored as ISO string in Parquet
    "datetime": StringType(),   # Stored as ISO string in Parquet
    "date": StringType(),       # Stored as ISO string in Parquet
    "uuid": StringType(),       # UUIDs are strings
}


class IngestorSchemaClient:
    """Client for fetching schema information from ingestor metadata API."""
    
    def __init__(self, ingestor_base_url: str = "http://ingestor:8001"):
        """Initialize the ingestor schema client.
        
        Args:
            ingestor_base_url: Base URL for the ingestor service
        """
        self.base_url = ingestor_base_url.rstrip('/')
        self.timeout = 30.0
        
    async def get_all_datasets(self) -> List[Dict[str, Any]]:
        """Get all available datasets from ingestor."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/metadata/datasets")
                if response.status_code == 200:
                    data = response.json()
                    datasets = data.get("data", [])
                    logger.info("✅ Retrieved %d datasets from ingestor", len(datasets))
                    return datasets
                else:
                    logger.error("❌ Failed to fetch datasets: HTTP %d", response.status_code)
                    return []
        except Exception as e:
            logger.error("❌ Error fetching datasets from ingestor: %s", e)
            return []
    
    async def get_dataset_schema(self, ingestion_id: str) -> Optional[Dict[str, Any]]:
        """Get schema for a specific dataset.
        
        Args:
            ingestion_id: The ingestion ID to get schema for
            
        Returns:
            Schema information or None if not found
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.base_url}/api/metadata/datasets/{ingestion_id}/schema"
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    schema_info = data.get("data", {})
                    logger.info("✅ Retrieved schema for ingestion_id: %s", ingestion_id)
                    return schema_info
                elif response.status_code == 404:
                    logger.warning("⚠️ Schema not found for ingestion_id: %s", ingestion_id)
                    return None
                else:
                    logger.error("❌ Failed to fetch schema for %s: HTTP %d", ingestion_id, response.status_code)
                    return None
        except Exception as e:
            logger.error("❌ Error fetching schema for %s: %s", ingestion_id, e)
            return None
    
    async def get_topics_summary(self) -> Dict[str, Any]:
        """Get summary of all topics and their schemas."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/metadata/topics")
                if response.status_code == 200:
                    data = response.json()
                    summary = data.get("data", {})
                    logger.info("✅ Retrieved topics summary from ingestor")
                    return summary
                else:
                    logger.error("❌ Failed to fetch topics summary: HTTP %d", response.status_code)
                    return {}
        except Exception as e:
            logger.error("❌ Error fetching topics summary: %s", e)
            return {}
    
    async def get_schema_evolution(self, ingestion_id: str) -> List[Dict[str, Any]]:
        """Get schema evolution history for a dataset.
        
        Args:
            ingestion_id: The ingestion ID to get evolution for
            
        Returns:
            List of schema evolution entries
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.base_url}/api/metadata/datasets/{ingestion_id}/evolution"
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    evolution = data.get("data", [])
                    logger.info("✅ Retrieved schema evolution for %s: %d entries", ingestion_id, len(evolution))
                    return evolution
                else:
                    logger.error("❌ Failed to fetch schema evolution for %s: HTTP %d", ingestion_id, response.status_code)
                    return []
        except Exception as e:
            logger.error("❌ Error fetching schema evolution for %s: %s", ingestion_id, e)
            return []
    
    async def build_data_context(self) -> Dict[str, Any]:
        """Build comprehensive data context from ingestor metadata."""
        try:
            logger.info("🔧 Building data context from ingestor metadata...")
            
            # Fetch all datasets and topics summary in parallel
            datasets_task = self.get_all_datasets()
            topics_task = self.get_topics_summary()
            
            datasets, topics_summary = await asyncio.gather(datasets_task, topics_task)
            
            # Build context structure
            context = {
                "sources": {},
                "total_sources": len(datasets),
                "total_fields": 0,
                "total_records": 0,
                "last_updated": None
            }
            
            # Process datasets into sources format
            for dataset in datasets:
                ingestion_id = dataset.get("ingestion_id")
                if not ingestion_id:
                    continue
                    
                # Get schema details for this dataset
                schema_info = await self.get_dataset_schema(ingestion_id)
                
                source_info = {
                    "ingestion_id": ingestion_id,
                    "fields": [],
                    "field_count": dataset.get("field_count", 0),
                    "record_count": dataset.get("record_count", 0),
                    "first_seen": dataset.get("first_seen"),
                    "last_updated": dataset.get("last_updated"),
                    "sample_data": dataset.get("sample_data")
                }
                
                # Extract field information from schema
                if schema_info and "schema" in schema_info:
                    schema_dict = schema_info["schema"]
                    for field_name, field_info in schema_dict.items():
                        source_info["fields"].append({
                            "name": field_name,
                            "type": field_info.get("type", "unknown"),
                            "nullable": field_info.get("nullable", True)
                        })
                
                context["sources"][ingestion_id] = source_info
                context["total_fields"] += source_info["field_count"]
                context["total_records"] += source_info["record_count"]
                
                # Track latest update
                if source_info["last_updated"]:
                    if not context["last_updated"] or source_info["last_updated"] > context["last_updated"]:
                        context["last_updated"] = source_info["last_updated"]
            
            logger.info("✅ Data context built successfully from ingestor")
            logger.info("📊 Context: %d sources, %d total fields, %d total records", 
                       context["total_sources"], context["total_fields"], context["total_records"])
            
            return context
            
        except Exception as e:
            logger.error("❌ Error building data context from ingestor: %s", e)
            return {
                "sources": {},
                "total_sources": 0,
                "total_fields": 0,
                "total_records": 0,
                "last_updated": None,
                "error": str(e)
            }
    
    def get_schema_info_sync(self, ingestion_id: str = None) -> List[Dict[str, Any]]:
        """Synchronous wrapper for getting schema info (backward compatibility).
        
        Args:
            ingestion_id: Optional ingestion ID filter
            
        Returns:
            List of schema information entries
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if ingestion_id:
                    schema_info = loop.run_until_complete(self.get_dataset_schema(ingestion_id))
                    return [schema_info] if schema_info else []
                else:
                    datasets = loop.run_until_complete(self.get_all_datasets())
                    return datasets
            finally:
                loop.close()
        except Exception as e:
            logger.error("❌ Error in sync schema info fetch: %s", e)
            return []
    
    def get_available_sources_sync(self) -> List[str]:
        """Synchronous wrapper for getting available sources."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                datasets = loop.run_until_complete(self.get_all_datasets())
                return [dataset.get("ingestion_id") for dataset in datasets if dataset.get("ingestion_id")]
            finally:
                loop.close()
        except Exception as e:
            logger.error("❌ Error in sync available sources fetch: %s", e)
            return []

    def get_merged_spark_schema_sync(self, cache_ttl_seconds: int = 300) -> Optional[StructType]:
        """Get merged Spark schema from all datasets with caching.
        
        This method fetches schema information from the ingestor for all datasets
        and merges them into a single Spark StructType. It uses caching to avoid
        repeated HTTP calls.
        
        Args:
            cache_ttl_seconds: Cache time-to-live in seconds (default 5 minutes)
            
        Returns:
            Merged Spark StructType, or None if no schemas available
        """
        # Check cache first
        if hasattr(self, '_schema_cache') and self._schema_cache:
            cache_time, cached_schema = self._schema_cache
            if time.time() - cache_time < cache_ttl_seconds:
                logger.info("✅ Using cached Spark schema (age: %.1fs)", time.time() - cache_time)
                return cached_schema
        
        try:
            logger.info("🔍 Fetching merged Spark schema from ingestor...")
            
            # Use synchronous HTTP client to avoid event loop conflicts
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(f"{self.base_url}/api/metadata/datasets")
                if response.status_code != 200:
                    logger.error("❌ Failed to fetch datasets: HTTP %d", response.status_code)
                    return None
                data = response.json()
                # API returns {"data": {"datasets": [...], "total": N}, ...}
                datasets = data.get("data", {}).get("datasets", [])
            
            if not datasets:
                logger.warning("⚠️ No datasets found in ingestor")
                return None
            
            logger.info("✅ Retrieved %d datasets from ingestor", len(datasets))
            
            # Merge all schema fields from all datasets
            merged_schema = self._merge_dataset_schemas(datasets)
            
            if merged_schema:
                # Cache the result
                self._schema_cache = (time.time(), merged_schema)
                logger.info("✅ Cached merged Spark schema with %d fields", len(merged_schema.fields))
            
            return merged_schema
            
        except Exception as e:
            logger.error("❌ Error fetching merged Spark schema: %s", e)
            return None
    
    def _merge_dataset_schemas(self, datasets: List[Dict[str, Any]]) -> Optional[StructType]:
        """Merge schema fields from multiple datasets into a single Spark StructType.
        
        Args:
            datasets: List of dataset metadata dictionaries
            
        Returns:
            Merged Spark StructType
        """
        import json
        
        all_fields: Dict[str, StructField] = {}
        
        for dataset in datasets:
            ingestion_id = dataset.get("ingestion_id", "unknown")
            schema_fields = dataset.get("schema_fields", [])
            
            # Handle case where schema_fields is a JSON string
            if isinstance(schema_fields, str):
                try:
                    schema_fields = json.loads(schema_fields)
                except json.JSONDecodeError:
                    logger.warning("⚠️ Could not parse schema_fields for %s", ingestion_id)
                    schema_fields = []
            
            if not schema_fields:
                logger.debug("ℹ️ No schema fields for dataset %s", ingestion_id)
                continue
            
            for field in schema_fields:
                field_name = field.get("name")
                field_type = field.get("type", "string").lower()
                nullable = field.get("nullable", True)
                
                if not field_name:
                    continue
                
                # Convert ingestor type to Spark type
                spark_type = INGESTOR_TO_SPARK_TYPE.get(field_type, StringType())
                
                if field_name not in all_fields:
                    # New field - add it
                    all_fields[field_name] = StructField(field_name, spark_type, nullable)
                else:
                    # Field already exists - resolve type conflicts
                    existing_field = all_fields[field_name]
                    resolved_type = self._resolve_type_conflict(
                        field_name, existing_field.dataType, spark_type
                    )
                    all_fields[field_name] = StructField(
                        field_name, 
                        resolved_type, 
                        existing_field.nullable or nullable
                    )
        
        if not all_fields:
            logger.warning("⚠️ No schema fields found in datasets")
            return None
        
        # Ensure ingestion_id is present (required for partitioning)
        if "ingestion_id" not in all_fields:
            all_fields["ingestion_id"] = StructField("ingestion_id", StringType(), True)
        
        # Create StructType with sorted fields for consistency
        sorted_fields = [all_fields[name] for name in sorted(all_fields.keys())]
        merged_schema = StructType(sorted_fields)
        
        logger.info("✅ Merged %d datasets into schema with %d fields", 
                   len(datasets), len(merged_schema.fields))
        
        return merged_schema
    
    def _resolve_type_conflict(self, field_name: str, type1, type2) -> Any:
        """Resolve type conflicts between two Spark data types.
        
        Uses type promotion hierarchy: bool -> int -> long -> float -> double -> string
        
        Args:
            field_name: Field name (for logging)
            type1: First Spark data type
            type2: Second Spark data type
            
        Returns:
            Resolved Spark data type
        """
        if type(type1) == type(type2):
            return type1
        
        # Define type promotion hierarchy (index order = promotion order)
        numeric_hierarchy = [
            BooleanType,
            IntegerType,
            LongType,
            FloatType,
            DoubleType,
        ]
        
        type1_class = type(type1)
        type2_class = type(type2)
        
        # Check if both are numeric types
        pos1 = next((i for i, t in enumerate(numeric_hierarchy) if t == type1_class), -1)
        pos2 = next((i for i, t in enumerate(numeric_hierarchy) if t == type2_class), -1)
        
        if pos1 >= 0 and pos2 >= 0:
            # Both are numeric - promote to the more general type
            promoted_type = numeric_hierarchy[max(pos1, pos2)]()
            logger.debug("🔢 Type promotion for '%s': %s + %s -> %s", 
                        field_name, type1, type2, promoted_type)
            return promoted_type
        
        # If one is numeric and one is string, or both are different non-numeric, use string
        logger.debug("🔤 Fallback to string for '%s': %s + %s -> StringType", 
                    field_name, type1, type2)
        return StringType()
    
    def invalidate_cache(self):
        """Invalidate the schema cache."""
        self._schema_cache = None
        logger.info("🔄 Schema cache invalidated")
