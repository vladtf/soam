"""
API routes for Copilot-powered computation generation.
"""
from fastapi import APIRouter, Depends, HTTPException
from src.api.models import ApiResponse
from src.api.response_utils import success_response, internal_server_error
from src.api.dependencies import get_spark_manager, get_minio_client, ConfigDep, MinioClientDep
from src.copilot.copilot_service import CopilotService, ComputationRequest
from src.computations.validation import validate_computation_definition
from src.spark.spark_manager import SparkManager
from minio import Minio
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["copilot"])

@router.post("/copilot/generate-computation", response_model=ApiResponse)
async def generate_computation(
    request: ComputationRequest,
    spark_manager: SparkManager = Depends(get_spark_manager),
    minio_client: Minio = Depends(get_minio_client)
) -> ApiResponse:
    """Generate a computation using Azure OpenAI Copilot."""
    try:
        # Get copilot service instance
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_KEY")
        
        if not azure_endpoint or not api_key:
            raise HTTPException(status_code=503, detail="Azure OpenAI not configured")

        logger.info("Using Azure OpenAI endpoint: %s", azure_endpoint)

        copilot_service = CopilotService(azure_endpoint, api_key)

        logger.info("Processing generate computation request: %s", request)

        # Generate computation
        suggestion = await copilot_service.generate_computation(
            request, spark_manager, minio_client
        )
        
        # Validate the generated computation
        validation_result = validate_computation_definition(suggestion.definition)
        
        if not validation_result.get("valid", False):
            # Lower confidence if validation issues found
            suggestion.confidence *= 0.7
            suggestion.explanation += f"\n\nValidation Notes: {validation_result.get('message', '')}"
        
        return success_response(
            data=suggestion.dict(),
            message="Computation generated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating computation: {e}")
        return internal_server_error("Failed to generate computation", str(e))

@router.get("/copilot/context", response_model=ApiResponse)
async def get_copilot_context(
    spark_manager: SparkManager = Depends(get_spark_manager),
    minio_client: Minio = Depends(get_minio_client)
):
    """Get current data context for copilot suggestions."""
    try:
        # Get copilot service instance
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_KEY")
        
        if not azure_endpoint or not api_key:
            raise HTTPException(status_code=503, detail="Azure OpenAI not configured")

        logger.info("Using Azure OpenAI endpoint: %s", azure_endpoint)

        copilot_service = CopilotService(azure_endpoint, api_key)
        
        context = copilot_service.build_data_context(spark_manager, minio_client)
        return success_response(
            data=context,
            message="Context retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error retrieving context: {e}")
        return internal_server_error("Failed to retrieve context", str(e))

@router.get("/copilot/health", response_model=ApiResponse)
async def copilot_health():
    """Check if Copilot service is available."""
    try:
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_KEY")
        
        if not azure_endpoint or not api_key:
            return success_response(
                data={"available": False, "reason": "Azure OpenAI not configured"},
                message="Copilot service not available"
            )
        
        return success_response(
            data={"available": True, "endpoint": azure_endpoint},
            message="Copilot service available"
        )
    except Exception as e:
        return internal_server_error("Failed to check copilot health", str(e))
