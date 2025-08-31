---
applyTo: '**'
---

# SOAM Development Guide for AI Coding Assistants

## Project Overview

SOAM is a smart city IoT platform built with Python/FastAPI backend, React/TypeScript frontend, and microservices architecture. The system ingests MQTT sensor data, processes it with Spark streaming, stores in MinIO/Neo4j, and provides real-time dashboards. Development uses Skaffold + Kubernetes for local deployment with Docker containers.

The architecture follows a **data lake pattern** with Bronze (raw) → Silver (normalized) → Gold (aggregated) layers, all orchestrated through Kubernetes. **Core Data Flow**: MQTT sensors → Ingestor → MinIO (Bronze) → Spark Streaming → Schema Inference → Enrichment → Neo4j/Gold Layer → Dashboard

## Established Good Practices (FOLLOW THESE)

**Based on comprehensive codebase analysis, the following patterns are already established and MUST be maintained:**

### ✅ Dependency Injection Excellence
- Uses `@lru_cache()` for singleton instances
- Type aliases provide both DI and type hints: `SparkManagerDep`, `Neo4jManagerDep`, `ConfigDep`, `MinioClientDep`
- Centralized configuration in `AppConfig`

### ✅ Explicit Error Handling
- All error functions return `HTTPException` - callers must `raise` them explicitly
- Specific error types: `bad_request_error()`, `not_found_error()`, `conflict_error()`, `internal_server_error()`
- Database rollback pattern in all exception handlers

### ✅ Comprehensive Logging with Emojis
- Standardized emoji prefixes: ✅ (success), ❌ (error), ⚠️ (warning), 🔍 (debug)
- Context-rich logging with user/operation details
- Consistent logger creation: `logger = get_logger(__name__)`

### ✅ Response Model Consistency
- ALWAYS use `response_model=ApiResponse[T]` or `ApiListResponse[T]`
- Generic typing ensures frontend type safety
- Meaningful success messages in all responses

### ✅ Import Organization Standards
- Predictable import order: stdlib → FastAPI → SQLAlchemy → src modules
- Type alias usage for dependency injection
- Consistent utility imports

### ✅ Database Transaction Patterns
- Input validation before database operations
- Explicit transaction management with rollback
- User context tracking in all mutations

### ✅ Router Structure Conventions
- HTTP methods in logical order: GET (list, single) → POST → PATCH → DELETE
- Consistent endpoint naming and prefixing
- Action endpoints placed after CRUD operations

## Tech Map / Key Files

### Infrastructure & Deployment
- `skaffold.yaml` - Main dev orchestration, builds 8 services, handles port-forwarding
- `k8s/` - Kubernetes manifests for all services (StatefulSets/Services)
- `spark-values.yaml` - Helm values for Spark cluster deployment
- `docker-compose.yml` - Alternative Docker Compose setup
- `utils/cleanup-images.ps1` - PowerShell script for Docker image management

### Backend (Python/FastAPI)
- `backend/Dockerfile` - Multi-stage build with Spark/Java dependencies
- `backend/Pipfile` - Python dependencies (pipenv managed)
- `backend/src/main.py` - FastAPI app with lifecycle management
- `backend/src/api/` - API routers organized by feature
- `backend/src/schema_inference/` - Schema inference package (modular system)
- `backend/src/spark/` - Spark streaming and enrichment logic
- `backend/src/neo4j/` - Graph database interactions

### Frontend (React/TypeScript)
- `frontend/package.json` - React app with Vite, TypeScript, Bootstrap
- `frontend/src/` - Component-based React architecture
- `frontend/Dockerfile` - nginx-based production build

### Services
- `ingestor/` - MQTT-to-storage ingestion service
- `simulator/` - IoT device simulators (temperature, air quality, smart bins)
- `mosquitto/` - MQTT broker configuration

## Critical Development Patterns

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
from src.api.response_utils import success_response, not_found_error, bad_request_error, internal_server_error

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
    except Exception as e:
        logger.error("Error updating item: %s", e)
        db.rollback()
        raise internal_server_error("Failed to update item", str(e))
```

**Key Rules**: 
- NEVER call error functions directly - always `raise error_function()`
- Use specific error types: `bad_request_error()`, `not_found_error()`, `conflict_error()`, `internal_server_error()`
- Always include database rollback in exception handlers
- Provide detailed error messages for debugging

### 3. Comprehensive Logging (MANDATORY)
**Pattern**: Standardized logging with emojis and context

```python
from src.utils.logging import get_logger
logger = get_logger(__name__)

