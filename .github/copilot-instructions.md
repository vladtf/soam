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

### Backend (Python/FastAPI) - Port 8000
**Main Application Structure:**
- `backend/Dockerfile` - Multi-stage build with Spark/Java dependencies
- `backend/Pipfile` - Python dependencies (pipenv managed)
- `backend/src/main.py` - FastAPI app with lifecycle management and router registration
- `backend/src/middleware.py` - Request ID middleware for request tracing
- `backend/src/logging_config.py` - Structured logging configuration

**API Layer (`backend/src/api/`):**
- `dependencies.py` - **CRITICAL**: Central DI with `@lru_cache()` singletons and type aliases
- `models.py` - Pydantic request/response models with generic types (`ApiResponse[T]`, `ApiListResponse[T]`)
- `response_utils.py` - **MANDATORY**: Unified response utilities (`success_response()`, error functions)
- Core API routers:
  - `device_routes.py` - Device/sensor management with Neo4j integration
  - `dashboard_tiles_routes.py` - User-defined dashboard tiles with time series support
  - `minio_routes.py` - MinIO bucket/object management and data access
  - `health_routes.py` - Health checks and system status
  - `feedback_routes.py` - User feedback collection
  - `error_routes.py` - Client error tracking and analytics
  - `normalization_routes.py` - Data normalization rule management
  - `normalization_preview_routes.py` - Schema normalization preview
  - `config_routes.py` - System configuration endpoints
  - `settings_routes.py` - User settings management
  - `troubleshooting.py` - Advanced diagnostics and pipeline tracing
- `routers/schema.py` - Schema inference stream management

**Business Logic Layer:**
- `backend/src/computations/` - SQL computation engine with AI copilot integration:
  - `computation_routes.py` - CRUD operations for saved computations
  - `service.py` - Core computation execution service
  - `executor.py` - SQL query executor with Spark integration
  - `validation.py` - SQL query validation and security
  - `sources.py` - Data source discovery and schema introspection
  - `examples.py` - Pre-built computation examples
- `backend/src/copilot/` - AI-powered natural language to SQL conversion:
  - `copilot_routes.py` - AI copilot API endpoints
  - `copilot_service.py` - Azure OpenAI integration for SQL generation
- `backend/src/services/` - Cross-cutting business services:
  - `ingestor_schema_client.py` - Client for fetching metadata from ingestor service
  - `normalization_preview.py` - Schema normalization preview logic

**Data & Storage Layer:**
- `backend/src/database/` - SQLAlchemy ORM and database management:
  - `database.py` - Database connection, session management, and initialization
  - `models.py` - Core SQLAlchemy models (Feedback, NormalizationRule, ClientError, Settings, etc.)
- `backend/src/minio/` - Object storage service integration
- `backend/src/neo4j/` - Graph database operations:
  - `neo4j_manager.py` - Core Neo4j connection and CRUD operations
  - `building_routes.py` - Building/location management API

**Spark & Analytics Layer:**
- `backend/src/spark/` - Apache Spark integration for stream processing:
  - `spark_manager.py` - **CRITICAL**: Main Spark coordinator with stream lifecycle management
  - `session.py` - `SparkSessionManager` with optimized configuration
  - `spark_routes.py` - Spark cluster management API
  - `streaming.py` - `StreamingManager` for stream orchestration
  - `data_access.py` - `DataAccessManager` for bronze/silver/gold layer access
  - `diagnostics.py` - Data pipeline diagnostics and troubleshooting
  - `enrichment/` - Data enrichment pipeline:
    - `enrichment_manager.py` - Main enrichment orchestrator
    - `batch_processor.py` - Batch processing logic for file-based ingestion
    - `union_schema.py` - Dynamic schema handling for multi-source data
    - `device_filter.py` - Device-based data filtering
    - `cleaner.py` - Data cleaning and validation
    - `usage_tracker.py` - Resource usage monitoring

**Utilities (`backend/src/utils/`):**
- `api_utils.py` - **MANDATORY**: API decorators for error handling (`@handle_api_errors`)
- `response_utils.py` - Response formatting utilities
- `logging.py` - Emoji-based structured logging (`get_logger()`)
- `database_utils.py` - Database utilities and error handling
- `settings_manager.py` - Application settings management
- `spark_utils.py` - Spark-specific utilities
- `validation.py` - Input validation utilities

