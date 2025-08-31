"""
Comprehensive API utilities to reduce code duplication in API route handlers.
Consolidates api_decorators.py functionality to eliminate duplication.
"""
import logging
import functools
import asyncio
from typing import Any, Callable, Optional, Dict
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from src.api.response_utils import success_response, internal_server_error
from src.api.models import ApiResponse
from src.utils.logging import get_logger
from src.utils.database_utils import DatabaseError
from src.utils.validation import validate_required_fields

logger = get_logger(__name__)


def handle_api_errors(operation_name: str, success_message: Optional[str] = None):
    """
    Unified decorator for async API error handling with standardized responses.
    
    Args:
        operation_name: Description of the operation for logging
        success_message: Optional custom success message
        
    Usage:
        @handle_api_errors("get user data")
        async def get_user(user_id: int):
            return {"user": user_data}
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> ApiResponse:
            try:
                # Execute the decorated function
                result = await func(*args, **kwargs)
                
                # If the function already returns an ApiResponse, return it directly
                if isinstance(result, ApiResponse):
                    return result
                
                # Otherwise, wrap the result in a success response
                message = success_message or f"{operation_name.capitalize()} completed successfully"
                _log_api_success(operation_name)
                return success_response(data=result, message=message)
                
            except HTTPException:
                # Re-raise HTTPExceptions (like 404, 400, etc.) without modification
                raise
            except DatabaseError as e:
                _log_api_error(operation_name, e)
                return internal_server_error(f"Failed to {operation_name}: Database error")
            except SQLAlchemyError as e:
                _log_api_error(operation_name, e)
                return internal_server_error(f"Failed to {operation_name}: Database error")
            except Exception as e:
                # Log and handle unexpected errors
                _log_api_error(operation_name, e)
                return internal_server_error(f"Failed to {operation_name}: {str(e)}")
        
        return wrapper
    return decorator


def handle_api_errors_sync(operation_name: str, success_message: Optional[str] = None):
    """
    Unified decorator for synchronous API error handling with standardized responses.
    
    Args:
        operation_name: Description of the operation for logging
        success_message: Optional custom success message
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> ApiResponse:
            try:
                result = func(*args, **kwargs)
                
                if isinstance(result, ApiResponse):
                    return result
                
                message = success_message or f"{operation_name.capitalize()} completed successfully"
                _log_api_success(operation_name)
                return success_response(data=result, message=message)
                
            except HTTPException:
                raise
            except DatabaseError as e:
                _log_api_error(operation_name, e)
                return internal_server_error(f"Failed to {operation_name}: Database error")
            except SQLAlchemyError as e:
                _log_api_error(operation_name, e)
                return internal_server_error(f"Failed to {operation_name}: Database error")
            except Exception as e:
                _log_api_error(operation_name, e)
                return internal_server_error(f"Failed to {operation_name}: {str(e)}")
        
        return wrapper
    return decorator


def api_endpoint(success_message: Optional[str] = None, error_message: Optional[str] = None):
    """
    Advanced decorator for API endpoints with auto async/sync detection.
    
    Args:
        success_message: Custom success message
        error_message: Custom error message prefix
        
    Usage:
        @api_endpoint(success_message="Data retrieved", error_message="Failed to get data")
        async def get_data():
            return {"data": "value"}
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> ApiResponse:
            try:
                # Call the original function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # If result is already an ApiResponse, return it
                if isinstance(result, ApiResponse):
                    return result
                
                # Wrap result in success response
                message = success_message or "Operation completed successfully"
                return success_response(data=result, message=message)
                
            except DatabaseError as e:
                logger.error(f"Database error in {func.__name__}: {e}")
                error_msg = error_message or "Database operation failed"
                return internal_server_error(error_msg, str(e))
            except SQLAlchemyError as e:
                logger.error(f"SQLAlchemy error in {func.__name__}: {e}")
                error_msg = error_message or "Database error occurred"
                return internal_server_error(error_msg, str(e))
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
                error_msg = error_message or "Internal server error"
                return internal_server_error(error_msg, str(e))
        
        # Return sync wrapper for sync functions
        if not asyncio.iscoroutinefunction(func):
            def sync_wrapper(*args, **kwargs) -> ApiResponse:
                # Create event loop for async wrapper if needed
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If we're in an async context, we need to handle this differently
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(lambda: asyncio.run(async_wrapper(*args, **kwargs)))
                            return future.result()
                    else:
                        return loop.run_until_complete(async_wrapper(*args, **kwargs))
                except RuntimeError:
                    # No event loop, run in new one
                    return asyncio.run(async_wrapper(*args, **kwargs))
            return sync_wrapper
        
        return async_wrapper
    return decorator


def validate_request_data(required_fields: Optional[list] = None, optional_fields: Optional[list] = None):
    """
    Enhanced decorator to validate request data using centralized validation.
    
    Args:
        required_fields: List of required field names
        optional_fields: List of optional field names
        
    Usage:
        @validate_request_data(required_fields=['name', 'email'])
        def create_user(user_data: dict):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Find the data parameter (usually a dict or pydantic model)
            data = None
            for arg in args:
                if isinstance(arg, dict):
                    data = arg
                    break
            
            if data is None:
                for value in kwargs.values():
                    if isinstance(value, dict):
                        data = value
                        break
            
            # Use centralized validation
            if data and required_fields:
                validate_required_fields(data, required_fields, func.__name__)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def log_request_context(endpoint: str, context: Dict[str, Any]) -> None:
    """
    Log request context for debugging.
    
    Args:
        endpoint: API endpoint name
        context: Context information (user_id, request_id, etc.)
    """
    context_str = ", ".join([f"{k}={v}" for k, v in context.items()])
    logger.debug(f"🔍 {endpoint} request [{context_str}]")


class ApiResponseBuilder:
    """
    Builder class for creating consistent API responses.
    """
    
    def __init__(self):
        self._data = None
        self._message = None
        self._status = "success"
    
    def data(self, data: Any) -> 'ApiResponseBuilder':
        """Set response data."""
        self._data = data
        return self
    
    def message(self, message: str) -> 'ApiResponseBuilder':
        """Set response message."""
        self._message = message
        return self
    
    def success(self) -> 'ApiResponseBuilder':
        """Mark response as successful."""
        self._status = "success"
        return self
    
    def error(self) -> 'ApiResponseBuilder':
        """Mark response as error."""
        self._status = "error"
        return self
    
    def build(self) -> ApiResponse:
        """Build the API response."""
        return ApiResponse(
            status=self._status,
            data=self._data,
            message=self._message
        )


def response_builder() -> ApiResponseBuilder:
    """
    Factory function to create an API response builder.
    
    Usage:
        return response_builder().data({"id": 1}).message("User created").build()
    """
    return ApiResponseBuilder()


# Internal logging helpers
def _log_api_error(operation: str, error: Exception, context: Optional[dict] = None) -> None:
    """Log API errors with consistent format."""
    context_str = ""
    if context:
        context_items = [f"{k}={v}" for k, v in context.items()]
        context_str = f" [{', '.join(context_items)}]"
    
    logger.error(f"❌ {operation} failed{context_str}: {str(error)}")


def _log_api_success(operation: str, context: Optional[dict] = None) -> None:
    """Log API success with consistent format."""
    context_str = ""
    if context:
        context_items = [f"{k}={v}" for k, v in context.items()]
        context_str = f" [{', '.join(context_items)}]"
    
    logger.info(f"✅ {operation} completed successfully{context_str}")


# Legacy compatibility - mark for deprecation
# These functions are provided for backward compatibility but should be migrated to the consolidated versions above
