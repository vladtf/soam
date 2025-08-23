"""
API endpoints for data troubleshooting and diagnostics.
"""
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from ..spark.data_troubleshooter import DataTroubleshooter
from .dependencies import get_spark_manager, get_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/troubleshooting", tags=["troubleshooting"])


class FieldDiagnosticRequest(BaseModel):
    """Request model for field transformation diagnosis."""
    sensor_id: str = Field(..., description="The sensor ID to investigate")
    field_name: str = Field(..., description="The field name to track (e.g., 'temperature')")
    minutes_back: int = Field(default=30, ge=1, le=1440, description="How many minutes back to look")
    ingestion_id: Optional[str] = Field(None, description="Optional ingestion ID filter")


class PipelineTraceRequest(BaseModel):
    """Request model for pipeline tracing."""
    sensor_id: str = Field(..., description="The sensor ID to trace")
    minutes_back: int = Field(default=10, ge=1, le=1440, description="How many minutes back to look")


@router.post("/diagnose-field")
async def diagnose_field_transformation(request: FieldDiagnosticRequest, spark_manager=Depends(get_spark_manager), config=Depends(get_config)):
    """
    Diagnose why a specific field becomes null during data transformation.
    
    This endpoint traces a field through the entire data pipeline:
    1. Raw data ingestion
    2. Normalization
    3. Enrichment
    4. Silver layer aggregation
    
    Returns detailed analysis and recommendations for troubleshooting.
    """
    try:
        troubleshooter = DataTroubleshooter(spark_manager.session_manager, config.minio_bucket)
        
        result = troubleshooter.diagnose_field_transformation(
            sensor_id=request.sensor_id,
            field_name=request.field_name,
            minutes_back=request.minutes_back,
            ingestion_id=request.ingestion_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in field diagnosis: {e}")
        raise HTTPException(status_code=500, detail=f"Diagnosis failed: {str(e)}")


@router.post("/trace-pipeline")
async def trace_data_pipeline(request: PipelineTraceRequest, spark_manager=Depends(get_spark_manager), config=Depends(get_config)):
    """
    Trace how data flows through the transformation pipeline for a specific sensor.
    
    This endpoint provides a complete view of data transformation stages:
    - Raw data samples
    - Enriched data samples  
    - Silver layer aggregations
    
    Useful for understanding data structure changes across pipeline stages.
    """
    try:
        troubleshooter = DataTroubleshooter(spark_manager.session_manager, config.minio_bucket)
        
        result = troubleshooter.get_field_transformation_pipeline(
            sensor_id=request.sensor_id,
            minutes_back=request.minutes_back
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in pipeline trace: {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline trace failed: {str(e)}")


@router.get("/quick-diagnosis")
async def quick_field_diagnosis(
    sensor_id: str = Query(..., description="The sensor ID to investigate"),
    field_name: str = Query(..., description="The field name to track"),
    minutes_back: int = Query(default=30, ge=1, le=1440, description="Minutes back to look"),
    ingestion_id: Optional[str] = Query(None, description="Optional ingestion ID filter"),
    spark_manager=Depends(get_spark_manager),
    config=Depends(get_config)
):
    """
    Quick GET endpoint for field transformation diagnosis.
    
    Same functionality as POST /diagnose-field but as a GET request for easier testing.
    """
    try:
        troubleshooter = DataTroubleshooter(spark_manager.session_manager, config.minio_bucket)
        
        result = troubleshooter.diagnose_field_transformation(
            sensor_id=sensor_id,
            field_name=field_name,
            minutes_back=minutes_back,
            ingestion_id=ingestion_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in quick diagnosis: {e}")
        raise HTTPException(status_code=500, detail=f"Quick diagnosis failed: {str(e)}")


@router.get("/health")
async def troubleshooting_health(spark_manager=Depends(get_spark_manager), config=Depends(get_config)):
    """Health check for troubleshooting endpoints."""
    try:
        # Test Spark connection
        spark = spark_manager.session_manager.spark
        test_df = spark.range(1)
        test_df.count()  # Simple operation to verify Spark is working
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "spark_session": "active",
            "minio_bucket": config.minio_bucket
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


@router.get("/sensor-ids")
async def get_available_sensor_ids(
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of sensor IDs to return"),
    minutes_back: int = Query(default=1440, ge=1, le=10080, description="How many minutes back to look (max 1 week)"),
    spark_manager=Depends(get_spark_manager),
    config=Depends(get_config)
):
    """
    Get a list of available sensor IDs from recent data across all pipeline stages.
    
    This endpoint scans bronze, enriched, and gold data layers to find sensor IDs
    that have been active within the specified time window. Useful for populating
    dropdowns in troubleshooting tools.
    
    Returns sensor IDs found in each pipeline stage plus a combined unique list.
    """
    try:
        troubleshooter = DataTroubleshooter(spark_manager.session_manager, config.minio_bucket)
        
        result = troubleshooter.get_available_sensor_ids(
            limit=limit,
            minutes_back=minutes_back
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting sensor IDs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sensor IDs: {str(e)}")
