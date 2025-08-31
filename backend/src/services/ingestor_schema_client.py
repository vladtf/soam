"""
Client service for fetching schema information from the ingestor API.
"""
import asyncio
import httpx
from typing import Dict, List, Any, Optional
from src.utils.logging import get_logger

logger = get_logger(__name__)


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
