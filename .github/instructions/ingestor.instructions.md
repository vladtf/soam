---
applyTo: 'ingestor/**'
---

# Ingestor Service (Python/FastAPI) - Port 8001

## Tech Map / Key Files

**Modular Data Ingestion Platform:**
- `ingestor/src/main.py` - FastAPI app factory with lifespan manager, auto-registers "Local Simulators MQTT" data source on startup
- `ingestor/src/middleware.py` - `RequestIdMiddleware` for request tracking
- `ingestor/src/config.py` - Legacy `ConnectionConfig` dataclass (vestigial — actual config in `IngestorConfig`)
- `ingestor/src/metrics.py` - Prometheus metrics (12 metrics total)

### API Layer (`ingestor/src/api/`)
- `dependencies.py` - DI container with manual singleton pattern (`_*_instance` globals):
  - `IngestorConfig` - All settings from env vars (MQTT, MinIO creds/bucket)
  - `IngestorState` - Partitioned `deque` buffers per `ingestion_id`, runtime-tunable max rows
  - Type aliases: `ConfigDep`, `MinioClientDep`, `IngestorStateDep`, `MetadataServiceDep`
- `models.py` - `ApiResponse[T]`, `ApiListResponse[T]` (mirrors backend pattern), `HealthStatus`
- `response_utils.py` - Simpler than backend: `success_response()`, `error_response()` (returns model, not HTTPException), `list_response()`
- `routers/` - API endpoint organization:
  - `health.py` - Health checks, readiness probes, and Prometheus metrics
  - `data.py` - Legacy data access API (partition buffers)
  - `metadata.py` - Schema metadata and data quality metrics
  - `data_sources.py` - Dynamic data source management API (uses `init_dependencies(registry, manager)` module-level initialization)

### Connector Architecture (`ingestor/src/connectors/`)
- `base.py` - **CRITICAL**: Abstract base connector with standardized `DataMessage` format + `ConnectorRegistry` (auto-discovery)
- `__init__.py` - Auto-discovers all `*_connector.py` modules and triggers `@ConnectorRegistry.register()` decorators
- `mqtt_connector.py` - MQTT broker integration with shared subscriptions for horizontal scaling
- `rest_api_connector.py` - REST API polling connector with configurable intervals
- `coap_connector.py` - CoAP (RFC 7252) connector with observe (push) and poll modes for constrained IoT devices

### Services Layer (`ingestor/src/services/`)
- `data_source_service.py` - **CRITICAL**: Registry and manager for pluggable data sources:
  - `DataSourceRegistry` - Type registration and discovery
  - `DataSourceManager` - Instance lifecycle management with auto-restart, health monitoring

### Storage & Metadata (Dual Database Architecture)
- `ingestor/src/storage/minio_client.py` - MinIO client for bronze layer storage
- `ingestor/src/metadata/` - Schema extraction and tracking:
  - `service.py` - `MetadataService` coordinating extraction and storage
  - `extractor.py` - `MetadataExtractor` with background batch processing (batch_size=100, timeout=30s), schema inference with type merging/promotion, thread-safe with `threading.Lock`. **Key design**: all int/float inferred as `"double"` for Parquet consistency; strings never inferred as timestamp.
  - `storage.py` - `MetadataStorage` using **raw SQLite** (not SQLAlchemy) with 3 tables: `dataset_metadata`, `schema_evolution`, `data_quality`. Thread-safe with `threading.Lock` and `@contextmanager` for connections.
- `ingestor/src/database/` - **SQLAlchemy ORM** for data source configuration:
  - `database.py` - Standard SQLAlchemy setup with `@lru_cache()` engine, `get_db()` generator
  - `models.py` - `DataSourceType` (config_schema as JSON), `DataSource` (ingestion_id, status, audit fields), `DataSourceMetric` (with cascade delete)
- **⚠️ Note**: Ingestor has **two separate database systems**: SQLAlchemy (`ingestor.db`) for data sources, raw SQLite (`/data/metadata.db`) for metadata

### Utilities
- `ingestor/src/utils/timestamp_utils.py` - Timestamp parsing, standardization, and `ensure_datetime()` for timezone-safe coercion

## Ingestor Development Patterns

### Error Handling Difference
**⚠️ IMPORTANT**: Ingestor uses a DIFFERENT error pattern from the backend:
- Backend: error functions return `HTTPException` — callers must `raise` them
- Ingestor: `error_response()` returns an `ApiResponse` model with error status — NOT an exception

### Modular Connector Architecture
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

### Adding a New Connector (Zero-Touch Registration)
```python
# 1. Create ingestor/src/connectors/myprotocol_connector.py
# 2. Decorate with @ConnectorRegistry.register("myprotocol")
# 3. That's it — auto-discovery handles the rest (no other files to edit)

from .base import BaseDataConnector, ConnectorRegistry

@ConnectorRegistry.register("myprotocol")
class MyProtocolConnector(BaseDataConnector):
    # Implement: connect, disconnect, start_ingestion, stop_ingestion,
    #           health_check, get_config_schema, get_display_info
    ...
```

### Data Source Management
```python
# ConnectorRegistry auto-populated by decorators (no hardcoded dict)
class DataSourceRegistry:
    """Registry for pluggable connector types."""
    @property
    def CONNECTOR_TYPES(self):
        return ConnectorRegistry.get_all()  # mqtt, rest_api, coap, ...

class DataSourceManager:
    """Manages individual data source instances with lifecycle control."""
    # Auto-restart, health monitoring, metrics collection
```

### Critical Data Flow
Connector → `DataMessage` → `data_handler` closure → Partition Buffer + MinIO Bronze Layer → Metadata Extraction

- All connectors output standardized `DataMessage` format
- `data_handler()` in `main.py` processes every message (metrics → timestamp normalization → payload → buffer + MinIO → metadata)
- Partition buffers maintain compatibility with legacy `/api/partitions` endpoint
- MinIO client handles bronze layer storage with ingestion_id partitioning
- `MetadataExtractor` infers schemas in background batches and stores via `MetadataStorage`

### Service Architecture

- `DataSourceRegistry` - Type discovery and connector registration
- `DataSourceManager` - Instance lifecycle management with auto-restart
- `MetadataService` + `MetadataExtractor` + `MetadataStorage` - Three-layer metadata system
- `MinioClient` - Bronze layer storage with partitioning strategy

### Ingestor Database Models
```python
class DataSourceType(Base):
    """Registered connector types. config_schema as JSON, connector_class as Python path."""

class DataSource(Base):
    """Individual instances. ingestion_id (unique), status, audit fields. Cascade delete on metrics."""

class DataSourceMetric(Base):
    """Performance and health metrics."""
```

### Ingestor Code Conventions
```powershell
# Use pipenv for all Python operations
cd ingestor
pipenv install
pipenv shell
python src/main.py
```

- Uses same logging patterns as backend: `get_logger(__name__)`, emoji prefixes
- DI uses manual singleton pattern (`_*_instance` globals) instead of `@lru_cache()`
- Response utilities return models, not exceptions
- All mutable models track `created_at`/`updated_at`
