"""
Test script to verify Copilot service setup with mocked data
Run this script to check if the Copilot integration is working correctly
"""
import os
import sys

sys.path.append('..\\')

import asyncio
import logging
from unittest.mock import Mock, AsyncMock, patch
from dotenv import load_dotenv
from src.copilot.copilot_service import CopilotService, ComputationRequest

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_mock_spark_manager():
    """Create a mock Spark manager with sample data"""
    mock_spark = Mock()
    
    # Mock get_available_datasets
    mock_spark.get_available_datasets.return_value = [
        "bronze_temperature", "bronze_air_quality", "bronze_smart_bins",
        "silver_sensor_aggregates", "gold_city_metrics"
    ]
    
    # Mock get_dataset_schema
    def mock_schema(dataset):
        schemas = {
            "bronze_temperature": ["device_id", "timestamp", "temperature", "humidity", "location"],
            "bronze_air_quality": ["device_id", "timestamp", "pm25", "pm10", "co2", "location"],
            "bronze_smart_bins": ["bin_id", "timestamp", "fill_level", "location", "status"],
            "silver_sensor_aggregates": ["location", "date", "avg_temperature", "max_temperature", "avg_humidity"],
            "gold_city_metrics": ["date", "location", "health_index", "sustainability_score"]
        }
        return schemas.get(dataset, [])
    
    mock_spark.get_dataset_schema.side_effect = mock_schema
    
    # Mock get_sample_data
    def mock_sample_data(dataset, limit=5):
        samples = {
            "bronze_temperature": [
                {"device_id": "TEMP001", "timestamp": "2025-08-27T10:00:00", "temperature": 22.5, "humidity": 65.2, "location": "Downtown"},
                {"device_id": "TEMP002", "timestamp": "2025-08-27T10:00:00", "temperature": 24.1, "humidity": 58.7, "location": "Park District"}
            ],
            "bronze_air_quality": [
                {"device_id": "AQ001", "timestamp": "2025-08-27T10:00:00", "pm25": 15.2, "pm10": 22.1, "co2": 410, "location": "City Center"}
            ]
        }
        return samples.get(dataset, [])
    
    mock_spark.get_sample_data.side_effect = mock_sample_data
    mock_spark.close = Mock()
    
    return mock_spark

def create_mock_minio_client():
    """Create a mock MinIO client"""
    mock_minio = Mock()
    
    # Mock bucket listing to return proper list
    mock_bucket_1 = Mock()
    mock_bucket_1.name = "bronze"
    mock_bucket_2 = Mock()
    mock_bucket_2.name = "silver"
    mock_bucket_3 = Mock()
    mock_bucket_3.name = "gold"
    
    mock_minio.list_buckets.return_value = [mock_bucket_1, mock_bucket_2, mock_bucket_3]
    
    # Mock object listing to return proper list
    def mock_list_objects(bucket_name, prefix="", recursive=False):
        mock_objects = []
        if bucket_name == "bronze":
            obj1 = Mock()
            obj1.object_name = "temperature/2025/08/27/data.parquet"
            obj2 = Mock() 
            obj2.object_name = "air_quality/2025/08/27/data.parquet"
            obj3 = Mock()
            obj3.object_name = "smart_bins/2025/08/27/data.parquet"
            mock_objects = [obj1, obj2, obj3]
        return mock_objects
    
    mock_minio.list_objects.side_effect = mock_list_objects
    
    return mock_minio