# Use emoji prefixes for easy log scanning
logger.info("✅ Device updated by '%s': %s changes", user, "; ".join(changes))
logger.error("❌ Failed to update device: %s", str(e))
logger.warning("⚠️ Potential schema conflict detected")
logger.debug("🔍 Processing batch with %d files", file_count)
```

**Logging Standards**:
- ✅ Success operations with context details
- ❌ Errors with full exception details
- ⚠️ Warnings for potential issues
- 🔍 Debug information for troubleshooting
- Always include user/operation context in business logic logs

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

### 5. API Decorators (RECOMMENDED)
**Pattern**: Use decorators to reduce boilerplate error handling

```python
from src.utils.api_utils import handle_api_errors, handle_api_errors_sync

@router.get("/config", response_model=ApiResponse)
@handle_api_errors("get system configuration")
async def get_config():
    # No try/catch needed - decorator handles exceptions
    return success_response(data=config_data, message="Config retrieved")

# For sync endpoints
@router.get("/sync-endpoint", response_model=ApiResponse)  
@handle_api_errors_sync("sync operation")
def sync_handler():
    return success_response(data=result)
```

**Benefits**: Eliminates repetitive try/catch blocks, standardizes error responses

### 6. Schema Inference System (Critical)
**Location**: `backend/src/schema_inference/` - This is a modular package that automatically infers schemas from bronze files.

**Key Pattern**: Never read parquet files with Spark streaming directly - use batch processing:
```python
# ❌ Wrong - causes "Schema must be specified" error
stream = spark.readStream.parquet(path)

# ✅ Correct - use rate trigger for periodic processing
stream = spark.readStream.format("rate").trigger(processingTime="30 seconds")
```

### 7. Data Layer Patterns
- **Bronze**: Raw sensor data in `s3a://lake/bronze/ingestion_id=*/date=*/hour=*/*.parquet`
- **Silver**: Normalized data via Spark enrichment pipeline
- **Gold**: Aggregated data and alerts stored in Neo4j
- **Schema Storage**: SQLite database with `SchemaInfo` and `SchemaInferenceLog` tables

## Dev Workflow (Windows PowerShell)

### Start Development Environment
```powershell
# Full development environment with port-forwarding
skaffold dev --trigger=polling --watch-poll-interval=5000 --default-repo=localhost:5000/soam

# If using profiles (check skaffold.yaml for available profiles)
skaffold dev -p push --default-repo=localhost:5000/soam
```

### Clean Development Environment
```powershell
# Stop Skaffold and clean up
skaffold delete

# Clean Docker images (uses project-specific cleanup script)
.\utils\cleanup-images.ps1

# Reset Kubernetes resources if needed
kubectl delete all --all
```

## Run/Debug Single Service

### Local Development (with pipenv)
```powershell
# Backend
cd backend
pipenv install
pipenv shell
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend  
cd frontend
npm install
npm run dev  # Runs on port 3000

# Ingestor
cd ingestor
pipenv install
pipenv shell
python src/main.py
```

### Cluster Deployment (Single Service)
```powershell
# Build and deploy single service
skaffold build -t latest backend
kubectl rollout restart statefulset/backend

# Check deployment status
kubectl get pods -w
kubectl describe pod <pod-name>
```

## Port-Forward + API Probing

### Port Forwarding (Auto-configured in skaffold.yaml)
```powershell
# Manual port-forwards if needed
kubectl port-forward svc/backend-external 8000:8000
kubectl port-forward svc/frontend 3000:3000  
kubectl port-forward svc/ingestor 8001:8001
kubectl port-forward svc/neo4j 7474:7474
kubectl port-forward svc/minio 9000:9000 9090:9090
kubectl port-forward svc/soam-spark-master-svc 8080:80
```

### API Health Checks
```powershell
# Backend health
curl -s http://localhost:8000/api/troubleshooting/health | ConvertFrom-Json
curl -s http://localhost:8000/api/ready | ConvertFrom-Json

# API documentation
curl -s http://localhost:8000/docs  # FastAPI Swagger UI
curl -s http://localhost:8000/openapi.json | ConvertFrom-Json | Select-Object -ExpandProperty paths

# Test API endpoints
curl -s http://localhost:8000/api/devices | ConvertFrom-Json
curl -s http://localhost:8000/api/dashboard/tiles | ConvertFrom-Json
curl -s http://localhost:8000/api/minio/buckets | ConvertFrom-Json

# Schema inference APIs
curl -s http://localhost:8000/api/schema/ | ConvertFrom-Json
curl -s http://localhost:8000/api/schema/stream/status | ConvertFrom-Json
```

### Service-Specific Probes
```powershell
# Ingestor health
curl -s http://localhost:8001/health | ConvertFrom-Json

# Neo4j browser
Start-Process http://localhost:7474

# MinIO console  
Start-Process http://localhost:9090

# Spark UI
Start-Process http://localhost:8080
```

## Logs & Troubleshooting