### Ingestor Service (Python/FastAPI) - Port 8001
**Modular Data Ingestion Platform:**
- `ingestor/src/main.py` - FastAPI app with connector lifecycle management
- `ingestor/src/middleware.py` - Request tracking middleware
- `ingestor/src/config.py` - Ingestor-specific configuration

**API Layer (`ingestor/src/api/`):**
- `dependencies.py` - DI container with Prometheus metrics and singleton services
- `routers/` - API endpoint organization:
  - `health.py` - Health checks, readiness probes, and Prometheus metrics
  - `data.py` - Legacy data access API (partition buffers)
  - `metadata.py` - Schema metadata and data quality metrics
  - `data_sources.py` - **NEW**: Dynamic data source management API

**Connector Architecture (`ingestor/src/connectors/`):**
- `base.py` - **CRITICAL**: Abstract base connector with standardized `DataMessage` format
- `mqtt_connector.py` - MQTT broker integration with auto-reconnection
- `rest_api_connector.py` - REST API polling connector with configurable intervals

**Services Layer (`ingestor/src/services/`):**
- `data_source_service.py` - **CRITICAL**: Registry and manager for pluggable data sources:
  - `DataSourceRegistry` - Type registration and discovery
  - `DataSourceManager` - Instance lifecycle management
  - Support for MQTT, REST API, and extensible connector types

**Storage & Metadata:**
- `ingestor/src/storage/minio_client.py` - MinIO client for bronze layer storage
- `ingestor/src/metadata/service.py` - Metadata extraction and schema evolution tracking
- `ingestor/src/database/` - SQLAlchemy models for data source configuration

**Utilities:**
- `ingestor/src/utils/timestamp_utils.py` - Timestamp parsing and standardization

### Frontend (React/TypeScript) - Port 3000
**Application Architecture:**
- `frontend/src/main.tsx` - React app entry point with context providers
- `frontend/src/App.tsx` - Main app component with routing
- `frontend/src/config.ts` - **CRITICAL**: Configuration management with dynamic loading
- `frontend/public/config/config.json` - Runtime configuration (backendUrl, ingestorUrl)

**Context & State Management (`frontend/src/context/`):**
- `ConfigContext.tsx` - Global configuration context with dynamic loading

**API Integration (`frontend/src/api/`):**
- `backendRequests.tsx` - **COMPREHENSIVE**: All backend and ingestor API calls with TypeScript interfaces
  - Backend APIs: computations, dashboard tiles, devices, troubleshooting
  - Ingestor APIs: data sources, metadata, health monitoring
  - Copilot APIs: AI-powered SQL generation

**Component Architecture (`frontend/src/components/`):**
**Core Dashboard Components:**
- `DashboardGrid.tsx` - React-grid-layout integration with drag & drop
- `DashboardTile.tsx` - Visualization component (table/stat/timeseries)
- `TileWithData.tsx` - **CRITICAL**: Data fetching, auto-refresh, and chart rendering
- `TileModal.tsx` - Tile creation/editing with live preview
- `DashboardHeader.tsx` - Dashboard controls and settings

**Data Visualization:**
- `TemperatureChart.tsx` - Time series temperature visualization
- `StatisticsCards.tsx` - System metrics display
- `SparkApplicationsCard.tsx` - Spark cluster status
- `TemperatureAlertsCard.tsx` - Real-time alert display
- `EnrichmentStatusCard.tsx` - Data pipeline status

**Data Management:**
- `sensor-data/` - Sensor data browsing components
- `computations/` - SQL computation management UI
- `pipeline/` - Data pipeline monitoring components

**Utility Components:**
- `ErrorBoundary.tsx` - Global error handling
- `MetadataViewer.tsx` - JSON data inspector
- `ThemedReactJson.tsx` - Styled JSON viewer
- `WithTooltip.tsx` - Reusable tooltip wrapper

**Pages (`frontend/src/pages/`):**
- `DashboardPage.tsx` - **MAIN**: Modular dashboard with user-defined tiles
- `DataPipelinePage.tsx` - Spark streaming monitoring
- `DataSourcesPage.tsx` - Ingestor data source management
- `MinioBrowserPage.tsx` - Object storage browser
- `MetadataPage.tsx` - Schema metadata explorer
- `TroubleshootingPage.tsx` - Advanced diagnostics interface
- `SettingsPage.tsx` - Application settings
- `OntologyPage.tsx` - Neo4j graph visualization

