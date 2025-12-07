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

**Local Development (Skaffold):**
- `skaffold.yaml` - Main dev orchestration, builds 8 services, handles port-forwarding
- `k8s/` - Kubernetes manifests for all services (StatefulSets/Services)
- `spark-values.yaml` - Helm values for Spark cluster deployment
- `utils/cleanup-images.ps1` - PowerShell script for Docker image management

**Azure Cloud Deployment (Terraform):**
- `terraform/` - 2-step Terraform deployment to Azure AKS
  - `terraform/01-azure-infrastructure/` - Azure resources (AKS cluster + ACR container registry)
  - `terraform/02-kubernetes-resources/` - All Kubernetes resources (deployments, services, PVCs, Helm charts)
  - `terraform/deploy.ps1` - **CRITICAL**: Orchestration script for full deployment lifecycle
- `docs/azure-deployment.md` - Comprehensive Azure deployment guide with troubleshooting

### Backend (Python/FastAPI) - Port 8000
**Main Application Structure:**
- `backend/Dockerfile` - Multi-stage build with Spark/Java dependencies
- `backend/Pipfile` - Python dependencies (pipenv managed)
- `backend/src/main.py` - FastAPI app with lifecycle management and router registration
- `backend/src/middleware.py` - Request ID middleware for request tracing
- `backend/src/logging_config.py` - Structured logging configuration

**Authentication Layer (`backend/src/auth/`):** - **NEW: JWT-based multi-role authentication**
- `config.py` - `AuthSettings` dataclass with JWT configuration (SECRET_KEY, token expiration, default admin)
- `security.py` - Password hashing (bcrypt), JWT token creation/decoding (python-jose)
- `dependencies.py` - **CRITICAL**: Auth dependencies (`get_current_user`, `require_roles`, `require_admin`, `require_user_or_admin`)
- `routes.py` - Full auth API: login, register, refresh, logout, user management (CRUD)
- `init_admin.py` - Default admin user initialization with all roles

**Auth System Features:**
- Multi-role support: Users can have multiple roles stored as JSON list (e.g., `["admin", "user", "viewer"]`)
- JWT access tokens (30min) + refresh tokens (7 days)
- Role-based authorization: `require_roles()` checks if user has ANY of the specified roles
- User model: `roles` field is JSON list, with helper methods `get_roles()`, `has_role()`, `has_any_role()`
- Password hashing: bcrypt via passlib (bcrypt==4.0.1 pinned for compatibility)

**API Layer (`backend/src/api/`):**
- `dependencies.py` - **CRITICAL**: Central DI with `@lru_cache()` singletons and type aliases
- `models.py` - Pydantic request/response models with generic types (`ApiResponse[T]`, `ApiListResponse[T]`)
- `response_utils.py` - **MANDATORY**: Unified response utilities (`success_response()`, error functions)
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
  - `spark_models.py` - Pydantic models for Spark API responses
  - `streaming.py` - `StreamingManager` for stream orchestration
  - `data_access.py` - `DataAccessManager` for bronze/silver/gold layer access
  - `diagnostics.py` - Data pipeline diagnostics
  - `diagnostics_enhanced.py` - Enhanced diagnostics with detailed tracing
  - `master_client.py` - Spark master client for cluster communication
  - `config.py` - Spark configuration settings
  - `enrichment/` - Data enrichment pipeline:
    - `enrichment_manager.py` - Main enrichment orchestrator
    - `batch_processor.py` - Batch processing logic for file-based ingestion
    - `union_schema.py` - Dynamic schema handling for multi-source data
    - `device_filter.py` - Device-based data filtering
    - `cleaner.py` - Data cleaning and validation
    - `usage_tracker.py` - Resource usage monitoring
    - `value_transformer.py` - Value transformation logic

**Utilities (`backend/src/utils/`):**
- `api_utils.py` - **MANDATORY**: API decorators for error handling (`@handle_api_errors`)
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
- `AuthContext.tsx` - **NEW**: JWT-based authentication context with multi-role support
- `ConfigContext.tsx` - Global configuration context with dynamic loading
- `ErrorContext.tsx` - Error handling and display context
- `ThemeContext.tsx` - Theme management (light/dark mode)