### Pod Logs
```powershell
# Service logs
kubectl logs -f statefulset/backend
kubectl logs -f deployment/ingestor  
kubectl logs -f deployment/frontend
kubectl logs -f statefulset/neo4j

# Previous container logs (for crashloop debugging)
kubectl logs backend-0 --previous

# Multi-container logs
kubectl logs backend-0 -c backend
```

### Resource Status
```powershell
# Pod status and events
kubectl get pods -o wide
kubectl describe pod backend-0
kubectl get events --sort-by=.metadata.creationTimestamp

# Resource usage
kubectl top pods
kubectl top nodes

# PVC status (for stateful services)
kubectl get pvc
kubectl describe pvc backend-db-pvc
```

### Common Issues & Fixes
```powershell
# Image pull issues
kubectl describe pod <pod-name> | Select-String "Failed"
docker images | Select-String "backend|frontend|ingestor"

# Restart deployments
kubectl rollout restart statefulset/backend
kubectl rollout restart deployment/ingestor

# Check service endpoints
kubectl get endpoints
kubectl describe service backend-external

# Debug networking
kubectl exec -it backend-0 -- /bin/bash
# Inside pod: curl neo4j:7474, curl minio:9000, etc.
```

## Code Conventions

### Python (Backend/Ingestor) - MANDATORY Patterns
```powershell
# Use pipenv for all Python operations
cd backend
pipenv install --dev
pipenv shell

# Code formatting & linting (add to Pipfile dev-packages as needed)
# black src/
# flake8 src/
# mypy src/

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
from src.api.response_utils import success_response, list_response, not_found_error, bad_request_error, internal_server_error

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

### Error Handling & Logging
```python
import logging
logger = logging.getLogger(__name__)

# Structured logging with emojis for quick scanning
logger.info("✅ Operation completed successfully")
logger.error("❌ Operation failed")
logger.warning("⚠️ Potential issue detected")
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
```

### Frontend
```powershell
cd frontend
npm run lint
npm run build
npm run preview
```

### Project Structure
- `/api/` - FastAPI routers grouped by domain (health, devices, minio, etc.)
- `/services/` - Business logic services
- `/database/` - SQLAlchemy models and database utilities  
- `/schema_inference/` - Dedicated package for schema management
- `/spark/` - Spark streaming and enrichment components
- `/neo4j/` - Graph database operations

## Feature Checklist

When implementing new features, always:

1. **API Development**:
   - Add router to appropriate `/api/` module
   - Use dependency injection pattern (see `dependencies.py`)
   - Include proper error handling and logging
   - Add OpenAPI documentation with response models

2. **Database Changes**:
   - Update SQLAlchemy models in `/database/models.py`
   - Add migration logic in `main.py` startup
   - Test with both SQLite (dev) and production setup

3. **Spark Integration**:
   - Use schema inference package for data schemas
   - Add enrichment logic to `/spark/enrichment/`
   - Consider streaming vs batch processing needs

4. **Frontend Integration**:
   - Update TypeScript interfaces in `/frontend/src/types/`
   - Add API calls to service modules
   - Use React Bootstrap for consistent styling

5. **Testing & Deployment**:
   - Test locally with `pipenv shell` and manual API calls
   - Test in cluster with port-forwarding
   - Check logs for errors: `kubectl logs -f statefulset/backend`
   - Verify frontend integration at `http://localhost:3000`

## Implementation Standards Checklist

**Before submitting any code, verify:**

### ✅ Dependency Injection
- [ ] Uses type aliases: `SparkManagerDep`, `Neo4jManagerDep`, `ConfigDep`, `MinioClientDep`
- [ ] Follows centralized DI pattern from `dependencies.py`
- [ ] No direct instantiation of services in endpoints

### ✅ Error Handling
- [ ] All error functions use `raise error_function()` pattern
- [ ] Database rollback in all exception handlers
- [ ] Specific error types used (not generic `HTTPException`)

### ✅ Logging
- [ ] Uses `get_logger(__name__)` for logger creation
- [ ] Emoji prefixes: ✅ ❌ ⚠️ 🔍
- [ ] Context included in business logic logs (user, operation details)

### ✅ Response Models
- [ ] `response_model=ApiResponse[T]` or `ApiListResponse[T]` specified
- [ ] Generic typing used for type safety
- [ ] Meaningful success messages included

### ✅ Code Organization
- [ ] Imports organized: stdlib → FastAPI → SQLAlchemy → src modules
- [ ] Router endpoints ordered: GET → POST → PATCH → DELETE
- [ ] Database operations include input validation and user context

## Safe Ops Rules

