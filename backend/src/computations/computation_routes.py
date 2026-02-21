"""Routers for user-defined computations."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.models import ComputationCreate, ComputationUpdate, ComputationResponse, ApiResponse, ApiListResponse
from src.api.response_utils import success_response, list_response, not_found_error, bad_request_error, internal_server_error
from src.database.database import get_db
from src.database.models import Device
from src.api.dependencies import get_spark_manager, ConfigDep, MinioClientDep
from src.spark.spark_manager import SparkManager

# Import refactored modules
from src.computations.examples import EXAMPLE_DEFINITIONS, get_example_by_id, get_dsl_info
from src.computations.sources import detect_available_sources, infer_schemas
from src.computations.service import ComputationService
from src.computations.sensitivity import calculate_computation_sensitivity, SENSITIVITY_ORDER
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["computations"])

# Thread pool for running Spark computations asynchronously
# This prevents blocking the FastAPI event loop during expensive Spark operations
_computation_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="computation-api")


@router.get("/computations/examples", response_model=ApiResponse)
def get_examples(config: ConfigDep, client: MinioClientDep):
    """Return suggested examples and available sources (datasets) discovered from MinIO."""
    sources = detect_available_sources(config, client)
    data = {
        "sources": sources,
        "examples": EXAMPLE_DEFINITIONS,
        "dsl": get_dsl_info()
    }
    return success_response(data, "Examples retrieved successfully")


@router.get("/computations/sources", response_model=ApiResponse)
def get_sources(config: ConfigDep, client: MinioClientDep):
    """Get available data sources."""
    sources = detect_available_sources(config, client)
    return success_response({"sources": sources}, "Sources retrieved successfully")


@router.post("/computations/analyze-sensitivity", response_model=ApiResponse)
def analyze_computation_sensitivity(payload: dict, db: Session = Depends(get_db)):
    """
    Analyze the sensitivity of a computation definition before creation.
    
    This helps users understand what sensitivity level their computation will inherit
    based on the devices referenced in their definition.
    
    Payload:
        definition: The computation DSL definition (select, where, orderBy, etc.)
    """
    definition = payload.get("definition", {})
    
    # Calculate sensitivity
    sensitivity, source_devices = calculate_computation_sensitivity(db, definition)
    
    # Get device details for each source
    device_details = []
    if source_devices:
        devices = db.query(Device).filter(Device.ingestion_id.in_(source_devices)).all()
        for device in devices:
            device_details.append({
                "ingestion_id": device.ingestion_id,
                "name": device.name,
                "sensitivity": device.sensitivity.value if device.sensitivity else "public",
            })
    
    # Generate warning message if sensitivity is elevated
    warning = None
    if sensitivity.value in ["confidential", "restricted"]:
        warning = (
            f"⚠️ This computation will have {sensitivity.value.upper()} sensitivity "
            f"because it references devices with that sensitivity level. "
            f"Only users with appropriate roles will be able to view tiles using this computation."
        )
    
    return success_response({
        "sensitivity": sensitivity.value,
        "source_devices": device_details,
        "warning": warning,
        "sensitivity_levels": [s.value for s in SENSITIVITY_ORDER],
    }, "Sensitivity analysis completed")


@router.post("/computations/examples/{example_id}/preview", response_model=ApiResponse)
async def preview_example_computation(example_id: str, spark: SparkManager = Depends(get_spark_manager)):
    """Preview an example computation by ID."""
    example = get_example_by_id(example_id)
    if not example:
        raise not_found_error("Example computation not found")
    
    def _execute_preview():
        """Execute preview computation in thread pool."""
        service = ComputationService(db=None, spark_manager=spark)
        result = service.preview_example(example_id, example)
        return {
            "example": example,
            "result": result,
            "row_count": len(result)
        }
    
    try:
        # Run Spark computation in thread pool to prevent blocking FastAPI event loop
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(_computation_executor, _execute_preview)
        return success_response(
            data, 
            f"Example computation '{example['title']}' executed successfully"
        )
    except HTTPException:
        # Let FastAPI handle HTTPExceptions directly
        raise
    except Exception as e:
        logger.exception(f"Example computation preview failed for {example_id}")
        raise bad_request_error(str(e))


@router.get("/computations/schemas", response_model=ApiResponse)
async def get_schemas(config: ConfigDep, client: MinioClientDep, spark: SparkManager = Depends(get_spark_manager)):
    """Return detected sources plus inferred column schemas for each source using Spark."""
    def _get_schemas():
        """Get schemas in thread pool."""
        sources = detect_available_sources(config, client)
        schemas = infer_schemas(sources, spark)
        return {"sources": sources, "schemas": schemas}
    
    try:
        # Run Spark operation in thread pool to prevent blocking FastAPI event loop
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(_computation_executor, _get_schemas)
        return success_response(data, "Schemas retrieved successfully")
    except Exception as e:
        logger.exception("Schema inference failed")
        raise internal_server_error("Failed to retrieve schemas", str(e))


@router.get("/computations", response_model=ApiListResponse[ComputationResponse])
def list_computations(db: Session = Depends(get_db)):
    """List all computations."""
    try:
        service = ComputationService(db)
        computations = service.list_computations()
        return list_response(computations, message="Computations retrieved successfully")
    except Exception as e:
        logger.error("Error listing computations: %s", e)
        raise internal_server_error("Failed to retrieve computations", str(e))


@router.post("/computations", response_model=ApiResponse[ComputationResponse])
def create_computation(payload: ComputationCreate, db: Session = Depends(get_db)):
    """Create a new computation."""
    try:
        service = ComputationService(db)
        computation = service.create_computation(payload)
        return success_response(computation, "Computation created successfully")
    except HTTPException:
        # Let FastAPI handle HTTPExceptions (like 409 conflicts) directly
        raise
    except ValueError as e:
        raise bad_request_error(str(e))
    except Exception as e:
        logger.error("Error creating computation: %s", e)
        raise internal_server_error("Failed to create computation", str(e))


@router.patch("/computations/{comp_id}", response_model=ApiResponse[ComputationResponse])
def update_computation(comp_id: int, payload: ComputationUpdate, db: Session = Depends(get_db)):
    """Update an existing computation."""
    try:
        service = ComputationService(db)
        computation = service.update_computation(comp_id, payload)
        return success_response(computation, "Computation updated successfully")
    except HTTPException:
        # Let FastAPI handle HTTPExceptions (like 404, 409) directly
        raise
    except ValueError as e:
        raise bad_request_error(str(e))
    except Exception as e:
        logger.error("Error updating computation: %s", e)
        raise internal_server_error("Failed to update computation", str(e))


@router.delete("/computations/{comp_id}", response_model=ApiResponse)
def delete_computation(comp_id: int, db: Session = Depends(get_db)):
    """Delete a computation."""
    try:
        service = ComputationService(db)
        service.delete_computation(comp_id)
        return success_response(message="Computation deleted successfully")
    except HTTPException:
        # Let FastAPI handle HTTPExceptions (like 404) directly
        raise
    except Exception as e:
        logger.error("Error deleting computation: %s", e)
        raise internal_server_error("Failed to delete computation", str(e))


@router.get("/computations/{comp_id}/dependencies", response_model=ApiResponse)
def check_computation_dependencies(comp_id: int, db: Session = Depends(get_db)):
    """Check if computation has dependent dashboard tiles before deletion."""
    try:
        service = ComputationService(db)
        dependencies = service.check_computation_dependencies(comp_id)
        return success_response(dependencies, "Dependencies checked successfully")
    except HTTPException:
        # Let FastAPI handle HTTPExceptions (like 404) directly
        raise
    except Exception as e:
        logger.error("Error checking computation dependencies: %s", e)
        raise internal_server_error("Failed to check dependencies", str(e))


@router.post("/computations/{comp_id}/preview", response_model=ApiResponse)
async def preview_computation(comp_id: int, db: Session = Depends(get_db), spark: SparkManager = Depends(get_spark_manager)):
    """Preview a computation's results."""
    def _execute_computation_preview():
        """Execute computation preview in thread pool."""
        service = ComputationService(db, spark)
        return service.preview_computation(comp_id)
    
    try:
        # Run Spark computation in thread pool to prevent blocking FastAPI event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_computation_executor, _execute_computation_preview)
        return success_response(result, "Computation preview executed successfully")
    except HTTPException:
        # Let FastAPI handle HTTPExceptions directly
        raise
    except ValueError as e:
        raise bad_request_error(str(e))
    except Exception as e:
        logger.exception("Computation preview failed")
        raise bad_request_error(str(e))
