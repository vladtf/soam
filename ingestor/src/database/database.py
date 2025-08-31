"""
SQLAlchemy database setup for ingestor.
Following the backend pattern for consistency.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from functools import lru_cache

# Database configuration
INGESTOR_DATABASE_URL = os.getenv("INGESTOR_DATABASE_URL", "sqlite:///./ingestor.db")

# Create engine
engine = create_engine(
    INGESTOR_DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in INGESTOR_DATABASE_URL else {}
)

# Create sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@lru_cache()
def get_database_engine():
    """Get database engine - cached for performance."""
    return engine


def init_database():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