**Type Definitions (`frontend/src/types/`):**
- `dataSource.ts` - TypeScript interfaces for modular data source system
- `imports.d.ts` - Module declarations for external libraries

**Utilities (`frontend/src/utils/`):**
- `timeUtils.ts` - **CRITICAL**: Time formatting for refresh intervals and relative time display

### Supporting Services
- `simulator/` - IoT device simulators (temperature, air quality, smart bins, traffic)
- `rest-api-simulator/` - REST API endpoint simulator for testing
- `mosquitto/` - MQTT broker configuration and persistence
- `neo4j/` - Graph database with ontology initialization
- `grafana/` - Monitoring dashboards with Prometheus integration
- `prometheus/` - Metrics collection and monitoring

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

### 6. Modular Dashboard System (CRITICAL)
**Pattern**: Component-based architecture with time series chart support and auto-refresh

**Location**: Frontend dashboard system is fully modularized into reusable components:

```typescript
// Core dashboard components
frontend/src/components/TileWithData.tsx      - Data fetching, refresh logic, chart rendering
frontend/src/components/TileModal.tsx         - Tile creation/editing with live preview
frontend/src/components/DashboardTile.tsx     - Chart/table/stat visualization component
frontend/src/components/DashboardGrid.tsx     - Grid layout with drag-and-drop
frontend/src/components/DashboardHeader.tsx   - Dashboard controls and settings
frontend/src/utils/timeUtils.ts              - Time formatting utilities

// Backend API support
backend/src/api/dashboard_tiles_routes.py    - CRUD operations for user-defined tiles
```

**Key Features**:
- **Time Series Support**: LineChart with recharts, configurable time/value fields
- **Auto-Refresh**: Configurable intervals with throttling and concurrent request prevention
- **Live Preview**: Real-time tile preview during configuration
- **Drag & Drop**: React-grid-layout integration for dashboard customization
- **Type Safety**: Full TypeScript integration with backend response models

**Critical Implementation Details**:
```typescript
// TileWithData.tsx - Proper useEffect dependency management to prevent infinite loops
useEffect(() => {
  // Data fetching logic
}, [tile.id, tsKey]); // ❌ NEVER include 'rows' in dependencies

// Auto-refresh with minimum interval safety
const safeRefreshInterval = Math.max(refreshIntervalMs, 15000); // Minimum 15 seconds

// Time series configuration in tile.config
{
  "timeField": "time_start",      // X-axis field
  "valueField": "avg_temperature", // Y-axis field  
  "chartHeight": 250,             // Chart height in pixels
  "refreshInterval": 30000,       // Refresh interval in milliseconds
  "autoRefresh": true             // Enable/disable auto-refresh
}
```

**Backend Examples**: Dashboard tiles with time series support:
```python
# Time series tile example in dashboard_tiles_routes.py
{
    "id": "timeseries-chart",
    "title": "Time series chart", 
    "tile": {
        "name": "Time Series Chart",
        "computation_id": cid,
        "viz_type": "timeseries",
        "config": {
            "timeField": "time_start",
            "valueField": "avg_temperature", 
            "chartHeight": 250,
            "refreshInterval": 30000,
            "autoRefresh": True
        }
    }
}
```

### 7. Modular Ingestor Architecture (NEW SYSTEM)
**Location**: `ingestor/` - Complete rewrite with pluggable connector architecture

**Key Innovation**: Dynamic data source registration with standardized connector interface:
```python
# Base connector contract in ingestor/src/connectors/base.py
@dataclass
class DataMessage:
    """Standardized message format from any connector type."""
    data: Dict[str, Any]           # Raw sensor data
    metadata: Dict[str, Any]       # Source metadata
    source_id: str                 # Ingestion ID for partitioning
    timestamp: str                 # ISO timestamp
    raw_payload: Optional[str] = None  # Original message for debugging

class BaseDataConnector(ABC):
    """Abstract base for all data connectors."""
    @abstractmethod
    async def start(self) -> None: pass
    @abstractmethod
    async def stop(self) -> None: pass
    @abstractmethod
    async def get_health(self) -> ConnectorHealthResponse: pass
```

