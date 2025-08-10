"""
Spark-related API endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any

from src.api.models import SparkTestResult, ApiResponse
from src.api.dependencies import SparkManagerDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/spark", tags=["spark"])


@router.get("/master-status", response_model=ApiResponse)
async def get_spark_master_status(spark_manager: SparkManagerDep):
    """Get Spark master status including workers and applications."""
    try:
        return spark_manager.get_spark_master_status()
    except Exception as e:
        logger.error(f"Error fetching Spark master status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/average-temperature", response_model=ApiResponse)
async def get_average_temperature(
    spark_manager: SparkManagerDep,
    minutes: int = Query(30, ge=1, le=1440, description="Time window in minutes")
):
    """Get streaming average temperature data for the specified time window."""
    try:
        return spark_manager.get_streaming_average_temperature(minutes)
    except Exception as e:
        logger.error(f"Error fetching average temperature: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/temperature-alerts", response_model=ApiResponse)
async def get_temperature_alerts(
    spark_manager: SparkManagerDep,
    since_minutes: int = Query(60, ge=1, le=1440, description="Time window in minutes")
):
    """Get recent temperature alerts."""
    try:
        return spark_manager.get_temperature_alerts(since_minutes)
    except Exception as e:
        logger.error(f"Error fetching temperature alerts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/enrichment-summary", response_model=ApiResponse)
async def get_enrichment_summary(
    spark_manager: SparkManagerDep,
    minutes: int = Query(10, ge=1, le=1440, description="Lookback window in minutes")
):
    """Summarize enrichment inputs and recent activity (registered devices, recent sensors, matches)."""
    try:
        return spark_manager.get_enrichment_summary(minutes)
    except Exception as e:
        logger.error(f"Error fetching enrichment summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test/computation", response_model=SparkTestResult)
async def test_spark_computation(spark_manager: SparkManagerDep):
    """Test Spark with a basic computation."""
    try:
        return spark_manager.test_spark_basic_computation()
    except Exception as e:
        logger.error(f"Error in Spark computation test: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test/sensor-data", response_model=SparkTestResult)
async def test_sensor_data_access(spark_manager: SparkManagerDep):
    """Test Spark access to sensor data."""
    try:
        return spark_manager.test_sensor_data_access()
    except Exception as e:
        logger.error(f"Error in sensor data access test: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
