---
applyTo: 'backend/**'
---

# Backend Service (Python/FastAPI) - Port 8000

## Tech Map / Key Files

**Main Application Structure:**
- `backend/Dockerfile` - Multi-stage build with Spark/Java dependencies
- `backend/Pipfile` - Python dependencies (pipenv managed)
- `backend/src/main.py` - FastAPI app factory (`create_app()`) with lifespan context manager
- `backend/src/middleware.py` - `RequestIdMiddleware` for request tracing (UUID generation, duration logging)
- `backend/src/logging_config.py` - Structured logging configuration with `set_request_id()`
- `backend/src/metrics.py` - Prometheus metrics (pipeline latency, throughput, data freshness)

**Startup Sequence** (in `main.py` lifespan):
1. Prometheus metrics initialization
2. `.env` loading
3. DB table creation + column migrations (5 `ensure_*_columns()` calls)
4. Normalization rule seeding (`DataCleaner.seed_normalization_rules()`)
5. Default settings + admin user initialization
6. `NormalizationRuleUsageTracker.start()` background aggregator
7. DI singletons materialized (config, Spark, Neo4j)

**18 routers registered**: auth, buildings, spark, health, minio, devices, feedback, normalization, normalization_preview, value_transformation, errors, computations, copilot, dashboard_tiles, config, settings, schema

### Authentication Layer (`backend/src/auth/`)
- `config.py` - `AuthSettings` dataclass with JWT configuration (SECRET_KEY, token expiration, default admin)
- `security.py` - Password hashing (bcrypt), JWT token creation/decoding (python-jose)
- `dependencies.py` - **CRITICAL**: Auth dependencies:
  - `get_current_user` - Requires valid JWT, returns `User`
  - `get_current_user_optional` - Returns `User | None` (for endpoints that work with or without auth)
  - `get_user_roles_from_token(authorization, db)` - Extracts roles without raising exceptions
  - `require_roles(allowed_roles)` - Factory: user must have ANY of the specified roles
  - `require_admin` - Shortcut for `require_roles([UserRole.ADMIN])`
  - `require_user_or_admin` - Shortcut for `require_roles([UserRole.ADMIN, UserRole.USER])`
  - `require_any_role` - Shortcut for `require_roles([UserRole.ADMIN, UserRole.USER, UserRole.VIEWER])`
- `routes.py` - Full auth API: login, register, refresh, logout, user management, test-users
- `init_admin.py` - Default admin user initialization with all roles

**Auth System Features:**
- Multi-role support: Users can have multiple roles stored as JSON list (e.g., `["admin", "user", "viewer"]`)
- JWT access tokens (30min) + refresh tokens (7 days)
- Role-based authorization: `require_roles()` checks if user has ANY of the specified roles
- User model: `roles` field is JSON list, with helper methods `get_roles()`, `has_role()`, `has_any_role()`
- Password hashing: bcrypt via passlib (bcrypt==4.0.1 pinned for compatibility)
- Default credentials: Username: `admin`, Password: `admin`, Roles: `["admin", "user", "viewer"]`

### API Layer (`backend/src/api/`)
- `dependencies.py` - **CRITICAL**: Central DI with `@lru_cache()` singletons and type aliases
  - `AppConfig` class with all config from env vars
  - 4 cached singletons: `get_config()`, `get_spark_manager()`, `get_neo4j_manager()`, `get_minio_client()`
  - 4 type aliases: `SparkManagerDep`, `Neo4jManagerDep`, `ConfigDep`, `MinioClientDep`
- `models.py` - Pydantic request/response models with generic types (`ApiResponse[T]`, `ApiListResponse[T]`)
  - Domain model triplets: Create/Update/Response for Buildings, Devices, NormalizationRules, ValueTransformationRules, Computations, DashboardTiles, Feedback, Settings
  - `DeviceCreate`/`DeviceUpdate` include `sensitivity` and `data_retention_days`
  - `DashboardTile` models include `access_restricted` and `restriction_message` for RBAC
- `response_utils.py` - **MANDATORY**: Unified response utilities
  - Success: `success_response(data, message)`, `list_response(data, total, page, ...)`
  - Errors (all return `HTTPException`, must `raise`): `bad_request_error()`, `not_found_error()`, `forbidden_error()`, `conflict_error()`, `internal_server_error()`
  - Exception converters: `handle_http_exception(e)`, `handle_generic_exception(e, context)`
