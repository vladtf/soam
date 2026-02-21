"""
Utilities for creating consistent API responses across all endpoints.
This module ensures all endpoints follow the same response structure
that matches frontend expectations.
"""
from typing import Any, List, Optional, Tuple
from fastapi import HTTPException, Query, status
from sqlalchemy.orm import Query as SAQuery
from src.api.models import ApiResponse, ApiListResponse

# Default pagination values
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500


def paginate_query(query: SAQuery, page: int, page_size: int) -> Tuple[list, int]:
    """Apply pagination to a SQLAlchemy query.
    
    Returns:
        Tuple of (paginated_rows, total_count)
    """
    total = query.count()
    offset = (page - 1) * page_size
    rows = query.offset(offset).limit(page_size).all()
    return rows, total


def success_response(
    data: Any = None,
    message: Optional[str] = None,
    status_text: str = "success"
) -> ApiResponse:
    """Create a successful API response."""
    return ApiResponse(
        status=status_text,
        data=data,
        message=message
    )


def error_response(
    message: str,
    detail: Optional[str] = None,
    status_code: int = 400,
    status_text: str = "error"
) -> HTTPException:
    """Create an error API response and return HTTPException with proper status code."""
    error_detail = detail or message
    return HTTPException(
        status_code=status_code,
        detail=error_detail
    )


def not_found_error(message: str = "Resource not found", detail: Optional[str] = None) -> HTTPException:
    """Return a 404 Not Found error."""
    return error_response(message, detail, status_code=404)


def bad_request_error(message: str, detail: Optional[str] = None) -> HTTPException:
    """Return a 400 Bad Request error."""
    return error_response(message, detail, status_code=400)


def forbidden_error(message: str = "Permission denied", detail: Optional[str] = None) -> HTTPException:
    """Return a 403 Forbidden error."""
    return error_response(message, detail, status_code=403)


def internal_server_error(message: str = "Internal server error", detail: Optional[str] = None) -> HTTPException:
    """Return a 500 Internal Server Error."""
    return error_response(message, detail, status_code=500)


def conflict_error(message: str, detail: Optional[str] = None) -> HTTPException:
    """Return a 409 Conflict error."""
    return error_response(message, detail, status_code=409)


def list_response(
    data: List[Any],
    total: Optional[int] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    message: Optional[str] = None,
    status_text: str = "success"
) -> ApiListResponse:
    """Create a list API response."""
    return ApiListResponse(
        status=status_text,
        data=data,
        total=total or len(data),
        page=page,
        page_size=page_size,
        message=message
    )


def handle_http_exception(e: HTTPException) -> ApiResponse:
    """Convert HTTPException to consistent API response."""
    status_text = "error"
    if e.status_code == status.HTTP_404_NOT_FOUND:
        status_text = "error"
    elif e.status_code == status.HTTP_400_BAD_REQUEST:
        status_text = "error"
    elif e.status_code >= 500:
        status_text = "error"
    
    return ApiResponse(
        status=status_text,
        message=e.detail,
        detail=f"HTTP {e.status_code}: {e.detail}"
    )


def handle_generic_exception(e: Exception, context: str = "") -> ApiResponse:
    """Convert generic exception to consistent API response."""
    message = f"Internal server error"
    if context:
        message = f"{context}: {message}"
    
    return ApiResponse(
        status="error",
        message=message,
        detail=str(e)
    )