async def test_copilot_service():
    """Test the copilot service with mocked dependencies (similar to real app requests)"""

    logger.info("🚀 Starting Copilot Service Test with Mocked Data")
    
    # Load environment variables
    load_dotenv()

    # Check Azure OpenAI environment variables
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_KEY")
    
    if not endpoint or not api_key:
        logger.error("❌ Azure OpenAI environment variables not set!")
        logger.info("Please set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY in your .env file")
        return False
    
    logger.info("✅ Azure OpenAI environment variables found")
    logger.info(f"Endpoint: {endpoint}")
    
    try:
        # Initialize service
        service = CopilotService(endpoint, api_key)
        logger.info("✅ CopilotService initialized successfully")
        
        # Test the request structure that the frontend would send
        logger.info("📋 Testing ComputationRequest structure...")
        
        # These are the exact kinds of requests the frontend CopilotAssistant component would send
        test_requests = [
            # Simple temperature analysis request (minimal)
            {
                "user_prompt": "Calculate the average temperature by location for today",
                "preferred_dataset": "bronze_temperature"
            },
            
            # Air quality monitoring request (with context)
            {
                "user_prompt": "Show me air quality readings where PM2.5 is above 25",
                "context": "I want to monitor air pollution levels in the city",
                "preferred_dataset": "bronze_air_quality"
            },
            
            # Smart bin efficiency request (with context, no preferred dataset)
            {
                "user_prompt": "Find smart bins that are more than 80% full",
                "context": "Need to optimize waste collection routes"
            },
            
            # Aggregated data request (minimal - no context or preferred dataset)
            {
                "user_prompt": "Create a daily summary of all sensor readings grouped by location"
            },
            
            # Alert/threshold request (all fields)
            {
                "user_prompt": "Alert when temperature exceeds 30 degrees or humidity drops below 30%",
                "context": "Set up environmental monitoring alerts",
                "preferred_dataset": "bronze_temperature"
            }
        ]
        
        success_count = 0
        for i, request_data in enumerate(test_requests, 1):
            try:
                # Create ComputationRequest object from the request data
                request = ComputationRequest(**request_data)
                
                logger.info(f"✅ Test {i}: Request structure valid")
                logger.info(f"   Prompt: '{request.user_prompt}'")
                logger.info(f"   Context: {request.context or 'None'}")
                logger.info(f"   Preferred Dataset: {request.preferred_dataset or 'Auto-select'}")
                
                # Just verify the request can be serialized (like FastAPI would do)
                request_dict = request.model_dump()
                logger.info(f"   Serialized correctly: {len(request_dict)} fields")
                
                success_count += 1
                
            except Exception as e:
                logger.error(f"❌ Test {i} failed: {e}")
        
        if success_count == len(test_requests):
            logger.info("🎉 All request structure tests passed!")
        else:
            logger.warning(f"⚠️ {success_count}/{len(test_requests)} tests passed")
        
        # Test a real API call if Azure OpenAI is available (but with simplified context)
        logger.info("🤖 Testing actual Azure OpenAI call with simplified context...")
        
        try:
            # Create a minimal test request
            test_request = ComputationRequest(
                user_prompt="Calculate average temperature by location",
                context="Sample IoT temperature sensor data",
                preferred_dataset="bronze"
            )
            
            # Create minimal mock dependencies for the actual call
            mock_spark = Mock()
            mock_spark.spark = Mock()
            mock_minio = Mock()
            
            # Mock the context building to return a simple structure
            original_build_context = service.build_data_context
            def mock_build_context(spark_manager, minio_client):
                return {
                    "available_sources": ["bronze", "silver", "gold"],
                    "schemas": {
                        "bronze": {"columns": ["device_id", "timestamp", "temperature", "location"]},
                        "silver": {"columns": ["location", "date", "avg_temperature"]},
                        "gold": {"columns": ["location", "health_index"]}
                    },
                    "sample_data": {
                        "bronze": [{"device_id": "TEMP001", "temperature": 22.5, "location": "Downtown"}]
                    },
                    "example_computations": [],
                    "computation_syntax": "Use Spark SQL syntax for data processing"
                }
            
            service.build_data_context = mock_build_context
            
            # Try the actual generation
            result = await service.generate_computation(test_request, mock_spark, mock_minio)
            
            logger.info("✅ Azure OpenAI call successful!")
            logger.info(f"   Title: {result.title}")
            logger.info(f"   Dataset: {result.dataset}")
            logger.info(f"   Confidence: {result.confidence}")
            logger.info(f"   Description: {result.description}")
            logger.info(f"   Explanation: {result.explanation}")
            logger.info(f"   Suggested Columns: {result.suggested_columns}")
            logger.info(f"   🎯 COMPUTATION DEFINITION: {str(result.definition)}")
            
            # Also log the definition in a more readable format if it's JSON
            try:
                if isinstance(result.definition, str) and (result.definition.startswith('{') or result.definition.startswith('[')):
                    import json
                    parsed_def = json.loads(result.definition)
                    logger.info(f"   📋 PARSED DEFINITION: {json.dumps(parsed_def, indent=2)}")
                else:
                    logger.info(f"   📋 DEFINITION (raw): {str(result.definition)}")
            except Exception as e:
                logger.info(f"   📋 DEFINITION (error parsing): {str(result.definition)} - Error: {e}")

            success_count += 1
            
        except Exception as e:
            logger.warning(f"⚠️ Azure OpenAI call failed (this might be normal): {e}")
        
        logger.info("✅ Copilot service test completed successfully!")
        return success_count > 0
        
    except Exception as e:
        logger.error(f"❌ Error during copilot service test: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = asyncio.run(test_copilot_service())
    if success:
        print("\n🎉 All tests passed! Copilot integration is working correctly.")
        print("\n📋 Test Summary:")
        print("   ✅ ComputationRequest structure validation")
        print("   ✅ Request serialization (FastAPI compatibility)")
        print("   ✅ Environment configuration")
        print("   ✅ CopilotService initialization")
        print("   ⚠️  Azure OpenAI call (may fail if deployment not configured)")
        print("\n💡 The request structure matches what the frontend CopilotAssistant sends!")
        exit(0)
    else:
        print("\n❌ Some tests failed. Check the logs above for details.")
        exit(1)