- Core API routers:
  - `config_routes.py` - System configuration endpoints
  - `dashboard_tiles_routes.py` - User-defined dashboard tiles with time series support
  - `device_routes.py` - Device/sensor management with Neo4j integration
  - `error_routes.py` - Client error tracking and analytics
  - `feedback_routes.py` - User feedback collection
  - `health_routes.py` - Health checks and system status
  - `minio_routes.py` - MinIO bucket/object management and data access
  - `normalization_preview_routes.py` - Schema normalization preview
  - `normalization_routes.py` - Data normalization rule management
  - `settings_routes.py` - User settings management
  - `value_transformation_routes.py` - Value transformation rule management
- `routers/schema.py` - Schema inference stream management

### Business Logic Layer
- `backend/src/computations/` - SQL computation engine with AI copilot integration:
  - `computation_routes.py` - CRUD operations for saved computations
  - `service.py` - Core computation execution service
  - `executor.py` - SQL query executor with Spark integration
  - `validation.py` - SQL query validation and security
  - `sources.py` - Data source discovery and schema introspection
  - `examples.py` - Pre-built computation examples
  - `sensitivity.py` - **Sensitivity-Based Access Control (SBAC)**: Analyzes computation data sensitivity based on referenced devices, enforces role-based access (viewer→PUBLIC, user→INTERNAL, admin→RESTRICTED)
- `backend/src/copilot/` - AI-powered natural language to SQL conversion:
  - `copilot_routes.py` - AI copilot API endpoints
  - `copilot_service.py` - Azure OpenAI integration for SQL generation
- `backend/src/dashboard/` - Dashboard tile system:
  - `examples.py` - Predefined dashboard tile templates with smart computation matching (4 static examples: table-basic, stat-avg, timeseries-chart, temperature-over-threshold-table)
- `backend/src/services/` - Cross-cutting business services:
  - `ingestor_schema_client.py` - HTTP client for fetching metadata from ingestor service
  - `normalization_preview.py` - Schema normalization preview logic

### Data & Storage Layer
- `backend/src/database/` - SQLAlchemy ORM and database management:
  - `database.py` - Database connection, session management, and initialization
  - `models.py` - Core SQLAlchemy models:
    - `User` - Multi-role RBAC (`roles` as JSON list), helpers: `get_roles()`, `has_role()`, `has_any_role()`
    - `NormalizationRule` - `raw_key` → `canonical_key` mapping, `applied_count`/`last_applied_at` metrics
    - `ValueTransformationRule` - `field_name`, `transformation_type` (filter/aggregate/convert/validate), `order_priority`
    - `Computation` - JSON `definition`, `recommended_tile_type`, `sensitivity` (enum), `source_devices` (JSON list)
    - `DashboardTile` - `computation_id`, `viz_type`, JSON `config`/`layout`, `sensitivity`
    - `Device` - `ingestion_id` (unique), `sensitivity`, `data_retention_days`
    - `Setting` - Key-value store with `value_type` enum (string/number/boolean/json), category grouping
    - `ClientError` - Frontend error tracking with stack/url/component/severity
    - `Feedback` - Email + message
  - 2 Enums: `UserRole` (admin/user/viewer), `DataSensitivity` (public/internal/confidential/restricted)
- `backend/src/minio/` - Object storage service integration:
  - `minio_browser.py` - `MinioBrowser` class wrapping MinIO SDK (list_prefixes, list_recursive, preview_parquet via PyArrow→Pandas, delete_object, delete_objects, delete_prefix)
- `backend/src/neo4j/` - Graph database operations:
  - `neo4j_manager.py` - Core Neo4j connection and CRUD operations
  - `building_routes.py` - Building/location management API

