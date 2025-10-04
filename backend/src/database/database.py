"""
SQLite database configuration and session management.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

# Database URL
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./feedback.db")

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get database session.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """
    Create all tables in the database.
    """
    Base.metadata.create_all(bind=engine)


def ensure_rule_metrics_columns() -> None:
    """Ensure applied_count and last_applied_at columns exist on normalization_rules.

    This is a lightweight, idempotent migration mainly for SQLite.
    """
    try:
        dialect: str = engine.url.get_backend_name()
        with engine.connect() as conn:
            if 'sqlite' in dialect:
                rows = conn.exec_driver_sql("PRAGMA table_info('normalization_rules')").fetchall()
                existing = {row[1] for row in rows}  # name is at index 1
                if 'applied_count' not in existing:
                    conn.exec_driver_sql(
                        "ALTER TABLE normalization_rules ADD COLUMN applied_count INTEGER NOT NULL DEFAULT 0"
                    )
                if 'last_applied_at' not in existing:
                    conn.exec_driver_sql(
                        "ALTER TABLE normalization_rules ADD COLUMN last_applied_at DATETIME NULL"
                    )
            else:
                # Best-effort for other DBs
                try:
                    conn.exec_driver_sql(
                        "ALTER TABLE normalization_rules ADD COLUMN applied_count INTEGER NOT NULL DEFAULT 0"
                    )
                except Exception:
                    pass
                try:
                    conn.exec_driver_sql(
                        "ALTER TABLE normalization_rules ADD COLUMN last_applied_at TIMESTAMPTZ NULL"
                    )
                except Exception:
                    pass
    except Exception:
        # Non-fatal; table might not exist yet or DB may not support ALTER
        pass


def ensure_rule_ownership_columns():
    """Ensure created_by and updated_by columns exist on normalization_rules.
    
    This is a lightweight, idempotent migration for adding ownership tracking.
    """
    try:
        dialect = engine.url.get_backend_name()
        with engine.connect() as conn:
            if 'sqlite' in dialect:
                rows = conn.exec_driver_sql("PRAGMA table_info('normalization_rules')").fetchall()
                existing = {row[1] for row in rows}  # name is at index 1
                if 'created_by' not in existing:
                    conn.exec_driver_sql(
                        "ALTER TABLE normalization_rules ADD COLUMN created_by VARCHAR(255) NOT NULL DEFAULT 'system'"
                    )
                if 'updated_by' not in existing:
                    conn.exec_driver_sql(
                        "ALTER TABLE normalization_rules ADD COLUMN updated_by VARCHAR(255) NULL"
                    )
            else:
                # Best-effort for other DBs
                try:
                    conn.exec_driver_sql(
                        "ALTER TABLE normalization_rules ADD COLUMN created_by VARCHAR(255) NOT NULL DEFAULT 'system'"
                    )
                except Exception:
                    pass
                try:
                    conn.exec_driver_sql(
                        "ALTER TABLE normalization_rules ADD COLUMN updated_by VARCHAR(255) NULL"
                    )
                except Exception:
                    pass
    except Exception:
        # Non-fatal; table might not exist yet or DB may not support ALTER
        pass


def ensure_computation_ownership_columns():
    """Ensure created_by and updated_by columns exist on computations.
    
    This is a lightweight, idempotent migration for adding ownership tracking.
    """
    try:
        dialect = engine.url.get_backend_name()
        with engine.connect() as conn:
            if 'sqlite' in dialect:
                rows = conn.exec_driver_sql("PRAGMA table_info('computations')").fetchall()
                existing = {row[1] for row in rows}  # name is at index 1
                if 'created_by' not in existing:
                    conn.exec_driver_sql(
                        "ALTER TABLE computations ADD COLUMN created_by VARCHAR(255) NOT NULL DEFAULT 'system'"
                    )
                if 'updated_by' not in existing:
                    conn.exec_driver_sql(
                        "ALTER TABLE computations ADD COLUMN updated_by VARCHAR(255) NULL"
                    )
            else:
                # Best-effort for other DBs
                try:
                    conn.exec_driver_sql(
                        "ALTER TABLE computations ADD COLUMN created_by VARCHAR(255) NOT NULL DEFAULT 'system'"
                    )
                except Exception:
                    pass
                try:
                    conn.exec_driver_sql(
                        "ALTER TABLE computations ADD COLUMN updated_by VARCHAR(255) NULL"
                    )
                except Exception:
                    pass
    except Exception:
        # Non-fatal; table might not exist yet or DB may not support ALTER
        pass


def ensure_device_ownership_columns():
    """Ensure created_by and updated_by columns exist on devices.
    
    This is a lightweight, idempotent migration for adding ownership tracking.
    """
    try:
        dialect = engine.url.get_backend_name()
        with engine.connect() as conn:
            if 'sqlite' in dialect:
                rows = conn.exec_driver_sql("PRAGMA table_info('devices')").fetchall()
                existing = {row[1] for row in rows}  # name is at index 1
                if 'created_by' not in existing:
                    conn.exec_driver_sql(
                        "ALTER TABLE devices ADD COLUMN created_by VARCHAR(255) NOT NULL DEFAULT 'system'"
                    )
                if 'updated_by' not in existing:
                    conn.exec_driver_sql(
                        "ALTER TABLE devices ADD COLUMN updated_by VARCHAR(255) NULL"
                    )
            else:
                # Best-effort for other DBs
                try:
                    conn.exec_driver_sql(
                        "ALTER TABLE devices ADD COLUMN created_by VARCHAR(255) NOT NULL DEFAULT 'system'"
                    )
                except Exception:
                    pass
                try:
                    conn.exec_driver_sql(
                        "ALTER TABLE devices ADD COLUMN updated_by VARCHAR(255) NULL"
                    )
                except Exception:
                    pass
    except Exception:
        # Non-fatal; table might not exist yet or DB may not support ALTER
        pass


def ensure_computation_recommended_tile_type_column():
    """Ensure recommended_tile_type column exists on computations.
    
    This is a lightweight, idempotent migration for adding tile type recommendations.
    """
    try:
        dialect = engine.url.get_backend_name()
        with engine.connect() as conn:
            if 'sqlite' in dialect:
                rows = conn.exec_driver_sql("PRAGMA table_info('computations')").fetchall()
                existing = {row[1] for row in rows}  # name is at index 1
                if 'recommended_tile_type' not in existing:
                    conn.exec_driver_sql(
                        "ALTER TABLE computations ADD COLUMN recommended_tile_type VARCHAR(32) NULL"
                    )
            else:
                # Best-effort for other DBs
                try:
                    conn.exec_driver_sql(
                        "ALTER TABLE computations ADD COLUMN recommended_tile_type VARCHAR(32) NULL"
                    )
                except Exception:
                    pass
    except Exception:
        # Non-fatal; table might not exist yet or DB may not support ALTER
        pass