**API Integration (`frontend/src/api/`):**
- `backendRequests.tsx` - **COMPREHENSIVE**: All backend and ingestor API calls with TypeScript interfaces
  - Backend APIs: computations, dashboard tiles, devices
  - Ingestor APIs: data sources, metadata, health monitoring
  - Copilot APIs: AI-powered SQL generation
  - Auth APIs: login, register, refresh, user management

**Component Architecture (`frontend/src/components/`):**
**Core Dashboard Components:**
- `DashboardGrid.tsx` - React-grid-layout integration with drag & drop
- `DashboardTile.tsx` - Visualization component (table/stat/timeseries)
- `TileWithData.tsx` - **CRITICAL**: Data fetching, auto-refresh, and chart rendering
- `TileModal.tsx` - Tile creation/editing with live preview
- `DashboardHeader.tsx` - Dashboard controls and settings

**Data Visualization & Status Cards:**
- `TemperatureChart.tsx` - Time series temperature visualization
- `StatisticsCards.tsx` - System metrics display
- `SparkApplicationsCard.tsx` - Spark cluster status
- `TemperatureAlertsCard.tsx` - Real-time alert display
- `EnrichmentStatusCard.tsx` - Data pipeline status
- `ValueTransformationStatusCard.tsx` - Transformation rule status

**Pipeline Components (`pipeline/`):**
- `PipelineNavigationSidebar.tsx` - Navigation sidebar with rule counts
- `PipelineOverview.tsx` - Pipeline status overview card
- `PipelineOverviewTab.tsx` - Overview tab content
- `SensorDataTab.tsx` - Sensor data browsing tab
- `NormalizationTab.tsx` - Normalization rules management tab
- `NormalizationRulesSection.tsx` - Normalization rules table and CRUD
- `ValueTransformationsTab.tsx` - **COMPLETE**: Value transformation rules management with full CRUD operations, field selection, and examples
- `ComputationsTab.tsx` - SQL computations tab
- `ComputationsSection.tsx` - Computations table and management
- `DevicesTab.tsx` - Device registration and management tab
- `SchemaConfiguration.tsx` - Schema configuration component

**Computations Components (`computations/`):**
- `ComputationsTable.tsx` - Computations list and management table
- `CopilotAssistant.tsx` - AI-powered SQL generation assistant
- `DefinitionValidator.ts` - SQL definition validation utilities
- `PreviewModal.tsx` - Computation result preview modal

**Sensor Data Components (`sensor-data/`):**
- `DataViewer.tsx` - Sensor data viewer component
- `DevicesTableCard.tsx` - Devices table card component
- `EnrichmentDiagnosticCard.tsx` - Enrichment diagnostic card
- `RegisterDeviceCard.tsx` - Device registration card
- `TopControlsBar.tsx` - Top controls bar for sensor data

**Navigation & Layout:**
- `AppNavbar.tsx` - Main application navigation bar with auth integration
- `PageHeader.tsx` - Reusable page header component
- `Footer.tsx` - Application footer
- `ProtectedRoute.tsx` - **NEW**: Role-based route protection for authenticated routes

**Utility & Support Components:**
- `ErrorBoundary.tsx` - Global error handling wrapper
- `withErrorBoundary.tsx` - HOC for error boundary
- `ErrorCenter.tsx` - Error logging and display center
- `DevErrorOverlay.tsx` - Development error overlay
- `ErrorTestComponent.tsx` - Error testing component
- `DebugPanel.tsx` - Debug information panel
- `DebugFloatingButton.tsx` - Floating debug button
- `MetadataViewer.tsx` - JSON data inspector
- `ThemedReactJson.tsx` - Styled JSON viewer with theme support
- `ThemedTable.tsx` - Themed table component
- `WithTooltip.tsx` - Reusable tooltip wrapper
- `DynamicConfigForm.tsx` - Dynamic form configuration
- `DynamicFields.tsx` - Dynamic field rendering
- `NormalizationPreviewModal.tsx` - Normalization preview modal
- `NewBuildingModal.tsx` - New building creation modal
- `OntologyViewer.tsx` - Ontology graph viewer
- `SensorForm.tsx` - Sensor registration form
- `SensorData.tsx` - Sensor data display component
- `TemperatureThresholdModal.tsx` - Temperature threshold configuration modal