### Spark & Analytics Layer
- `backend/src/spark/` - Apache Spark integration for stream processing:
  - `spark_manager.py` - **CRITICAL**: Main Spark coordinator with stream lifecycle management
  - `session.py` - `SparkSessionManager` with optimized S3A configuration
  - `spark_routes.py` - Spark cluster management API
  - `spark_models.py` - Pydantic models for Spark API responses
  - `streaming.py` - `StreamingManager` for stream orchestration
  - `data_access.py` - `DataAccessManager` for bronze/silver/gold layer access
  - `diagnostics.py` - Data pipeline diagnostics
  - `diagnostics_enhanced.py` - Enhanced diagnostics with detailed tracing
  - `master_client.py` - Spark master client for cluster communication
  - `config.py` - Spark configuration settings
  - `enrichment/` - Data enrichment pipeline:
    - `enrichment_manager.py` - Main orchestrator: fetch schema from ingestor → create raw stream → transform to union schema → add metadata → write via BatchProcessor. Uses flexible schema strategy (all numeric/timestamp fields read as StringType for cross-source compatibility). Thread-safe with `_enrich_query_lock`.
    - `batch_processor.py` - 5-step pipeline with `@profile_step` decorator on each step: get_allowed_ids → should_process → filter_dataframe → apply_transformations → write_delta. Delta write with `mergeSchema("true")`, partitioned by `ingestion_id`.
    - `union_schema.py` - Dynamic schema handling for multi-source data
    - `device_filter.py` - Device-based data filtering
    - `cleaner.py` - Data cleaning, validation, and normalization rule seeding
    - `usage_tracker.py` - `NormalizationRuleUsageTracker` with background aggregation
    - `value_transformer.py` - Value transformation logic

### Utilities (`backend/src/utils/`)
- `api_utils.py` - **MANDATORY**: API decorators and utilities:
  - `@handle_api_errors(operation_name)` - Async error handling decorator
  - `@handle_api_errors_sync(operation_name)` - Sync error handling decorator
  - `@api_endpoint(success_message, error_message)` - Advanced auto async/sync detection
  - `@validate_request_data(required_fields, optional_fields)` - Input validation decorator
  - `ApiResponseBuilder` - Fluent builder with `.data()`, `.message()`, `.success()`, `.error()`, `.build()` chain
  - `log_request_context()` - Debug logging utility
- `logging.py` - Comprehensive logging utilities:
  - `get_logger(name)` - Standard logger creation
  - `log_api_error(logger, operation, error, context)` - Structured error logging with emoji
  - `log_api_success(logger, operation, context)` - Structured success logging with emoji
  - `@log_exceptions()` - Auto-log exceptions in functions
  - `@log_function_calls()` - Log function calls and results at DEBUG level
  - `@log_execution_time(operation_name)` - Log function duration with smart formatting (μs/ms/s/m) and 🚀/✅/❌ emojis
- `step_profiler.py` - Performance profiling with Prometheus metrics:
  - `StepProfiler` class with `record(module, step, duration)`, `time_step(module, step)` context manager
  - `@profile_step(module, step)` decorator - Records step durations as Prometheus Gauge (`step_duration_seconds` with labels `[module, step]`)
  - Module-level singleton: `step_profiler`
  - Used extensively in `batch_processor.py` for pipeline step profiling
- `database_utils.py` - Database utilities and error handling
- `settings_manager.py` - Application settings management
- `spark_utils.py` - Spark-specific utilities
- `validation.py` - Input validation utilities

### Project Structure
- `/api/` - FastAPI routers grouped by domain (health, devices, minio, etc.)
- `/services/` - Business logic services
- `/database/` - SQLAlchemy models and database utilities
- `/spark/` - Spark streaming and enrichment components
- `/neo4j/` - Graph database operations
- `/auth/` - JWT authentication and authorization
- `/computations/` - SQL computation engine with sensitivity analysis
- `/dashboard/` - Dashboard tile examples and templates
- `/copilot/` - AI-powered SQL generation
- `/minio/` - MinIO browser abstraction

## Backend Development Patterns

### 1. Dependency Injection Architecture (MANDATORY)
**Pattern**: All services use FastAPI's DI with cached instances and type aliases
**Location**: `src/api/dependencies.py` - Central DI configuration

```python
# ALWAYS use these exact imports and patterns for new endpoints
from src.api.dependencies import SparkManagerDep, Neo4jManagerDep, ConfigDep, MinioClientDep
from fastapi import Depends

@router.get("/endpoint", response_model=ApiResponse)
async def handler(spark_manager: SparkManagerDep, config: ConfigDep):
    # Type aliases provide dependency injection + type hints
    # Spark session available via spark_manager.session_manager.spark
    return success_response(data=result)
```

