"""
Copilot service for AI-powered computation generation using Azure OpenAI.
"""
from typing import Dict, List, Any, Optional
import json
from datetime import datetime, date
from decimal import Decimal
from openai import AzureOpenAI
from pydantic import BaseModel
from src.computations.examples import EXAMPLE_DEFINITIONS
from src.computations.validation import validate_computation_definition
from src.spark.spark_manager import SparkManager
from src.services.ingestor_schema_client import IngestorSchemaClient
from src.utils.logging import get_logger

logger = get_logger(__name__)

class ComputationRequest(BaseModel):
    user_prompt: str
    context: Optional[str] = None
    preferred_dataset: Optional[str] = None

class ComputationSuggestion(BaseModel):
    title: str
    description: str
    dataset: str
    definition: Dict[str, Any]  # Changed from str to Dict
    confidence: float
    explanation: str
    suggested_columns: List[str]

class CopilotService:
    def __init__(self, azure_endpoint: str, api_key: str, api_version: str = "2024-02-15-preview"):
        self.client = AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            api_version=api_version
        )
        self.model = "gpt-4"  # or your deployed model name
        # Initialize schema client for fetching metadata from ingestor
        self.schema_client = IngestorSchemaClient()
    
    def _safe_json_serialize(self, obj: Any) -> str:
        """Safely serialize objects to JSON, handling non-serializable types."""
        def json_serializer(obj):
            """JSON serializer for objects not serializable by default json code"""
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            elif isinstance(obj, Decimal):
                return float(obj)
            elif hasattr(obj, 'isoformat'):
                return obj.isoformat()
            elif hasattr(obj, '__dict__'):
                return str(obj)
            else:
                return str(obj)
        
        try:
            return json.dumps(obj, indent=2, default=json_serializer)
        except Exception as e:
            logger.warning("⚠️ Error serializing object to JSON: %s", e)
            return json.dumps({"error": f"Serialization failed: {str(e)}"}, indent=2)
    
    async def generate_computation(
        self, 
        request: ComputationRequest,
        spark_manager: SparkManager,
        minio_client
    ) -> ComputationSuggestion:
        """Generate a computation based on user prompt and available data context."""
        logger.info("🚀 Starting computation generation for request: user_prompt='%s', context='%s', preferred_dataset='%s'", 
                   request.user_prompt, request.context, request.preferred_dataset)
        
        try:
            # Gather context about available data sources
            logger.info("📊 Building data context...")
            context = self.build_data_context(spark_manager, minio_client)
            logger.info("✅ Data context built successfully. Available sources: %s", list(context.get('available_sources', [])))
            logger.debug("📋 Full data context: %s", context)

            # Create the prompt for Azure OpenAI
            logger.info("📝 Creating prompts for Azure OpenAI...")
            system_prompt = self._create_system_prompt(context)
            user_prompt = self._create_user_prompt(request, context)
            logger.info("✅ Prompts created successfully. System prompt length: %d chars, User prompt length: %d chars", 
                       len(system_prompt), len(user_prompt))
            logger.debug("📄 System prompt: %s", system_prompt[:500] + "..." if len(system_prompt) > 500 else system_prompt)
            logger.debug("📄 User prompt: %s", user_prompt)

            # Make the Azure OpenAI API call
            logger.info("🤖 Calling Azure OpenAI API with model: %s", self.model)
            api_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
                "response_format": {"type": "json_object"}
            }
            logger.debug("🔧 API parameters: %s", {k: v if k != 'messages' else f"[{len(v)} messages]" for k, v in api_params.items()})

            response = self.client.chat.completions.create(**api_params)
            logger.info("✅ Azure OpenAI API call successful")
            
            # Parse the response
            logger.info("📦 Parsing Azure OpenAI response...")
            raw_content = response.choices[0].message.content
            logger.debug("📄 Raw response content: %s", raw_content)
            
            result = json.loads(raw_content)
            logger.info("✅ Response parsed successfully")
            logger.debug("🔍 Raw parsed result: %s", result)
            
            # Clean and normalize the result before creating the Pydantic model
            logger.info("🧹 Normalizing response data...")
            result = self._normalize_openai_response(result)
            logger.info("✅ Response normalized successfully")
            logger.debug("🔍 Normalized result: %s", result)
            
            # Create and return the final suggestion
            logger.info("🎯 Creating ComputationSuggestion object...")
            suggestion = ComputationSuggestion(**result)
            logger.info("✅ Computation generation completed successfully! Title: '%s', Dataset: '%s', Confidence: %.2f", 
                       suggestion.title, suggestion.dataset, suggestion.confidence)
            
            return suggestion
            
        except json.JSONDecodeError as e:
            logger.error("❌ JSON parsing error: %s. Raw content: %s", e, raw_content if 'raw_content' in locals() else 'Not available')
            raise RuntimeError(f"Failed to parse Azure OpenAI response as JSON: {str(e)}")
        except Exception as e:
            logger.error("❌ Error generating computation: %s", e, exc_info=True)
            raise RuntimeError(f"Failed to generate computation: {str(e)}")
    
    def build_data_context(self, spark_manager: SparkManager, minio_client) -> Dict[str, Any]:
        """Build comprehensive context about available data sources and schemas."""
        logger.info("🔧 Building comprehensive data context...")
        
        try:
            # Try to get schema information from ingestor first
            logger.info("📊 Attempting to fetch schema from ingestor...")
            try:
                # Use async context from ingestor
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    context = loop.run_until_complete(self.schema_client.build_data_context())
                    if context.get("sources") and context.get("total_sources", 0) > 0:
                        logger.info("✅ Successfully built context from ingestor: %d sources", context["total_sources"])
                        
                        # Add example computations and syntax guide
                        context["example_computations"] = EXAMPLE_DEFINITIONS[:5]
                        context["computation_syntax"] = self._get_computation_syntax_guide()
                        return context
                finally:
                    loop.close()
            except Exception as e:
                logger.warning("⚠️ Failed to get context from ingestor, falling back to direct detection: %s", e)
            
            # Fallback: Direct detection and schema inference (legacy approach)
            logger.info("🔍 Falling back to direct data source detection...")
            
            # Get available data sources
            logger.info("🔍 Detecting available data sources...")
            sources = self._detect_available_sources(minio_client)
            logger.info("✅ Detected %d data sources: %s", len(sources), sources)
            
            # Get schema information for each source
            logger.info("📊 Retrieving schema information for each source...")
            schemas = {}
            sample_data = {}
            
            for i, source in enumerate(sources, 1):
                logger.info("📋 Processing source %d/%d: '%s'", i, len(sources), source)
                try:
                    # Get schema
                    logger.debug("🔍 Getting schema for source: %s", source)
                    schema_info = self._infer_schemas(spark_manager.session_manager.spark, [source], minio_client)
                    schemas[source] = schema_info.get(source, {})
                    logger.debug("✅ Schema retrieved for '%s': %s", source, schemas[source])
                    
                    # Get sample data (first 3 rows for context)
                    if source in ["bronze", "silver", "enriched", "gold", "alerts"]:
                        logger.debug("🔍 Getting sample data for source: %s", source)
                        sample_df = spark_manager.session_manager.spark.read.parquet(f"s3a://lake/{source}").limit(3)
                        sample_data[source] = [row.asDict() for row in sample_df.collect()]
                        logger.debug("✅ Sample data retrieved for '%s': %d rows", source, len(sample_data[source]))
                    else:
                        logger.debug("⏭️ Skipping sample data for non-standard source: %s", source)
                        
                except Exception as e:
                    logger.warning("⚠️ Could not get schema/sample for source '%s': %s", source, e)
                    schemas[source] = {"error": str(e)}
                    sample_data[source] = []
            
            # Build final context
            logger.info("🏗️ Assembling final data context...")
            context = {
                "available_sources": sources,
                "schemas": schemas,
                "sample_data": sample_data,
                "example_computations": EXAMPLE_DEFINITIONS[:5],  # Include some examples
                "computation_syntax": self._get_computation_syntax_guide()
            }
            
            logger.info("✅ Data context built successfully!")
            logger.info("📊 Context summary: %d sources, %d schemas, %d sample datasets, %d examples", 
                       len(sources), len(schemas), len(sample_data), len(context["example_computations"]))
            
            return context
            
        except Exception as e:
            logger.error("❌ Error building data context: %s", e, exc_info=True)
            # Return minimal context to prevent complete failure
            logger.warning("🔄 Falling back to minimal data context")
            return {
                "available_sources": [],
                "schemas": {},
                "sample_data": {},
                "example_computations": EXAMPLE_DEFINITIONS[:3],
                "computation_syntax": self._get_computation_syntax_guide(),
                "error": str(e)
            }
    
    def _detect_available_sources(self, minio_client) -> List[str]:
        """Detect available data sources in MinIO."""
        logger.debug("🔍 Detecting available data sources from MinIO...")
        
        try:
            sources = []
            # Check for common data lake layers
            logger.debug("📁 Checking for common data lake layers...")
            
            for layer in ["bronze", "silver", "enriched", "gold", "alerts"]:
                try:
                    logger.debug("🔍 Checking for layer: %s", layer)
                    objects = list(minio_client.list_objects("lake", prefix=f"{layer}/", recursive=False))
                    if objects:
                        sources.append(layer)
                        logger.debug("✅ Found layer '%s' with %d objects", layer, len(objects))
                    else:
                        logger.debug("⚪ No objects found for layer: %s", layer)
                except Exception as e:
                    logger.debug("⚠️ Error checking layer '%s': %s", layer, e)
                    pass
                    
            logger.info("✅ Detected %d data sources: %s", len(sources), sources)
            return sources
            
        except Exception as e:
            logger.error("❌ Error detecting sources: %s", e, exc_info=True)
            fallback = ["bronze", "enriched", "gold"]
            logger.warning("🔄 Using fallback sources: %s", fallback)
            return fallback
    
    def _infer_schemas(self, spark, sources: List[str], minio_client) -> Dict[str, Dict]:
        """Infer schemas for available data sources."""
        logger.debug("📊 Inferring schemas for %d sources: %s", len(sources), sources)
        
        schemas = {}
        for i, source in enumerate(sources, 1):
            logger.debug("📋 Processing schema %d/%d for source: '%s'", i, len(sources), source)
            
            try:
                logger.debug("📖 Reading parquet data from: s3a://lake/%s", source)
                df = spark.read.parquet(f"s3a://lake/{source}").limit(1)
                
                logger.debug("🔍 Extracting schema fields for: %s", source)
                schema_dict = {}
                for field in df.schema.fields:
                    schema_dict[field.name] = str(field.dataType)
                    
                logger.debug("🔢 Getting row count for: %s", source)
                row_count = df.count()
                
                schemas[source] = {
                    "columns": schema_dict,
                    "count": row_count
                }
                
                logger.debug("✅ Schema extracted for '%s': %d columns, %d rows", 
                           source, len(schema_dict), row_count)
                
            except Exception as e:
                logger.warning("⚠️ Error inferring schema for source '%s': %s", source, e)
                schemas[source] = {"error": str(e)}
                
        logger.info("✅ Schema inference complete for %d sources", len(sources))
        return schemas
    
    def _get_computation_syntax_guide(self) -> Dict[str, Any]:
        """Provide comprehensive guide to computation syntax."""
        return {
            "supported_operations": [
                "select", "where", "groupBy", "orderBy", "limit"
            ],
            "aggregation_functions": [
                "avg", "sum", "count", "min", "max", "first", "last"
            ],
            "column_access": {
                "sensor_data": "sensor_data.fieldName (for map fields)",
                "normalized_data": "normalized_data.fieldName (for numeric fields)",
                "direct": "columnName (for direct columns)"
            },
            "example_patterns": {
                "filtering": "select * from dataset where sensor_data.temperature > 25",
                "aggregation": "select sensor_data.sensorId, avg(normalized_data.temperature) as avg_temp from dataset groupBy sensor_data.sensorId",
                "time_filtering": "select * from dataset where timestamp > '2025-01-01'",
                "complex": "select sensor_data.sensorId, count(*) as readings, max(normalized_data.temperature) as max_temp from dataset where sensor_data.location = 'downtown' groupBy sensor_data.sensorId orderBy max_temp desc limit 10"
            },
            "common_columns": {
                "bronze": ["ingestion_id", "timestamp", "sensor_data", "normalized_data"],
                "enriched": ["ingestion_id", "timestamp", "sensor_data", "normalized_data"],
                "gold": ["sensorId", "time_start", "avg_temp"],
                "alerts": ["sensorId", "timestamp", "alert_type", "threshold", "value"]
            }
        }
    
    def _create_system_prompt(self, context: Dict[str, Any]) -> str:
        """Create system prompt with data context and syntax guide."""
        logger.debug("📝 Creating system prompt with data context...")
        
        sources_count = len(context.get('available_sources', []))
        schemas_count = len(context.get('schemas', {}))
        examples_count = len(context.get('example_computations', []))
        
        logger.debug("📊 Prompt context: %d sources, %d schemas, %d examples", 
                    sources_count, schemas_count, examples_count)
        
        prompt = f"""You are a helpful AI assistant that generates data computations for a smart city IoT platform.

**Available Data Sources:**
{self._safe_json_serialize(context['available_sources'])}

**Data Schemas:**
{self._safe_json_serialize(context['schemas'])}

**Sample Data (first 3 rows per source):**
{self._safe_json_serialize(context['sample_data'])}

**Computation Syntax Guide:**
{self._safe_json_serialize(context['computation_syntax'])}

**Example Computations:**
{self._safe_json_serialize([{'title': ex['title'], 'dataset': ex['dataset'], 'definition': ex['definition']} for ex in context['example_computations']])}

**Your Task:**
Generate data computations based on user requests. Always return a JSON object with these exact fields:
- title: Descriptive title (string)
- description: Clear explanation of what the computation does (string)  
- dataset: Which data source to use from available sources (string)
- definition: JSON object with computation structure (see examples below)
- confidence: Float between 0-1 indicating how confident you are (number)
- explanation: Step-by-step explanation of the computation logic (string)
- suggested_columns: Array of column names that would be useful to display (array)

**IMPORTANT: The 'definition' field must be a JSON object, not a SQL string. Use this structure:**
{{
  "select": ["column1", "column2", "expression as alias"],
  "where": [{{"col": "column", "op": ">", "value": 25}}],
  "groupBy": ["column1"],
  "orderBy": [{{"col": "column", "dir": "desc"}}],
  "limit": 100
}}

**Guidelines:**
1. Use the actual column names from the provided schemas
2. Follow the exact syntax patterns from examples
3. Prefer enriched data over bronze when possible
4. Use appropriate aggregations and filters
5. Consider the user's intent and suggest practical computations
6. Be conservative with confidence scores
7. Always validate column names exist in the chosen dataset
"""
        
        logger.debug("✅ System prompt created with %d characters", len(prompt))
        return prompt

    def _create_user_prompt(self, request: ComputationRequest, context: Dict[str, Any]) -> str:
        """Create user prompt with specific request and context."""
        logger.debug("📝 Creating user prompt from request...")
        
        prompt = f"User Request: {request.user_prompt}\n\n"
        logger.debug("📄 Base user request: %s", request.user_prompt)
        
        if request.preferred_dataset:
            prompt += f"Preferred Dataset: {request.preferred_dataset}\n"
            logger.debug("🎯 Preferred dataset specified: %s", request.preferred_dataset)
        
        if request.context:
            prompt += f"Additional Context: {request.context}\n"
            logger.debug("📋 Additional context provided: %s", request.context)
        
        prompt += "\nGenerate a computation that fulfills this request using the available data sources and following the syntax guide."
        
        logger.debug("✅ User prompt created with %d characters", len(prompt))
        return prompt

    def _normalize_openai_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize and clean the OpenAI response to ensure it matches our Pydantic model.
        Handles cases where OpenAI returns unexpected data types.
        """
        logger.debug("🔧 Normalizing OpenAI response...")
        logger.debug("📥 Raw response keys: %s", list(result.keys()))
        
        # Normalize explanation - convert list to string if needed
        if isinstance(result.get('explanation'), list):
            logger.debug("🔄 Converting explanation list to string")
            result['explanation'] = ' '.join(str(item) for item in result['explanation'])
        elif not isinstance(result.get('explanation'), str):
            logger.debug("🔄 Converting explanation to string")
            result['explanation'] = str(result.get('explanation', ''))
        
        # Normalize title - ensure it's a string
        if not isinstance(result.get('title'), str):
            logger.debug("🔄 Converting title to string")
            result['title'] = str(result.get('title', 'Untitled Computation'))
        
        # Normalize description - ensure it's a string
        if not isinstance(result.get('description'), str):
            logger.debug("🔄 Converting description to string")
            result['description'] = str(result.get('description', ''))
        
        # Normalize dataset - ensure it's a string
        if not isinstance(result.get('dataset'), str):
            logger.debug("🔄 Converting dataset to string")
            result['dataset'] = str(result.get('dataset', 'unknown'))
        
        # Normalize definition - ensure it's a dict object
        if isinstance(result.get('definition'), str):
            logger.debug("🔄 Parsing definition JSON string to dict")
            try:
                result['definition'] = json.loads(result['definition'])
                logger.debug("✅ Definition parsed successfully")
            except json.JSONDecodeError:
                logger.warning("⚠️ Invalid JSON in definition string, using default structure")
                result['definition'] = {
                    "select": ["*"],
                    "where": [],
                    "limit": 100,
                    "raw_query": result['definition']
                }
        elif isinstance(result.get('definition'), (dict, list)):
            logger.debug("✅ Definition is already a dict/list object")
            # It's already a proper object, no conversion needed
        else:
            logger.warning("⚠️ Invalid definition format, using default structure")
            # Create a default structure if definition is missing or invalid
            result['definition'] = {
                "select": ["*"],
                "where": [],
                "limit": 100
            }
        
        # Normalize confidence - ensure it's a float between 0 and 1
        confidence = result.get('confidence', 0.5)
        try:
            original_confidence = confidence
            confidence = float(confidence)
            if confidence > 1.0:
                logger.debug("🔄 Converting percentage confidence to decimal: %.1f -> %.3f", 
                           original_confidence, confidence / 100.0)
                confidence = confidence / 100.0  # Convert percentage to decimal
            confidence = max(0.0, min(1.0, confidence))  # Clamp between 0 and 1
            logger.debug("✅ Normalized confidence: %.3f", confidence)
        except (ValueError, TypeError):
            logger.warning("⚠️ Invalid confidence value, using default: 0.5")
            confidence = 0.5
        result['confidence'] = confidence
        
        # Normalize suggested_columns - ensure it's a list of strings
        suggested_columns = result.get('suggested_columns', [])
        if not isinstance(suggested_columns, list):
            logger.debug("🔄 Converting suggested_columns to list")
            if isinstance(suggested_columns, str):
                # Try to parse as JSON array first, then split by comma
                try:
                    suggested_columns = json.loads(suggested_columns)
                    logger.debug("✅ Parsed suggested_columns as JSON array")
                except json.JSONDecodeError:
                    logger.debug("🔄 Splitting suggested_columns by comma")
                    suggested_columns = [col.strip() for col in suggested_columns.split(',')]
            else:
                logger.debug("⚠️ Invalid suggested_columns format, using empty list")
                suggested_columns = []
        
        # Ensure all items in suggested_columns are strings
        result['suggested_columns'] = [str(col) for col in suggested_columns if col]
        logger.debug("✅ Normalized suggested_columns: %s", result['suggested_columns'])
        
        logger.info("✅ Response normalization complete")
        return result