**Pages (`frontend/src/pages/`):**
- `Home.tsx` - Landing page with system overview
- `DashboardPage.tsx` - **MAIN**: Modular dashboard with user-defined tiles
- `DataPipelinePage.tsx` - **COMPREHENSIVE**: Unified pipeline management with tabs for sensors, normalization, transformations, computations, and devices
- `DataSourcesPage.tsx` - Ingestor data source management (MQTT, REST API)
- `MinioBrowserPage.tsx` - Object storage browser and file explorer
- `MetadataPage.tsx` - Schema metadata explorer with field statistics
- `SettingsPage.tsx` - Application settings and configuration
- `OntologyPage.tsx` - Neo4j graph visualization and building management
- `FeedbackPage.tsx` - User feedback and bug report collection
- `NewEventsPage.tsx` - Event monitoring and alerts
- `MapPage.tsx` - Geospatial visualization (if enabled)
- `LoginPage.tsx` - **NEW**: Login and registration page with multi-role support

**Utilities (`frontend/src/utils/`):**
- `timeUtils.ts` - **CRITICAL**: Time formatting for refresh intervals and relative time display
- `authUtils.ts` - **NEW**: Authentication utilities (getAuthHeaders)

### Supporting Services
- `simulator/` - IoT device simulators (temperature, air quality, smart bins, traffic)
- `rest-api-simulator/` - REST API endpoint simulator for testing
- `mosquitto/` - MQTT broker configuration and persistence
- `neo4j/` - Graph database with ontology initialization
- `grafana/` - Monitoring dashboards with Prometheus integration
- `prometheus/` - Metrics collection and monitoring

### Documentation
- `docs/azure-deployment.md` - **CRITICAL**: Azure AKS deployment guide with troubleshooting
- `docs/copilot-setup.md` - AI Copilot configuration guide
- `docs/dependability-criteria.md` - System dependability requirements
- `docs/testing-dependability-features.md` - Testing guide for dependability features

## API Endpoints Reference

### Backend Service (Port 8000)

#### Authentication (`/api/auth`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Authenticate user, returns JWT access + refresh tokens |
| POST | `/api/auth/register` | Register new user (default role: USER) |
| POST | `/api/auth/refresh` | Refresh access token using refresh token |
| GET | `/api/auth/me` | Get current authenticated user info |
| POST | `/api/auth/logout` | Logout (client should discard tokens) |
| POST | `/api/auth/change-password` | Change current user's password |
| GET | `/api/auth/users` | List all users (admin only) |
| GET | `/api/auth/users/{user_id}` | Get user by ID (admin only) |
| PATCH | `/api/auth/users/{user_id}` | Update user (admin only) |
| DELETE | `/api/auth/users/{user_id}` | Delete user (admin only) |
| POST | `/api/auth/users/{user_id}/reset-password` | Reset user password (admin only) |
| GET | `/api/auth/test-users` | Get test users for development |

#### Health & Monitoring (`/api`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ready` | Readiness probe (checks Neo4j, Spark, DB) |
| GET | `/api/health` | Health check with component status |

#### Spark Operations (`/api/spark`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/spark/master-status` | Get Spark master status with workers |
| GET | `/api/spark/streams-status` | Get all running Spark streaming queries |
| GET | `/api/spark/average-temperature` | Get streaming average temperature data |
| GET | `/api/spark/temperature-alerts` | Get recent temperature alerts |
| GET | `/api/spark/enrichment-summary` | Get enrichment pipeline summary |
| GET | `/api/spark/test/computation` | Test basic Spark computation |
| GET | `/api/spark/test/sensor-data` | Test Spark access to sensor data |
| GET | `/api/spark/diagnose/enrichment-filtering` | Diagnose enrichment filtering issues |

