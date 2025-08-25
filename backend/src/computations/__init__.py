"""Computation management package.

This package provides a comprehensive computation system for data analysis:

- examples: Static computation examples for user guidance
- validation: Input validation and sanitization utilities  
- sources: Data source detection and schema inference
- executor: Spark-based computation execution engine
- service: Business logic and database operations
- computation_routes: FastAPI route handlers

The package is organized to separate concerns and make the code more maintainable.
"""

from src.computations.examples import EXAMPLE_DEFINITIONS, get_example_by_id, get_dsl_info
from src.computations.service import ComputationService
from src.computations.executor import ComputationExecutor
from src.computations.validation import validate_dataset, validate_username, validate_computation_definition
from src.computations.sources import detect_available_sources, infer_schemas

__all__ = [
    # Examples
    "EXAMPLE_DEFINITIONS",
    "get_example_by_id", 
    "get_dsl_info",
    
    # Core services
    "ComputationService",
    "ComputationExecutor",
    
    # Validation
    "validate_dataset",
    "validate_username", 
    "validate_computation_definition",
    
    # Sources
    "detect_available_sources",
    "infer_schemas",
]
