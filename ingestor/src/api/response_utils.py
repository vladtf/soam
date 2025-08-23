"""
Response utility functions for the SOAM ingestor API.
Provides consistent response formatting across all endpoints.
"""
from typing import Any, Optional, List
from .models import ApiResponse, ApiListResponse


def success_response(data: Any = None, message: Optional[str] = None) -> ApiResponse:
    """
    Create a successful API response.
    
    Args:
        data: Response data
        message: Optional success message
        
    Returns:
        ApiResponse with success status
    """
    return ApiResponse(
        status="success",
        data=data,
        message=message
    )


def error_response(message: str, data: Any = None) -> ApiResponse:
    """
    Create an error API response.
    
    Args:
        message: Error message
        data: Optional error data
        
    Returns:
        ApiResponse with error status
    """
    return ApiResponse(
        status="error",
        error=message,
        data=data
    )


def list_response(data: List[Any], message: Optional[str] = None, total: Optional[int] = None) -> ApiListResponse:
    """
    Create a list API response.
    
    Args:
        data: List of data items
        message: Optional message
        total: Total count (defaults to len(data))
        
    Returns:
        ApiListResponse with the data
    """
    return ApiListResponse(
        status="success",
        data=data,
        total=total if total is not None else len(data),
        message=message
    )