#### Dashboard Tiles (`/api/dashboard`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/tiles` | List all dashboard tiles with access control |
| POST | `/api/dashboard/tiles` | Create new dashboard tile |
| PATCH | `/api/dashboard/tiles/{tile_id}` | Update dashboard tile |
| DELETE | `/api/dashboard/tiles/{tile_id}` | Delete dashboard tile |
| GET | `/api/dashboard/examples` | Get example tile configurations |
| POST | `/api/dashboard/tiles/{tile_id}/preview` | Preview tile data by ID |
| POST | `/api/dashboard/tiles/preview` | Preview tile with custom config |

#### Computations (`/api/computations`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/computations` | List all saved computations |
| POST | `/api/computations` | Create new computation |
| PATCH | `/api/computations/{comp_id}` | Update computation |
| DELETE | `/api/computations/{comp_id}` | Delete computation |
| GET | `/api/computations/examples` | Get example computations and DSL info |
| GET | `/api/computations/sources` | Get available data sources |
| GET | `/api/computations/schemas` | Get inferred schemas for sources |
| POST | `/api/computations/analyze-sensitivity` | Analyze computation sensitivity |
| POST | `/api/computations/examples/{example_id}/preview` | Preview example computation |

#### AI Copilot (`/api/copilot`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/copilot/generate-computation` | Generate computation from natural language |
| GET | `/api/copilot/context` | Get data context for copilot |
| GET | `/api/copilot/health` | Check copilot service availability |

#### Devices (`/api/devices`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/devices` | List all registered devices |
| POST | `/api/devices` | Register or update device (auth required) |
| PATCH | `/api/devices/{device_id}` | Update device (auth required) |
| DELETE | `/api/devices/{device_id}` | Delete device |

#### Normalization Rules (`/api/normalization`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/normalization` | List all normalization rules |
| POST | `/api/normalization` | Create normalization rule |
| PATCH | `/api/normalization/{rule_id}` | Update normalization rule |
| DELETE | `/api/normalization/{rule_id}` | Delete normalization rule |
| PATCH | `/api/normalization/{rule_id}/toggle` | Toggle rule enabled/disabled |

#### Normalization Preview (`/api/normalization/preview`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/normalization/preview/sample-data` | Get sample raw data for preview |
| POST | `/api/normalization/preview/preview` | Preview normalization on sample data |
| POST | `/api/normalization/preview/compare` | Compare two normalization scenarios |

#### Value Transformations (`/api/value-transformations`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/value-transformations` | List all value transformation rules |
| POST | `/api/value-transformations` | Create transformation rule |
| PATCH | `/api/value-transformations/{rule_id}` | Update transformation rule |
| DELETE | `/api/value-transformations/{rule_id}` | Delete transformation rule |
| PATCH | `/api/value-transformations/{rule_id}/toggle` | Toggle rule enabled/disabled |
| GET | `/api/value-transformations/fields` | Get available fields for transformations |
| GET | `/api/value-transformations/types` | Get available transformation types |
| GET | `/api/value-transformations/examples` | Get transformation examples |

#### MinIO Storage (`/api/minio`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/minio/ls` | List prefix contents |
| GET | `/api/minio/find` | List files recursively with pagination |
| GET | `/api/minio/preview` | Preview Parquet file contents |
| GET | `/api/minio/find-data-files` | Find non-empty data files |
| DELETE | `/api/minio/object` | Delete single object |
| POST | `/api/minio/delete` | Delete multiple objects |
| DELETE | `/api/minio/prefix` | Delete all objects with prefix |

