"""
Comprehensive database utilities for session management, error handling, and common operations.
Consolidates database.py and database_utils.py to eliminate duplication.
"""
import logging
import functools
from contextlib import contextmanager
from typing import Optional, Type, TypeVar, Generic, List, Callable, Any
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from src.database.database import SessionLocal, get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class DatabaseError(Exception):
    """Custom exception for database operations."""
    pass


@contextmanager
def get_db_session():
    """
    Context manager for database sessions with automatic cleanup.
    
    Usage:
        with get_db_session() as db:
            # Use db session
            result = db.query(Model).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database operation failed: {str(e)}")
        raise DatabaseError(f"Database operation failed: {e}") from e
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during database operation: {str(e)}")
        raise
    finally:
        db.close()


def safe_db_operation(func):
    """
    Decorator for database operations with automatic error handling.
    
    Usage:
        @safe_db_operation
        def my_db_function(db: Session):
            return db.query(Model).all()
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemy error in {func.__name__}: {e}", exc_info=True)
            raise DatabaseError(f"Database operation failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            raise
    
    return wrapper


def execute_db_operation(operation: Callable[[Session], T], operation_name: str, context: Optional[dict] = None) -> Optional[T]:
    """
    Execute a database operation with consistent error handling and session management.
    
    Args:
        operation: Function that takes a Session and returns a result
        operation_name: Description of the operation for logging
        context: Optional context for logging
        
    Returns:
        Result of the operation or None if it failed
    """
    try:
        with get_db_session() as db:
            result = operation(db)
            logger.info(f"✅ {operation_name} completed successfully")
            return result
    except DatabaseError as e:
        logger.error(f"❌ {operation_name} failed (database error): {str(e)}")
        return None
    except Exception as e:
        logger.error(f"❌ {operation_name} failed (unexpected error): {str(e)}")
        return None


def create_db_record(model_instance: Any, operation_name: str) -> bool:
    """
    Create a database record with error handling.
    
    Args:
        model_instance: SQLAlchemy model instance to create
        operation_name: Description for logging
        
    Returns:
        True if successful, False otherwise
    """
    def create_operation(db: Session) -> bool:
        db.add(model_instance)
        db.flush()  # Get ID if needed
        return True
    
    result = execute_db_operation(create_operation, operation_name)
    return result is not None


def update_db_record(update_func: Callable[[Session], Any], operation_name: str) -> bool:
    """
    Update database records with error handling.
    
    Args:
        update_func: Function that performs the update
        operation_name: Description for logging
        
    Returns:
        True if successful, False otherwise
    """
    result = execute_db_operation(update_func, operation_name)
    return result is not None


class BaseRepository(Generic[T]):
    """
    Base repository class with common CRUD operations.
    """
    
    def __init__(self, model_class: Type[T], db_session: Session):
        self.model_class = model_class
        self.db = db_session
    
    @safe_db_operation
    def get_all(self, **filters) -> List[T]:
        """Get all records matching the filters."""
        query = self.db.query(self.model_class)
        for key, value in filters.items():
            if hasattr(self.model_class, key):
                query = query.filter(getattr(self.model_class, key) == value)
        return query.all()
    
    @safe_db_operation
    def get_by_id(self, id_value: int) -> Optional[T]:
        """Get a record by ID."""
        return self.db.query(self.model_class).filter(self.model_class.id == id_value).first()
    
    @safe_db_operation
    def create(self, **kwargs) -> T:
        """Create a new record."""
        instance = self.model_class(**kwargs)
        self.db.add(instance)
        self.db.flush()  # Get the ID without committing
        return instance
    
    @safe_db_operation
    def update(self, id_value: int, **kwargs) -> Optional[T]:
        """Update a record by ID."""
        instance = self.get_by_id(id_value)
        if instance:
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            self.db.flush()
        return instance
    
    @safe_db_operation
    def delete(self, id_value: int) -> bool:
        """Delete a record by ID."""
        instance = self.get_by_id(id_value)
        if instance:
            self.db.delete(instance)
            self.db.flush()
            return True
        return False
    
    @safe_db_operation
    def count(self, **filters) -> int:
        """Count records matching the filters."""
        query = self.db.query(self.model_class)
        for key, value in filters.items():
            if hasattr(self.model_class, key):
                query = query.filter(getattr(self.model_class, key) == value)
        return query.count()


def create_repository(model_class: Type[T], db_session: Session) -> BaseRepository[T]:
    """
    Factory function to create repository instances.
    
    Args:
        model_class: SQLAlchemy model class
        db_session: Database session
        
    Returns:
        Repository instance for the model
    """
    return BaseRepository(model_class, db_session)


# Legacy aliases for backward compatibility - these will be deprecated
safe_db_operation_legacy = execute_db_operation
execute_db_query = execute_db_operation
