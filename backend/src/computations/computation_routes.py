"""Routers for user-defined computations."""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.models import ComputationCreate, ComputationUpdate, ComputationResponse, ApiResponse, ApiListResponse
from src.api.response_utils import success_response, list_response, not_found_error, bad_request_error, internal_server_error
from src.database.database import get_db
from src.api.dependencies import get_spark_manager, ConfigDep, MinioClientDep
from src.spark.spark_manager import SparkManager

# Import refactored modules
from src.computations.examples import EXAMPLE_DEFINITIONS, get_example_by_id, get_dsl_info
from src.computations.sources import detect_available_sources, infer_schemas
from src.computations.service import ComputationService

logger = logging.getLogger(__name__)

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