#### Schema Metadata (`/api/schema`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/schema/datasets` | Get all datasets with metadata |
| GET | `/api/schema/datasets/{ingestion_id}` | Get schema for specific dataset |
| GET | `/api/schema/datasets/{ingestion_id}/evolution` | Get schema evolution history |
| GET | `/api/schema/topics` | Get topics summary |
| GET | `/api/schema/context` | Get comprehensive data context |
| GET | `/api/schema/sources` | Get list of available ingestion IDs |

#### Buildings (`/api/buildings`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/buildings` | List all buildings from Neo4j |
| POST | `/api/buildings` | Add new building |
| DELETE | `/api/buildings` | Delete building by name and coordinates |

#### Configuration (`/api/config`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config/schema` | Get current schema configuration |
| GET | `/api/config` | Get comprehensive system configuration |
| GET | `/api/config/features` | Get feature flags and capabilities |

#### Settings (`/api/settings`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings` | List all settings (optionally by category) |
| GET | `/api/settings/{key}` | Get specific setting by key |
| POST | `/api/settings` | Create new setting |
| PATCH | `/api/settings/{key}` | Update setting |
| DELETE | `/api/settings/{key}` | Delete setting |

#### Feedback (`/api/feedback`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/feedback` | List all feedback submissions |
| GET | `/api/feedback/{feedback_id}` | Get specific feedback |
| POST | `/api/feedback` | Submit new feedback |
| DELETE | `/api/feedback/{feedback_id}` | Delete feedback |

#### Client Errors (`/api/errors`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/errors` | List recent client errors |
| POST | `/api/errors` | Report client error |

---

### Ingestor Service (Port 8001)

#### Health & Monitoring (`/api`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ready` | Readiness probe (checks MinIO) |
| GET | `/api/health` | Health check with data source status |
| GET | `/api/metrics` | Prometheus metrics endpoint |

#### Data Access (`/api`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/data` | Get buffered sensor data across all partitions |
| GET | `/api/partitions` | List known ingestion_id partitions |
| GET | `/api/data/{ingestion_id}` | Get buffered data for specific partition |
| GET | `/api/diagnostics/topic-analysis` | Analyze topics and ingestion_ids |

#### Metadata (`/api/metadata`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/metadata/datasets` | Get metadata for all datasets |
| GET | `/api/metadata/datasets/{ingestion_id}` | Get metadata for specific dataset |
| GET | `/api/metadata/datasets/{ingestion_id}/schema` | Get schema for dataset |
| GET | `/api/metadata/datasets/{ingestion_id}/evolution` | Get schema evolution history |
| GET | `/api/metadata/datasets/{ingestion_id}/quality` | Get data quality metrics |
| POST | `/api/metadata/datasets/{ingestion_id}/quality` | Store quality metric |
| GET | `/api/metadata/topics` | Get topics summary |
| GET | `/api/metadata/current` | Get current in-memory metadata |
| GET | `/api/metadata/stats` | Get overall metadata statistics |
| POST | `/api/metadata/cleanup` | Clean up old metadata records |

#### Data Sources (`/api/data-sources`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/data-sources/types` | Get available data source types |
| GET | `/api/data-sources` | List all data sources |
| GET | `/api/data-sources/{source_id}` | Get specific data source |
| POST | `/api/data-sources` | Create new data source |
| PUT | `/api/data-sources/{source_id}` | Update data source |
| DELETE | `/api/data-sources/{source_id}` | Delete data source |
| POST | `/api/data-sources/{source_id}/start` | Start data source |
| POST | `/api/data-sources/{source_id}/stop` | Stop data source |
| POST | `/api/data-sources/{source_id}/restart` | Restart data source |
| GET | `/api/data-sources/{source_id}/health` | Get data source health |
| GET | `/api/data-sources/{source_id}/metrics` | Get data source metrics |

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

### 8. JWT Authentication System (NEW)
**Location**: `backend/src/auth/` - Complete JWT-based multi-role authentication

**Architecture Overview**:
```python
# Auth module structure
backend/src/auth/
├── config.py        # AuthSettings dataclass
├── security.py      # Password hashing & JWT operations
├── dependencies.py  # FastAPI dependencies for route protection
├── routes.py        # Auth API endpoints
└── init_admin.py    # Default admin user initialization
```