**Key Benefits**:
- `@lru_cache()` ensures singleton instances across requests
- Type aliases (`SparkManagerDep`, `Neo4jManagerDep`) provide both DI and typing
- Centralized configuration management via `AppConfig`

### 2. Explicit Error Handling (MANDATORY)
**Pattern**: All error utilities return exceptions that must be explicitly raised

```python
from src.api.response_utils import success_response, not_found_error, bad_request_error, forbidden_error, internal_server_error

@router.patch("/endpoint/{item_id}")
def update_item(item_id: int, payload: UpdatePayload):
    try:
        if not payload.updated_by or not payload.updated_by.strip():
            raise bad_request_error("User information required (updated_by)")
        
        item = db.query(Item).filter(Item.id == item_id).one_or_none()
        if not item:
            raise not_found_error("Item not found")
            
        # Update logic...
        return success_response(item.to_dict(), "Item updated successfully")
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error("❌ Error updating item: %s", e)
        db.rollback()
        raise internal_server_error("Failed to update item", str(e))
```

**Key Rules**:
- NEVER call error functions directly - always `raise error_function()`
- Use specific error types: `bad_request_error()`, `not_found_error()`, `forbidden_error()`, `conflict_error()`, `internal_server_error()`
- Always re-raise `HTTPException` before catching generic `Exception`
- Always include database rollback in exception handlers
- Provide detailed error messages for debugging

### 3. Comprehensive Logging (MANDATORY)
**Pattern**: Standardized logging with emojis, context, and decorators

```python
from src.utils.logging import get_logger, log_execution_time, log_exceptions
logger = get_logger(__name__)

# Use emoji prefixes for easy log scanning
logger.info("✅ Device updated by '%s': %s changes", user, "; ".join(changes))
logger.error("❌ Failed to update device: %s", str(e))
logger.warning("⚠️ Potential schema conflict detected")
logger.debug("🔍 Processing batch with %d files", file_count)

# Decorator for automatic execution time logging
@log_execution_time(operation_name="Schema Inference")
def get_schema():
    # Logs: "🚀 Starting Schema Inference..." then "✅ Schema Inference completed in 1.23s"
    pass

# Decorator for automatic exception logging
@log_exceptions()
def risky_operation():
    # Exceptions are automatically logged with exc_info=True
    pass
```

### 4. API Response Pattern (MANDATORY)
**Pattern**: Consistent response models and utilities

```python
from src.api.response_utils import success_response, list_response
from src.api.models import ApiResponse, ApiListResponse

@router.get("/items", response_model=ApiListResponse[ItemResponse])
def list_items():
    items = db.query(Item).all()
    return list_response([item.to_dict() for item in items], "Items retrieved successfully")

@router.post("/items", response_model=ApiResponse[ItemResponse])
def create_item(payload: ItemCreate):
    # Create logic...
    return success_response(item.to_dict(), "Item created successfully")
```

**Response Standards**:
- ALWAYS specify `response_model=ApiResponse[T]` or `ApiListResponse[T]`
- Use `success_response()` for single items, `list_response()` for collections
- Include meaningful success messages
- Generic `T` types ensure frontend type safety

### 5. API Decorators & Utilities (RECOMMENDED)
**Pattern**: Use decorators and builders to reduce boilerplate

```python
from src.utils.api_utils import handle_api_errors, handle_api_errors_sync, api_endpoint, validate_request_data, response_builder

# Async error handling decorator
@router.get("/config", response_model=ApiResponse)
@handle_api_errors("get system configuration")
async def get_config():
    # No try/catch needed - decorator handles HTTPException (re-raises), DatabaseError, SQLAlchemyError, generic Exception
    return success_response(data=config_data, message="Config retrieved")

# Sync error handling decorator
@router.get("/sync-endpoint", response_model=ApiResponse)
@handle_api_errors_sync("sync operation")
def sync_handler():
    return success_response(data=result)

# Input validation decorator
@validate_request_data(required_fields=["name", "type"], optional_fields=["description"])
def process_data(data):
    pass

# Fluent response builder
return response_builder().data(result).message("Success").success().build()
```

### 6. Performance Profiling (RECOMMENDED)
**Pattern**: Use step profiler for pipeline performance monitoring