### NEVER (without confirmation):
- `kubectl delete` on production-like resources
- `docker system prune -a` (use project cleanup script instead)
- Modify StatefulSet volumes without data backup
- Change Spark cluster configuration without understanding impact
- Run skaffold on another terminal. I'm using another terminal for hot reloading.
- Duplicate code that could be reused
- Use `readStream.parquet()` without schema specification
- Use blocking commands in CLI, like `kubectl logs -f statefulset/backend`
- Try to restart the pods. Skaffold dev is handling this automatically.

### ALWAYS:
- Show commands before execution in destructive operations
- Use `kubectl describe` and `kubectl logs` for investigation first
- Test API changes with curl/PowerShell before frontend integration
- Check resource limits when adding new containers
- Use `pipenv shell` before running Python scripts
- Verify port-forwarding is active before API testing
- Scan uncommitted changes with `git status` to understand the current state.
- Clean up unused code and dependencies.
- Use dependency injection pattern for new endpoints
- Test schema changes with `/api/schema/stream/status` endpoint
- Use PowerShell for CLI commands
- Use explicit error raising: `raise error_function()`
- Include database rollback in exception handlers
- Use emojis in logging for quick visual scanning
- Specify response models with generic typing
- Use absolute paths when running scripts. This ensures the command won't fail because of relative path issues.

## AI Copilot Integration

**Feature**: Natural language → SQL computation generation using Azure OpenAI
**Config**: Set `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY`, `AZURE_OPENAI_API_VERSION`
**Location**: `backend/src/copilot/` - includes context analysis and computation generation

## Data Processing Flow Understanding

1. **Ingestion**: MQTT sensors → `ingestor` → MinIO bronze layer (partitioned by ingestion_id/date/hour)
2. **Schema Inference**: `SchemaInferenceStream` runs every 30s, discovers new parquet files, infers schemas → SQLite
3. **Enrichment**: Spark reads bronze → applies normalization rules → writes silver/gold layers
4. **Normalization**: Uses `SchemaService` for dynamic field mapping based on inferred schemas
5. **Analytics**: Neo4j stores graph relationships, dashboard APIs serve aggregated data

## Templates/Snippets

### Commit Messages
```
feat: add device management API endpoints
fix: resolve schema inference memory leak  
docs: update API documentation for dashboard tiles
refactor: extract schema logic to dedicated package
```

### PowerShell API Testing Template
```powershell
# Test new API endpoint
$response = Invoke-RestMethod -Uri "http://localhost:8000/api/your-endpoint" -Method GET
$response | ConvertTo-Json -Depth 3

# POST with JSON body
$body = @{ key = "value" } | ConvertTo-Json
$response = Invoke-RestMethod -Uri "http://localhost:8000/api/endpoint" -Method POST -Body $body -ContentType "application/json"
```

### FastAPI Router Template
```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.api.models import ApiResponse, ApiListResponse
from src.api.response_utils import success_response, not_found_error, bad_request_error, internal_server_error
from src.api.dependencies import SparkManagerDep, Neo4jManagerDep, ConfigDep
from src.database.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/feature", tags=["feature"])

@router.get("/items", response_model=ApiListResponse[ItemResponse])
def list_items(db: Session = Depends(get_db)):
    try:
        items = db.query(Item).all()
        return list_response([item.to_dict() for item in items], "Items retrieved successfully")
    except Exception as e:
        logger.error("❌ Error listing items: %s", e)
        raise internal_server_error("Failed to retrieve items", str(e))

@router.post("/items", response_model=ApiResponse[ItemResponse])
def create_item(payload: ItemCreate, db: Session = Depends(get_db)):
    try:
        if not payload.created_by or not payload.created_by.strip():
            raise bad_request_error("User information required (created_by)")
            
        item = Item(**payload.dict())
        db.add(item)
        db.commit()
        db.refresh(item)
        
        logger.info("✅ Item created by '%s': %s", payload.created_by, item.name)
        return success_response(item.to_dict(), "Item created successfully")
    except Exception as e:
        logger.error("❌ Error creating item: %s", e)
        db.rollback()
        raise internal_server_error("Failed to create item", str(e))
```

## Glossary

- **SOAM** - Smart Operations and Asset Management (project name)
- **Schema Inference** - Automated detection of data structures from bronze layer files
- **Bronze Layer** - Raw ingested data stored in MinIO (parquet format)
- **Enriched Layer** - Processed data with normalization and metadata
- **Ingestion ID** - Unique identifier for data ingestion batches
- **Union Schema** - Flexible schema supporting multiple sensor data formats
- **Normalization Rules** - Mapping from raw sensor keys to canonical names
- **Fast Schema Provider** - In-memory schema cache for Spark operations
- **MinIO** - S3-compatible object storage for data lake
- **StatefulSet** - Kubernetes workload for stateful services (backend, Neo4j)
- **Port-Forward** - Kubernetes networking to access cluster services locally