**Data Source Management**:
```python
# Dynamic registration in ingestor/src/services/data_source_service.py
class DataSourceRegistry:
    """Registry for pluggable connector types."""
    CONNECTOR_TYPES = {
        "mqtt": MQTTConnector,
        "rest_api": RestApiConnector,
        # Easily extensible for new connector types
    }

class DataSourceManager:
    """Manages individual data source instances with lifecycle control."""
    # Auto-restart, health monitoring, metrics collection
```

**Critical Data Flow**: Connector → `DataMessage` → Partition Buffer → MinIO Bronze Layer
- All connectors output standardized `DataMessage` format
- Partition buffers maintain compatibility with legacy `/api/partitions` endpoint
- MinIO client handles bronze layer storage with ingestion_id partitioning
- Metadata service extracts schemas and tracks data quality metrics

### 8. Comprehensive Troubleshooting System (ADVANCED)
**Location**: `backend/src/api/troubleshooting.py` and `backend/src/spark/diagnostics.py`

**Advanced Pipeline Diagnostics**:
```python
# Field-level diagnostic tracing
@router.post("/diagnose-field", response_model=ApiResponse[FieldDiagnosticResult])
async def diagnose_field(
    sensor_id: str,
    field_name: str, 
    minutes_back: int,
    ingestion_id: Optional[str] = None
):
    """Trace a specific field through the entire pipeline: Bronze → Silver → Gold"""
    # Returns detailed pipeline trace with schema evolution and transformation history
```

**Pipeline Tracing Features**:
- End-to-end data lineage tracking from ingestion to dashboard
- Schema evolution detection with compatibility analysis
- Data quality metrics at each pipeline stage
- Performance bottleneck identification
- Missing data gap analysis

### 9. Real-time Dashboard System with Auto-refresh (COMPREHENSIVE)
**Location**: `frontend/src/components/TileWithData.tsx` and dashboard ecosystem

**Smart Refresh Logic**:
```typescript
// Critical auto-refresh implementation
useEffect(() => {
  // Data fetching logic with concurrency protection
}, [tile.id, tsKey]); // ❌ NEVER include 'rows' in dependencies to prevent loops

// Minimum refresh interval safety
const safeRefreshInterval = Math.max(refreshIntervalMs, 15000); // Minimum 15 seconds

// Time series configuration in tile.config
{
  "timeField": "time_start",         // X-axis field for charts
  "valueField": "avg_temperature",   // Y-axis field for charts
  "chartHeight": 250,                // Chart height in pixels
  "refreshInterval": 30000,          // Auto-refresh interval in ms
  "autoRefresh": true                // Enable/disable auto-refresh
}
```

**Dashboard Architecture**:
- **TileWithData.tsx**: Handles data fetching, caching, and auto-refresh with concurrency protection
- **DashboardTile.tsx**: Pure visualization component (table/stat/timeseries)
- **DashboardGrid.tsx**: React-grid-layout integration with drag & drop
- **TileModal.tsx**: Tile creation with live preview and validation
- Time series charts use recharts with responsive containers
- Automatic data caching to prevent redundant API calls
- User-configurable refresh intervals with minimum safety limits

### 10. AI Copilot Integration (AZURE OPENAI)
**Location**: `backend/src/copilot/` - Natural language to SQL conversion

**Features**:
- Context-aware SQL generation from natural language
- Schema introspection for accurate table/field references
- Query validation and security filtering
- Integration with computation engine for execution
- Configuration via Azure OpenAI API (endpoint, key, version)

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

## Core Service Architecture

### Backend Service Layer
**Key Services & Managers (All Singleton via DI):**

- `SparkManager` (`backend/src/spark/spark_manager.py`) - **CRITICAL**: Coordinates all Spark operations
  - `SparkSessionManager` - Optimized Spark session with S3A configuration  
  - `StreamingManager` - Manages streaming query lifecycle
  - `EnrichmentManager` - Orchestrates data enrichment pipeline
  - `DataAccessManager` - Provides bronze/silver/gold layer access

- `Neo4jManager` (`backend/src/neo4j/neo4j_manager.py`) - Graph database operations
  - Building/location management with spatial queries
  - Ontology-based data relationships
  - Auto-provisioning of initial graph data