```python
from src.utils.step_profiler import step_profiler, profile_step

# As decorator on pipeline steps
@profile_step("batch_processor", "1_filter_dataframe")
def _filter_dataframe(self, df):
    # Duration recorded as Prometheus Gauge: step_duration_seconds{module="batch_processor", step="1_filter_dataframe"}
    pass

# As context manager
with step_profiler.time_step("enrichment", "schema_inference"):
    schema = infer_schema(data)

# Manual recording
step_profiler.record("pipeline", "total_duration", elapsed_seconds)
```

### 7. Sensitivity-Based Access Control (SBAC)
**Pattern**: Data sensitivity analysis for computations and dashboard tiles
**Location**: `backend/src/computations/sensitivity.py`

```python
from src.computations.sensitivity import can_access_sensitivity, calculate_computation_sensitivity, get_restriction_message

# Sensitivity levels: PUBLIC < INTERNAL < CONFIDENTIAL < RESTRICTED
# Role mapping: viewer → PUBLIC, user → INTERNAL, admin → RESTRICTED

# Calculate sensitivity from referenced devices
sensitivity, source_devices = calculate_computation_sensitivity(db, computation.definition)

# Check access
if not can_access_sensitivity(user_roles, sensitivity):
    message = get_restriction_message(sensitivity, user_roles)
    # Returns user-friendly denial message
```

### 8. JWT Authentication System
**Location**: `backend/src/auth/` - Complete JWT-based multi-role authentication

**Multi-Role Authorization Pattern**:
```python
from src.auth.dependencies import get_current_user, get_current_user_optional, require_roles, require_admin, require_user_or_admin, require_any_role

# Protect routes with specific roles
@router.get("/admin-only")
async def admin_endpoint(user: User = Depends(require_admin)):
    pass

# Allow multiple roles (user has ANY of the specified roles)
@router.get("/users-or-admins")
async def protected(user: User = Depends(require_user_or_admin)):
    pass

# Optional authentication (works with or without token)
@router.get("/public-with-extras")
async def optional_auth(user: User | None = Depends(get_current_user_optional)):
    if user:
        # Show extra data for authenticated users
        pass

# Extract roles without requiring auth (for optional access control)
roles = get_user_roles_from_token(request.headers.get("Authorization"), db)
```

## Code Conventions

### Python (Backend) - MANDATORY Patterns
```powershell
# Use pipenv for all Python operations
cd backend
pipenv install --dev
pipenv shell

# Run tests
# pipenv run pytest tests/
```

### Module Import Standards (MANDATORY)
**Pattern**: Consistent import organization for all route files

```python
"""
Module docstring describing the API endpoints.
"""
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

# API models and response utilities (always these exact imports)
from src.api.models import ApiResponse, ApiListResponse, [SpecificModels]
from src.api.response_utils import success_response, list_response, not_found_error, bad_request_error, forbidden_error, internal_server_error

# Dependencies (use type aliases)
from src.api.dependencies import SparkManagerDep, Neo4jManagerDep, ConfigDep, MinioClientDep
from src.database.database import get_db  # Only for DB routes

# Utilities
from src.utils.logging import get_logger
from src.utils.api_utils import handle_api_errors, handle_api_errors_sync  # When using decorators

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["feature_name"])
```

### Database Operations (MANDATORY)
**Pattern**: Explicit transaction management with rollback handling

```python
@router.post("/items", response_model=ApiResponse[ItemResponse])
def create_item(payload: ItemCreate, db: Session = Depends(get_db)):
    try:
        # Validate input first
        if not payload.created_by or not payload.created_by.strip():
            raise bad_request_error("User information required (created_by)")
        
        # Check for existing records
        existing = db.query(Item).filter(Item.name == payload.name).one_or_none()
        if existing:
            raise conflict_error("Item already exists")
            
        # Create new record
        item = Item(
            name=payload.name,
            description=payload.description,
            created_by=payload.created_by.strip()
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        
        logger.info("✅ Item created by '%s': %s", payload.created_by, item.name)
        return success_response(item.to_dict(), "Item created successfully")
    except HTTPException:
        raise  # Always re-raise HTTP exceptions
    except Exception as e:
        logger.error("❌ Error creating item: %s", e)
        db.rollback()  # ALWAYS rollback on exceptions
        raise internal_server_error("Failed to create item", str(e))
```

