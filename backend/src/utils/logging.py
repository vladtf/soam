"""
Comprehensive logging utilities for the SOAM backend.
Consolidates logging.py and shared_logging.py to eliminate duplication.
"""
import logging
import functools
import time
from typing import Optional


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Get a logger instance with consistent configuration.
    
    Args:
        name: Logger name (typically __name__)
        level: Optional logging level override
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if level is not None:
        logger.setLevel(level)
        
    return logger


def log_api_error(logger: logging.Logger, operation: str, error: Exception, context: Optional[dict] = None) -> None:
    """
    Log API errors with consistent format and context.
    
    Args:
        logger: Logger instance
        operation: Description of the operation that failed
        error: The exception that occurred
        context: Optional additional context (user_id, request_id, etc.)
    """
    context_str = ""
    if context:
        context_items = [f"{k}={v}" for k, v in context.items()]
        context_str = f" [{', '.join(context_items)}]"
    
    logger.error(f"❌ {operation} failed{context_str}: {str(error)}")


def log_api_success(logger: logging.Logger, operation: str, context: Optional[dict] = None) -> None:
    """
    Log API success with consistent format.
    
    Args:
        logger: Logger instance
        operation: Description of the successful operation
        context: Optional additional context
    """
    context_str = ""
    if context:
        context_items = [f"{k}={v}" for k, v in context.items()]
        context_str = f" [{', '.join(context_items)}]"
    
    logger.info(f"✅ {operation} completed successfully{context_str}")


def log_exceptions(logger: Optional[logging.Logger] = None):
    """
    Decorator to automatically log exceptions in functions.
    
    Args:
        logger: Logger instance, will create one if None
        
    Usage:
        @log_exceptions()
        def my_function():
            # exceptions are automatically logged
            pass
    """
    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = get_logger(func.__module__)
            
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Exception in {func.__name__}: {e}", exc_info=True)
                raise
        return wrapper
    return decorator


def log_function_calls(logger: Optional[logging.Logger] = None, level: int = logging.DEBUG):
    """
    Decorator to log function calls and their results.
    
    Args:
        logger: Logger instance, will create one if None
        level: Logging level to use
        
    Usage:
        @log_function_calls()
        def my_function(arg1, arg2):
            return result
    """
    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = get_logger(func.__module__)
            
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if logger.isEnabledFor(level):
                args_repr = ', '.join(repr(a) for a in args)
                kwargs_repr = ', '.join(f'{k}={v!r}' for k, v in kwargs.items())
                all_args = ', '.join(filter(None, [args_repr, kwargs_repr]))
                logger.log(level, f"Calling {func.__name__}({all_args})")
            
            result = func(*args, **kwargs)
            
            if logger.isEnabledFor(level):
                logger.log(level, f"{func.__name__} returned {result!r}")
            
            return result
        return wrapper
    return decorator


def log_execution_time(logger: Optional[logging.Logger] = None, level: int = logging.INFO, operation_name: Optional[str] = None):
    """
    Decorator to log function execution time with performance metrics.
    
    Args:
        logger: Logger instance, will create one if None
        level: Logging level to use (default: INFO)
        operation_name: Custom operation name for logging (defaults to function name)
        
    Usage:
        @log_execution_time()
        def my_function():
            # execution time is automatically logged
            pass
            
        @log_execution_time(operation_name="Schema Inference")
        def _get_streaming_schema(self):
            # logged as "Schema Inference completed in X.XXs"
            pass
    """
    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = get_logger(func.__module__)
            
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            operation = operation_name or func.__name__.replace('_', ' ').title()
            
            logger.log(level, f"🚀 Starting {operation}...")
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                end_time = time.time()
                execution_time = end_time - start_time
                
                # Format time appropriately
                if execution_time < 0.001:
                    time_str = f"{execution_time * 1000000:.1f}μs"
                elif execution_time < 1:
                    time_str = f"{execution_time * 1000:.1f}ms"
                elif execution_time < 60:
                    time_str = f"{execution_time:.2f}s"
                else:
                    minutes = int(execution_time // 60)
                    seconds = execution_time % 60
                    time_str = f"{minutes}m {seconds:.2f}s"
                
                logger.log(level, f"✅ {operation} completed in {time_str}")
                return result
                
            except Exception as e:
                end_time = time.time()
                execution_time = end_time - start_time
                
                if execution_time < 1:
                    time_str = f"{execution_time * 1000:.1f}ms"
                else:
                    time_str = f"{execution_time:.2f}s"
                    
                logger.log(level, f"❌ {operation} failed after {time_str}: {str(e)}")
                raise
                
        return wrapper
    return decorator