- `ComputationService` (`backend/src/computations/service.py`) - SQL execution engine
  - Dynamic query execution on Spark
  - Schema introspection and validation
  - Integration with AI copilot for query generation

- `CopilotService` (`backend/src/copilot/copilot_service.py`) - Azure OpenAI integration
  - Natural language to SQL conversion
  - Context-aware schema analysis
  - Query optimization recommendations

### Ingestor Service Architecture
**Registry & Management Pattern:**

- `DataSourceRegistry` - Type discovery and connector registration
- `DataSourceManager` - Instance lifecycle management with auto-restart
- `MetadataService` - Schema extraction and data quality tracking
- `MinioClient` - Bronze layer storage with partitioning strategy

### Database Models & Storage
**Core SQLAlchemy Models (`backend/src/database/models.py`):**

```python
class NormalizationRule(Base):
    """User-defined schema normalization rules."""
    # Maps raw sensor keys to canonical field names
    # Supports global and ingestion-specific rules
    
class Feedback(Base):
    """User feedback and bug report collection."""
    
class ClientError(Base):
    """Frontend error tracking and analytics."""
    
class Settings(Base):
    """Application configuration and user preferences."""
    
class DashboardTile(Base):
    """User-defined dashboard tile definitions."""
    # Stores computation queries, visualization config, layouts
```

**Ingestor Models (`ingestor/src/database/models.py`):**
```python
class DataSourceType(Base):
    """Registered connector types (MQTT, REST API, etc.)."""
    
class DataSource(Base):
    """Individual data source instances with configuration."""
    
class DataSourceMetric(Base):
    """Performance and health metrics collection."""
```

## Data Processing Flow Understanding

1. **Ingestion**: MQTT/REST → Ingestor Connectors → `DataMessage` standardization → MinIO bronze layer
2. **Partitioning**: Data partitioned by `ingestion_id=*/date=*/hour=*/*.parquet` for efficient querying
3. **Schema Inference**: Spark batch jobs analyze new bronze files → SQLAlchemy schema storage
4. **Enrichment**: Spark streaming reads bronze → applies normalization rules → writes silver/gold layers
5. **Normalization**: User-defined rules map raw sensor keys to canonical field names
6. **Analytics**: Neo4j stores enriched relationships, dashboard APIs serve computed aggregations
7. **Monitoring**: Prometheus metrics collection, Grafana dashboards, health endpoints

### Critical Data Layer Patterns
- **Bronze**: Raw sensor data with original structure preserved
- **Silver**: Normalized data with consistent schema and cleansed values  
- **Gold**: Aggregated insights, alerts, and derived analytics
- **Schema Evolution**: Automatic detection and compatibility analysis
- **Partition Strategy**: Time-based partitioning enables efficient time-range queries

## Component Interaction Patterns

### Backend → Ingestor Communication
- **IngestorSchemaClient** (`backend/src/services/ingestor_schema_client.py`): HTTP client for metadata APIs
- **Data Context Building**: Aggregates schema info from `/api/metadata/datasets` and `/api/metadata/topics`
- **Real-time Schema Updates**: Backend polls ingestor for schema changes during enrichment

### Frontend → Backend API Flow
- **Configuration Loading**: `ConfigContext.tsx` loads runtime config from `/config/config.json`
- **API Abstraction**: `backendRequests.tsx` provides typed interfaces for all backend/ingestor endpoints
- **Dashboard Data Flow**: `TileWithData.tsx` → `previewDashboardTile()` → Computation Service → Spark Query → Results
- **Auto-refresh Safety**: Minimum 15-second intervals with concurrency protection

### Spark Pipeline Orchestration
- **Streaming Manager**: Controls query lifecycle (start/stop/restart) with failure recovery
- **Enrichment Manager**: Coordinates batch processing pipeline for bronze → silver transformation
- **Data Access Manager**: Provides abstracted access to all data layers (bronze/silver/gold)
- **Schema Integration**: Uses fast schema provider for dynamic schema application during processing

### Data Source Plugin Architecture
- **Registry Pattern**: `DataSourceRegistry.CONNECTOR_TYPES` maps type names to connector classes
- **Lifecycle Management**: `DataSourceManager` handles start/stop/health for all active sources
- **Standardized Output**: All connectors output `DataMessage` format for consistent processing
- **Extensibility**: New connector types register via simple class mapping in registry

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