### Router Organization (MANDATORY)
**Pattern**: Consistent router structure and endpoint naming

```python
router = APIRouter(prefix="/api", tags=["feature_name"])

# GET endpoints first (list, then single item)
@router.get("/items", response_model=ApiListResponse[ItemResponse])
def list_items(): pass

@router.get("/items/{item_id}", response_model=ApiResponse[ItemResponse])
def get_item(): pass

# POST endpoints (create)
@router.post("/items", response_model=ApiResponse[ItemResponse])
def create_item(): pass

# PATCH endpoints (update)
@router.patch("/items/{item_id}", response_model=ApiResponse[ItemResponse])
def update_item(): pass

# DELETE endpoints
@router.delete("/items/{item_id}", response_model=ApiResponse)
def delete_item(): pass

# Special action endpoints last
@router.post("/items/{item_id}/action", response_model=ApiResponse)
def perform_action(): pass
```

### Spark Integration Patterns
**Critical**: All Spark operations use the session manager pattern:
```python
# Get Spark session through dependency injection
spark = spark_manager.session_manager.spark
# Spark context available via spark.sparkContext

# Use batch-triggered approach for file processing
def start_stream():
    return (spark.readStream
        .format("rate")
        .option("rowsPerSecond", "1")
        .trigger(processingTime="30 seconds")
        .foreachBatch(process_batch)
        .start())

# Enrichment uses flexible schema (all numeric/timestamp as StringType)
# Delta write: mode("append"), mergeSchema("true"), partitioned by ingestion_id
```

## Core Service Architecture

**Key Services & Managers (All Singleton via DI):**

- `SparkManager` (`backend/src/spark/spark_manager.py`) - **CRITICAL**: Coordinates all Spark operations
  - `SparkSessionManager` - Optimized Spark session with S3A configuration
  - `StreamingManager` - Manages streaming query lifecycle
  - `EnrichmentManager` - Orchestrates data enrichment pipeline (schema fetch → stream → transform → batch process)
  - `DataAccessManager` - Provides bronze/silver/gold layer access
  - `BatchProcessor` - 5-step profiled pipeline with Delta write

- `Neo4jManager` (`backend/src/neo4j/neo4j_manager.py`) - Graph database operations
  - Building/location management with spatial queries
  - Ontology-based data relationships
  - Auto-provisioning of initial graph data

- `ComputationService` (`backend/src/computations/service.py`) - SQL execution engine
  - Dynamic query execution on Spark
  - Schema introspection and validation
  - Sensitivity analysis via `sensitivity.py`
  - Integration with AI copilot for query generation

- `CopilotService` (`backend/src/copilot/copilot_service.py`) - Azure OpenAI integration
  - Natural language to SQL conversion
  - Context-aware schema analysis
  - Query optimization recommendations

- `MinioBrowser` (`backend/src/minio/minio_browser.py`) - Object storage abstraction
  - list_prefixes, list_recursive, preview_parquet (PyArrow→Pandas)
  - delete_object, delete_objects (batch), delete_prefix

### Database Models

**Core SQLAlchemy Models (`backend/src/database/models.py`):**

```python
class UserRole(str, Enum):
    """User role enumeration for RBAC."""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"

class DataSensitivity(str, Enum):
    """Data sensitivity levels for SBAC."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"

class User(Base):
    """Multi-role RBAC. Helpers: get_roles(), has_role(), has_any_role()"""

class NormalizationRule(Base):
    """raw_key → canonical_key mapping. Tracks applied_count/last_applied_at."""

class ValueTransformationRule(Base):
    """field_name + transformation_type (filter/aggregate/convert/validate) + order_priority."""

class Computation(Base):
    """JSON definition, recommended_tile_type, sensitivity, source_devices."""

class DashboardTile(Base):
    """computation_id, viz_type, JSON config/layout, sensitivity."""

class Device(Base):
    """ingestion_id (unique), sensitivity, data_retention_days."""

class Setting(Base):
    """Key-value store with value_type (string/number/boolean/json), category."""

class ClientError(Base):
    """Frontend error tracking: stack, url, component, severity."""

class Feedback(Base):
    """User feedback: email + message."""
```
