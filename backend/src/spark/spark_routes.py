"""
Spark-related API endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException, Query

from src.api.models import SparkTestResult, ApiResponse
from src.api.response_utils import success_response, not_found_error, bad_request_error, internal_server_error
from src.api.dependencies import SparkManagerDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/spark", tags=["spark"])


@router.get("/master-status", response_model=ApiResponse)
async def get_spark_master_status(spark_manager: SparkManagerDep):
    """Get Spark master status including workers and applications."""
    try:
        status = spark_manager.get_spark_master_status()
        return success_response(status, "Spark master status retrieved successfully")
    except Exception as e:
        logger.error(f"Error fetching Spark master status: {str(e)}")
        raise internal_server_error("Failed to fetch Spark master status", str(e))


@router.get("/streams-status", response_model=ApiResponse)
async def get_running_streams_status(spark_manager: SparkManagerDep):
    """Get status information about all running Spark streaming queries."""
    try:
        streams_status = spark_manager.get_running_streams_status()
        return success_response(streams_status, "Running streams status retrieved successfully")
    except Exception as e:
        logger.error(f"Error fetching running streams status: {str(e)}")
        raise internal_server_error("Failed to fetch running streams status", str(e))


@router.get("/average-temperature", response_model=ApiResponse)
async def get_average_temperature(
    spark_manager: SparkManagerDep,
    minutes: int = Query(30, ge=1, le=1440, description="Time window in minutes")
):
    """Get streaming average temperature data for the specified time window."""
    try:
        data = spark_manager.get_streaming_average_temperature(minutes)
        return success_response(data, "Average temperature data retrieved successfully")
    except Exception as e:
        logger.error(f"Error fetching average temperature: {str(e)}")
        raise internal_server_error("Failed to fetch average temperature", str(e))


@router.get("/temperature-alerts", response_model=ApiResponse)
async def get_temperature_alerts(
    spark_manager: SparkManagerDep,
    since_minutes: int = Query(60, ge=1, le=1440, description="Time window in minutes")
):
    """Get recent temperature alerts."""
    try:
        alerts = spark_manager.get_temperature_alerts(since_minutes)
        return success_response(alerts, "Temperature alerts retrieved successfully")
    except Exception as e:
        logger.error(f"Error fetching temperature alerts: {str(e)}")
        raise internal_server_error("Failed to fetch temperature alerts", str(e))


@router.get("/enrichment-summary", response_model=ApiResponse)
async def get_enrichment_summary(
    spark_manager: SparkManagerDep,
    minutes: int = Query(10, ge=1, le=1440, description="Lookback window in minutes")
):
    """Summarize enrichment inputs and recent activity (registered devices, recent sensors, matches)."""
    try:
        summary = spark_manager.get_enrichment_summary(minutes)
        return success_response(summary, "Enrichment summary retrieved successfully")
    except Exception as e:
        logger.error(f"Error fetching enrichment summary: {str(e)}")
        raise internal_server_error("Failed to fetch enrichment summary", str(e))


@router.get("/test/computation", response_model=SparkTestResult)
async def test_spark_computation(spark_manager: SparkManagerDep):
    """Test Spark with a basic computation."""
    try:
        result = spark_manager.test_spark_basic_computation()
        return success_response(result, "Spark computation test completed successfully")
    except Exception as e:
        logger.error(f"Error in Spark computation test: {str(e)}")
        raise internal_server_error("Spark computation test failed", str(e))


@router.get("/test/sensor-data", response_model=SparkTestResult)
async def test_sensor_data_access(spark_manager: SparkManagerDep):
    """Test Spark access to sensor data."""
    try:
        result = spark_manager.test_sensor_data_access()
        return success_response(result, "Sensor data access test completed successfully")
    except Exception as e:
        logger.error(f"Error in sensor data access test: {str(e)}")
        raise internal_server_error("Sensor data access test failed", str(e))


@router.get("/diagnose/enrichment-filtering", response_model=ApiResponse)
async def diagnose_enrichment_filtering(spark_manager: SparkManagerDep):
    """Diagnose enrichment filtering issues - why certain sensors are being processed."""
    try:
        from .diagnostics_enhanced import diagnose_enrichment_filtering
        from .config import SparkConfig
        
        # Get the enriched path from spark manager or config
        enriched_path = f"s3a://{spark_manager.data_access.minio_bucket}/{SparkConfig.ENRICHED_PATH}"
        
        diagnosis = diagnose_enrichment_filtering(
            spark_manager.session_manager, 
            enriched_path
        )
        return success_response(
            diagnosis,
            "Enrichment filtering diagnosis completed"
        )
    except Exception as e:
        logger.error(f"Error in enrichment filtering diagnosis: {str(e)}")
        raise internal_server_error("Enrichment filtering diagnosis failed", str(e))
