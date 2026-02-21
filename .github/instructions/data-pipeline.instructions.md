---
applyTo: '{backend/src/spark/**,ingestor/src/**}'
---

# Data Pipeline & Processing

## Data Processing Flow

1. **Ingestion**: MQTT/REST → Ingestor Connectors → `DataMessage` → `data_handler()` → Partition Buffer + MinIO bronze layer
2. **Metadata Extraction**: `MetadataExtractor` processes messages in background batches (100 items/30s) → schema inference → `MetadataStorage` (SQLite)
3. **Partitioning**: Data partitioned by `ingestion_id=*/date=*/hour=*/*.parquet` for efficient querying
4. **Schema Provisioning**: Backend's `IngestorSchemaClient` fetches schema from ingestor → `EnrichmentManager` uses flexible schema (numeric/timestamp as StringType)
5. **Enrichment**: Spark streaming reads bronze → `DataCleaner.normalize_to_union_schema()` → `BatchProcessor` 5-step pipeline → Delta write to silver/gold
6. **Normalization**: User-defined rules map raw sensor keys to canonical field names (tracked by `NormalizationRuleUsageTracker`)
7. **Value Transformation**: Rules applied during enrichment (filter/aggregate/convert/validate) with error-resilient wrapping
8. **Analytics**: Computations execute SQL on Spark, sensitivity analyzed per query, dashboard tiles serve results
9. **Monitoring**: Prometheus metrics (pod-aware) → Grafana dashboards, step profiler tracks pipeline step durations

## Critical Data Layer Patterns

- **Bronze**: Raw sensor data with original structure preserved
- **Silver**: Normalized data with consistent schema and cleansed values
- **Gold**: Aggregated insights, alerts, and derived analytics
- **Schema Evolution**: Automatic detection tracked in `MetadataStorage.schema_evolution` table
- **Partition Strategy**: Time-based partitioning enables efficient time-range queries
- **Flexible Schema**: Enrichment reads all numeric/timestamp as StringType for cross-source compatibility

## Component Interaction Patterns

### Backend → Ingestor Communication
- **IngestorSchemaClient** (`backend/src/services/ingestor_schema_client.py`): HTTP client for metadata APIs
- **Data Context Building**: Aggregates schema info from `/api/metadata/datasets` and `/api/metadata/topics`
- **Schema Provisioning**: `get_merged_spark_schema_sync()` provides schema for enrichment streaming

### Frontend → Backend API Flow
- **Configuration Loading**: `ConfigContext.tsx` loads runtime config from `/config/config.json`
- **API Abstraction**: `backendRequests.tsx` central `doFetch<T>()` with auto-auth and 401 retry
- **Dashboard Data Flow**: `useDashboardData()` → `previewDashboardTile()` → Computation Service → Spark Query → Results
- **Pipeline Data Flow**: `usePipelineData()` → parallel API fetches → consolidated state → thin page component
- **Auto-refresh Safety**: Minimum 15-second intervals with concurrency protection, `useRef` for initial vs refresh distinction

### Spark Pipeline Orchestration
- **EnrichmentManager**: Coordinates schema fetch → stream creation → batch processing
- **BatchProcessor**: 5-step profiled pipeline: allowed IDs → process check → filter → transform → Delta write
- **Streaming Manager**: Controls query lifecycle (start/stop/restart) with failure recovery and 30s graceful timeout
- **Data Access Manager**: Provides abstracted access to all data layers (bronze/silver/gold)

### Data Source Plugin Architecture
- **Registry Pattern**: `DataSourceRegistry.CONNECTOR_TYPES` maps type names to connector classes
- **Lifecycle Management**: `DataSourceManager` handles start/stop/health for all active sources
- **Standardized Output**: All connectors output `DataMessage` format for consistent processing
- **Extensibility**: New connector types register via simple class mapping in registry
- **Auto-registration**: Startup auto-creates default MQTT data source if missing

## Pipeline Metrics & Monitoring

### Backend Metrics (`backend/src/metrics.py`) - Pod-aware, all include `pod` label

| Category | Metrics |
|----------|---------|
| Pipeline Latency (Histograms) | `pipeline_sensor_to_enrichment_latency_seconds`, `pipeline_sensor_to_gold_latency_seconds`, `pipeline_enrichment_to_gold_latency_seconds`, `pipeline_stage_latency_seconds` (by stage), `spark_batch_processing_latency_seconds` |
| Throughput (Counters) | `enrichment_records_processed_total`, `gold_records_written_total`, `spark_batches_processed_total` |
| Operational (Gauges + Counters) | `spark_active_streams`, `spark_stream_status`, `computation_executions_total`, `computation_execution_latency_seconds` |
| Data Freshness (Gauges) | `pipeline_layer_data_age_seconds`, `pipeline_processing_lag_seconds` |

Helper functions wrap raw Prometheus calls: `record_sensor_to_enrichment_latency()`, `record_spark_batch()`, `record_computation()`, `update_active_streams()`, `update_layer_data_age()`

### Ingestor Metrics (`ingestor/src/metrics.py`) - 12 metrics total

| Metric | Type | Labels |
|--------|------|--------|
| `ingestor_messages_received_total` | Counter | pod, source_type, ingestion_id |
| `ingestor_messages_processed_total` | Counter | pod, source_type, ingestion_id |
| `ingestor_messages_failed_total` | Counter | pod, source_type, ingestion_id, error_type |
| `ingestor_bytes_received_total` | Counter | pod, source_type |
| `ingestor_bytes_written_total` | Counter | pod, layer |
| `ingestor_timestamp_delay_seconds` | Histogram | pod, source_type |
| `ingestor_active_data_sources` | Gauge | pod, source_type |
| `ingestor_buffer_size_messages` | Gauge | pod, ingestion_id |
| `ingestor_buffer_size_bytes` | Gauge | pod, ingestion_id |
| `ingestor_files_written_total` | Counter | pod, layer |

### Step Profiler Metrics (`backend/src/utils/step_profiler.py`)
- `step_duration_seconds` (Gauge) with labels `[module, step]` — records last observed duration per pipeline step
- Used in `batch_processor.py` for steps: `1_get_allowed_ids`, `2_should_process`, `3_filter_dataframe`, `4_apply_transformations`, `5_write_delta`

**Grafana Dashboard**: `grafana/provisioning/ingestor-dashboards/pipeline-metrics.json`
