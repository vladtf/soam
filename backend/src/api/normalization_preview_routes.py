"""
API routes for data normalization preview functionality.
Provides endpoints to preview normalization results before applying them.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from src.database.database import get_db
from src.services.normalization_preview import DataNormalizationPreview
from src.minio.minio_browser import MinioBrowser
from src.api.dependencies import MinioClientDep, ConfigDep, AppConfig
from src.api.models import ApiResponse
from src.api.response_utils import success_response, internal_server_error
from minio import Minio
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/normalization/preview", tags=["normalization-preview"])


def _rules_to_dicts(rules: list) -> list[dict]:
    """Convert CustomNormalizationRule list to dictionary format."""
    return [
        {"raw_key": rule.raw_key, "canonical_key": rule.canonical_key, "ingestion_id": rule.ingestion_id}
        for rule in rules
    ]


class CustomNormalizationRule(BaseModel):
    """Schema for custom normalization rule."""
    raw_key: str = Field(..., description="Raw column name to normalize")
    canonical_key: str = Field(..., description="Target canonical column name")
    ingestion_id: Optional[str] = Field(None, description="Optional ingestion ID filter")


class NormalizationPreviewRequest(BaseModel):
    """Schema for normalization preview request."""
    ingestion_id: Optional[str] = Field(None, description="Optional ingestion ID to filter data")
    custom_rules: Optional[List[CustomNormalizationRule]] = Field(None, description="Custom rules to test")
    sample_limit: int = Field(100, ge=1, le=1000, description="Maximum sample records to analyze")


class NormalizationComparisonRequest(BaseModel):
    """Schema for comparing normalization scenarios."""
    ingestion_id: Optional[str] = Field(None, description="Optional ingestion ID context")
    scenario_a_rules: List[CustomNormalizationRule] = Field(..., description="First scenario rules")
    scenario_b_rules: List[CustomNormalizationRule] = Field(..., description="Second scenario rules")
    sample_limit: int = Field(100, ge=1, le=1000, description="Maximum sample records to analyze")


class RuleValidationRequest(BaseModel):
    """Schema for rule validation request."""
    rules: List[CustomNormalizationRule] = Field(..., description="Rules to validate")
    ingestion_id: Optional[str] = Field(None, description="Optional ingestion ID for context")
    sample_limit: int = Field(100, ge=1, le=1000, description="Maximum sample records to analyze")


def get_preview_service(
    minio_client: MinioClientDep,
    config: ConfigDep
) -> DataNormalizationPreview:
    minio_browser = MinioBrowser(client=minio_client, bucket=config.minio_bucket)
    return DataNormalizationPreview(minio_browser)


@router.get("/sample-data", response_model=ApiResponse)
async def get_sample_data(
    ingestion_id: Optional[str] = Query(None, description="Filter by ingestion ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    preview_service: DataNormalizationPreview = Depends(get_preview_service)
):
    """
    Get sample raw data for normalization preview.
    
    This endpoint retrieves recent raw data that can be used to preview
    how normalization rules will transform the data.
    """
    try:
        sample_df = preview_service.get_sample_data(ingestion_id=ingestion_id, limit=limit)
        
        if sample_df.empty:
            return success_response(
                data={
                    "data": [],
                    "columns": [],
                    "total_records": 0,
                    "sample_ingestion_ids": []
                },
                message="No sample data available",
                status_text="warning"
            )
        
        sample_data = {
            "data": sample_df.head(50).to_dict('records'),  # Return first 50 for display
            "columns": list(sample_df.columns),
            "total_records": len(sample_df),
            "sample_ingestion_ids": (
                sample_df['_ingestion_id'].dropna().unique().tolist() 
                if '_ingestion_id' in sample_df.columns else []
            )
        }
        
        return success_response(
            data=sample_data,
            message="Sample data retrieved successfully"
        )
        
    except Exception as e:
        logger.error("❌ Error getting sample data: %s", e)
        raise internal_server_error("Failed to retrieve sample data", str(e))


@router.post("/preview", response_model=ApiResponse)
async def preview_normalization(
    request: NormalizationPreviewRequest,
    db: Session = Depends(get_db),
    preview_service: DataNormalizationPreview = Depends(get_preview_service)
):
    """
    Preview how normalization rules will transform sample data.
    
    This endpoint applies existing normalization rules (and optionally custom rules)
    to sample data and returns both the original and transformed data for comparison.
    """
    try:
        # Get sample data
        sample_df = preview_service.get_sample_data(
            ingestion_id=request.ingestion_id, 
            limit=request.sample_limit
        )
        
        if sample_df.empty:
            return success_response(
                data={
                    "original_data": [],
                    "normalized_data": [],
                    "applied_rules": [],
                    "unmapped_columns": []
                },
                message="No sample data available for preview",
                status_text="warning"
            )
        
        # Convert custom rules to dictionary format
        custom_rules_dict = _rules_to_dicts(request.custom_rules) if request.custom_rules else None
        
        # Preview normalization
        preview_result = preview_service.preview_normalization(
            db=db,
            sample_data=sample_df,
            ingestion_id=request.ingestion_id,
            custom_rules=custom_rules_dict
        )
        
        return success_response(
            data={"preview": preview_result},
            message="Normalization preview generated successfully"
        )
        
    except Exception as e:
        logger.error("❌ Error previewing normalization: %s", e)
        raise internal_server_error("Failed to preview normalization", str(e))


@router.post("/compare", response_model=ApiResponse)
async def compare_normalization_scenarios(
    request: NormalizationComparisonRequest,
    db: Session = Depends(get_db),
    preview_service: DataNormalizationPreview = Depends(get_preview_service)
):
    """
    Compare two different normalization scenarios side by side.
    
    This endpoint allows you to compare how two different sets of normalization
    rules will transform the same sample data.
    """
    try:
        # Get sample data
        sample_df = preview_service.get_sample_data(
            ingestion_id=request.ingestion_id,
            limit=request.sample_limit
        )
        
        if sample_df.empty:
            return success_response(
                data={},
                message="No sample data available for comparison",
                status_text="warning"
            )
        
        # Convert rules to dictionary format
        scenario_a_rules = _rules_to_dicts(request.scenario_a_rules)
        
        scenario_b_rules = _rules_to_dicts(request.scenario_b_rules)
        
        # Compare scenarios
        comparison_result = preview_service.compare_normalization_scenarios(
            db=db,
            sample_data=sample_df,
            scenario_a_rules=scenario_a_rules,
            scenario_b_rules=scenario_b_rules,
            ingestion_id=request.ingestion_id
        )
        
        return success_response(
            data=comparison_result,
            message="Normalization scenarios compared successfully"
        )
        
    except Exception as e:
        logger.error("❌ Error comparing normalization scenarios: %s", e)
        raise internal_server_error("Failed to compare normalization scenarios", str(e))


@router.post("/validate", response_model=ApiResponse)
async def validate_normalization_rules(
    request: RuleValidationRequest,
    preview_service: DataNormalizationPreview = Depends(get_preview_service)
):
    """
    Validate normalization rules against sample data.
    
    This endpoint checks if the provided normalization rules are valid
    and can be applied to the available sample data.
    """
    try:
        # Get sample data for validation
        sample_df = preview_service.get_sample_data(
            ingestion_id=request.ingestion_id,
            limit=request.sample_limit
        )
        
        if sample_df.empty:
            return success_response(
                data={
                    "overall_valid": False,
                    "total_rules": len(request.rules),
                    "valid_rules": 0,
                    "invalid_rules": len(request.rules)
                },
                message="No sample data available for validation",
                status_text="warning"
            )
        
        # Convert rules to dictionary format
        rules_dict = _rules_to_dicts(request.rules)
        
        # Validate rules
        validation_result = preview_service.validate_normalization_rules(
            rules=rules_dict,
            sample_data=sample_df
        )
        
        return success_response(
            data=validation_result,
            message="Rules validated successfully"
        )
        
    except Exception as e:
        logger.error("❌ Error validating normalization rules: %s", e)
        raise internal_server_error("Failed to validate normalization rules", str(e))


@router.get("/ingestion-ids", response_model=ApiResponse)
async def get_available_ingestion_ids(
    preview_service: DataNormalizationPreview = Depends(get_preview_service)
):
    """
    Get list of available ingestion IDs from recent raw data.
    
    This endpoint helps users understand what ingestion IDs are available
    for filtering during normalization preview.
    """
    try:
        sample_df = preview_service.get_sample_data(limit=1000)
        
        if sample_df.empty or '_ingestion_id' not in sample_df.columns:
            return success_response(
                data=[],
                message="No ingestion IDs found in sample data",
                status_text="warning"
            )
        
        ingestion_ids = sample_df['_ingestion_id'].dropna().unique().tolist()
        
        return success_response(
            data={
                "ingestion_ids": sorted(ingestion_ids),
                "total_count": len(ingestion_ids)
            },
            message="Ingestion IDs retrieved successfully"
        )
        
    except Exception as e:
        logger.error("❌ Error getting available ingestion IDs: %s", e)
        raise internal_server_error("Failed to get ingestion IDs", str(e))