**Multi-Role Authorization Pattern**:
```python
from src.auth.dependencies import get_current_user, require_roles, require_admin

# Protect routes with specific roles
@router.get("/admin-only")
async def admin_endpoint(user: User = Depends(require_admin)):
    pass

# Allow multiple roles (user has ANY of the specified roles)
@router.get("/users-or-admins")  
async def protected(user: User = Depends(require_roles(["admin", "user"]))):
    pass

# Just require authentication, any role
@router.get("/authenticated")
async def any_auth(user: User = Depends(get_current_user)):
    pass
```

**Token Management**:
```python
# Access token (short-lived, 30 min)
access_token = create_access_token({"sub": user.username})

# Refresh token (long-lived, 7 days)
refresh_token = create_refresh_token({"sub": user.username})

# Token validation with user lookup
user = await get_current_user(token, db)
```

**User Model with Multi-Role Support**:
```python
class User(Base):
    id: int
    username: str  # Unique
    email: str     # Unique
    password_hash: str
    roles: JSON    # List of roles: ["admin", "user", "viewer"]
    is_active: bool
    created_at: datetime
    
    def get_roles(self) -> List[str]: ...
    def has_role(self, role: str) -> bool: ...
    def has_any_role(self, roles: List[str]) -> bool: ...  # Returns True if user has ANY role
```

**Frontend Authentication Context**:
```typescript
// AuthContext.tsx - Key exports
interface AuthContextType {
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  register: (data: RegisterData) => Promise<void>;
  isAuthenticated: boolean;
  isAdmin: boolean;
  hasRole: (...roles: UserRole[]) => boolean;      // Has ANY of roles
  hasAllRoles: (...roles: UserRole[]) => boolean;  // Has ALL roles
}

// Usage in components
const { user, isAdmin, hasRole, logout } = useAuth();
if (hasRole('admin', 'user')) {
  // User has either admin OR user role
}
```

**Default Credentials**: 
- Username: `admin`, Password: `admin`
- Roles: `["admin", "user", "viewer"]`

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

### Local Development with Skaffold

```powershell
# Full development environment with port-forwarding
skaffold dev --trigger=polling --watch-poll-interval=5000 --default-repo=localhost:5000/soam

# If using profiles (check skaffold.yaml for available profiles)
skaffold dev -p push --default-repo=localhost:5000/soam
```

### Azure Deployment with Terraform

**Full Deployment Workflow:**
```powershell
# 1. Login to Azure
az login
az account set --subscription "your-subscription-id"

# 2. Configure Step 1 variables
cd terraform/01-azure-infrastructure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars - set subscription_id and acr_name

# 3. Run full deployment (infrastructure + images + k8s resources)
cd ..
.\deploy.ps1 -Action deploy

# 4. Check deployment status
.\deploy.ps1 -Action status

# 5. Connect kubectl to AKS
az aks get-credentials --resource-group soam-rg --name soam-aks-cluster
kubectl get pods -n soam
```

**Deploy Script Options:**
```powershell
# Full deployment
.\deploy.ps1 -Action deploy

# Deploy only Azure infrastructure (Step 1)
.\deploy.ps1 -Action deploy -Step 1

# Deploy only Kubernetes resources (Step 2)  
.\deploy.ps1 -Action deploy -Step 2

# Skip image rebuild
.\deploy.ps1 -Action deploy -SkipImages

# Rebuild images only
.\deploy.ps1 -Action images-only

# Destroy everything
.\deploy.ps1 -Action destroy
```

**Terraform Structure:**
- **Step 1** (`terraform/01-azure-infrastructure/`): Creates Azure Resource Group, AKS cluster (3 nodes Standard_DS2_v2), ACR registry, role assignments
- **Step 2** (`terraform/02-kubernetes-resources/`): Deploys all K8s resources - namespace, secrets, PVCs, deployments, services, Helm charts for Spark
- Step 2 auto-receives AKS credentials from Step 1 outputs via `deploy.ps1`

