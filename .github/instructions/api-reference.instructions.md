---
applyTo: '{backend/src/api/**,frontend/src/api/**,ingestor/src/api/**}'
---

# API Endpoints Reference

## Backend Service (Port 8000)

### Authentication (`/api/auth`)
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

### Health & Monitoring (`/api`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ready` | Readiness probe (checks Neo4j, Spark, DB) |
| GET | `/api/health` | Health check with component status |
| GET | `/api/metrics` | Prometheus metrics endpoint |

### Spark Operations (`/api/spark`)
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

### Dashboard Tiles (`/api/dashboard`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/tiles` | List all dashboard tiles with access control |
| POST | `/api/dashboard/tiles` | Create new dashboard tile |
| PATCH | `/api/dashboard/tiles/{tile_id}` | Update dashboard tile |
| DELETE | `/api/dashboard/tiles/{tile_id}` | Delete dashboard tile |
| GET | `/api/dashboard/examples` | Get example tile configurations |
| POST | `/api/dashboard/tiles/{tile_id}/preview` | Preview tile data by ID |
| POST | `/api/dashboard/tiles/preview` | Preview tile with custom config |

### Computations (`/api/computations`)
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

### AI Copilot (`/api/copilot`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/copilot/generate-computation` | Generate computation from natural language |
| GET | `/api/copilot/context` | Get data context for copilot |
| GET | `/api/copilot/health` | Check copilot service availability |

### Devices (`/api/devices`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/devices` | List all registered devices |
| POST | `/api/devices` | Register or update device (auth required) |
| PATCH | `/api/devices/{device_id}` | Update device (auth required) |
| DELETE | `/api/devices/{device_id}` | Delete device |

### Normalization Rules (`/api/normalization`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/normalization` | List all normalization rules |
| POST | `/api/normalization` | Create normalization rule |
| PATCH | `/api/normalization/{rule_id}` | Update normalization rule |
| DELETE | `/api/normalization/{rule_id}` | Delete normalization rule |
| PATCH | `/api/normalization/{rule_id}/toggle` | Toggle rule enabled/disabled |

### Normalization Preview (`/api/normalization/preview`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/normalization/preview/sample-data` | Get sample raw data for preview |
| POST | `/api/normalization/preview/preview` | Preview normalization on sample data |
| POST | `/api/normalization/preview/compare` | Compare two normalization scenarios |

### Value Transformations (`/api/value-transformations`)
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

### MinIO Storage (`/api/minio`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/minio/ls` | List prefix contents |
| GET | `/api/minio/find` | List files recursively with pagination |
| GET | `/api/minio/preview` | Preview Parquet file contents |
| GET | `/api/minio/find-data-files` | Find non-empty data files |
| DELETE | `/api/minio/object` | Delete single object |
| POST | `/api/minio/delete` | Delete multiple objects |
| DELETE | `/api/minio/prefix` | Delete all objects with prefix |

### Schema Metadata (`/api/schema`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/schema/datasets` | Get all datasets with metadata |
| GET | `/api/schema/datasets/{ingestion_id}` | Get schema for specific dataset |
| GET | `/api/schema/datasets/{ingestion_id}/evolution` | Get schema evolution history |
| GET | `/api/schema/topics` | Get topics summary |
| GET | `/api/schema/context` | Get comprehensive data context |
| GET | `/api/schema/sources` | Get list of available ingestion IDs |

### Buildings (`/api/buildings`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/buildings` | List all buildings from Neo4j |
| POST | `/api/buildings` | Add new building |
| DELETE | `/api/buildings` | Delete building by name and coordinates |

### Configuration (`/api/config`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config/schema` | Get current schema configuration |
| GET | `/api/config` | Get comprehensive system configuration |
| GET | `/api/config/features` | Get feature flags and capabilities |

### Settings (`/api/settings`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings` | List all settings (optionally by category) |
| GET | `/api/settings/{key}` | Get specific setting by key |
| POST | `/api/settings` | Create new setting |
| PATCH | `/api/settings/{key}` | Update setting |
| DELETE | `/api/settings/{key}` | Delete setting |

### Feedback (`/api/feedback`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/feedback` | List all feedback submissions |
| GET | `/api/feedback/{feedback_id}` | Get specific feedback |
| POST | `/api/feedback` | Submit new feedback |
| DELETE | `/api/feedback/{feedback_id}` | Delete feedback |

### Client Errors (`/api/errors`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/errors` | List recent client errors |
| POST | `/api/errors` | Report client error |

---

## Ingestor Service (Port 8001)

### Health & Monitoring (`/api`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ready` | Readiness probe (checks MinIO) |
| GET | `/api/health` | Health check with data source status |
| GET | `/api/metrics` | Prometheus metrics endpoint |

### Data Access (`/api`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/data` | Get buffered sensor data across all partitions |
| GET | `/api/partitions` | List known ingestion_id partitions |
| GET | `/api/data/{ingestion_id}` | Get buffered data for specific partition |
| GET | `/api/diagnostics/topic-analysis` | Analyze topics and ingestion_ids |

### Metadata (`/api/metadata`)
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

### Data Sources (`/api/data-sources`)
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