**Critical Azure/Terraform Notes:**
- PVCs use `managed-premium` storage class with `WaitForFirstConsumer` binding mode - PVCs only bind when pods are scheduled
- Frontend nginx listens on port 80 (not 3000)
- Backend and ingestor PVCs have `wait_until_bound = false` to prevent Terraform timeout
- LoadBalancer services can take 2-5 minutes to get external IP

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

### Port Forwarding (Auto-configured in skaffold.yaml for local, manual for AKS)
```powershell
# Local k8s port-forwards (Skaffold handles this automatically)
kubectl port-forward svc/backend-external 8000:8000
kubectl port-forward svc/frontend 3000:3000  
kubectl port-forward svc/ingestor 8001:8001
kubectl port-forward svc/neo4j 7474:7474
kubectl port-forward svc/minio 9000:9000 9090:9090
kubectl port-forward svc/soam-spark-master-svc 8080:80

# Azure AKS port-forwards (with namespace)
kubectl port-forward svc/frontend 3000:80 -n soam           # NOTE: nginx on port 80
kubectl port-forward svc/backend-external 8000:8000 -n soam
kubectl port-forward svc/ingestor-external 8001:8001 -n soam
kubectl port-forward svc/minio 9000:9000 9090:9090 -n soam
kubectl port-forward svc/neo4j 7474:7474 7687:7687 -n soam
kubectl port-forward svc/soam-spark-master-svc 8080:80 -n soam

# Stop all port-forward processes
Get-Process kubectl -ErrorAction SilentlyContinue | Stop-Process
```

### API Health Checks
```powershell
# Backend health
curl -s http://localhost:8000/api/health | ConvertFrom-Json
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
# Service logs (add -n soam for AKS)
kubectl logs -f statefulset/backend
kubectl logs -f deployment/ingestor  
kubectl logs -f deployment/frontend
kubectl logs -f statefulset/neo4j

# Previous container logs (for crashloop debugging)
kubectl logs backend-0 --previous

# Multi-container logs
kubectl logs backend-0 -c backend

# AKS-specific (with namespace)
kubectl logs -f backend-0 -n soam
kubectl logs -f deployment/ingestor -n soam
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

# AKS-specific - check all resources in namespace
kubectl get all -n soam
kubectl get pods -n soam -w  # Watch in real-time
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

### Azure AKS Troubleshooting
```powershell
# Connect kubectl to AKS cluster
az aks get-credentials --resource-group soam-rg --name soam-aks-cluster

# Verify connection
kubectl cluster-info
kubectl get nodes

# Check images in ACR
az acr repository list --name <acr-name> -o table
az acr repository show-tags --name <acr-name> --repository backend -o table

# Check AKS has ACR pull permissions
az aks check-acr --name soam-aks-cluster --resource-group soam-rg --acr <acr-name>.azurecr.io

# Common AKS issues:
# - Pod stuck in Pending: Usually PVC not bound or insufficient resources
# - ImagePullBackOff: Check ACR permissions and image existence
# - PVC Pending: `managed-premium` uses WaitForFirstConsumer - binds when pod schedules
# - No external IP on LoadBalancer: Wait 2-5 minutes, check Azure portal if stuck

# See docs/azure-deployment.md for comprehensive troubleshooting
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
- Run `terraform destroy` without confirming with user (destroys all Azure resources)
- Delete Kubernetes namespace in AKS (causes data loss)

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
- For AKS deployments, always use `-n soam` namespace flag
- Check `docs/azure-deployment.md` for Azure/Terraform troubleshooting

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
class UserRole(str, Enum):
    """User role enumeration for RBAC."""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"

class User(Base):
    """User authentication and authorization model."""
    # Multi-role support: roles stored as JSON list (e.g., ["admin", "user"])
    # Helper methods: get_roles(), has_role(), has_any_role()
    # Default admin created on startup with all roles
    
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