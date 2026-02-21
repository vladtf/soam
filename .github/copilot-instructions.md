---
applyTo: '**'
---

# SOAM Development Guide for AI Coding Assistants

## Project Overview

SOAM is a smart city IoT platform built with Python/FastAPI backend, React/TypeScript frontend, and microservices architecture. The system ingests MQTT sensor data, processes it with Spark streaming, stores in MinIO/Neo4j, and provides real-time dashboards. Development uses Skaffold + Kubernetes for local deployment with Docker containers.

The architecture follows a **data lake pattern** with Bronze (raw) → Silver (normalized) → Gold (aggregated) layers, all orchestrated through Kubernetes. **Core Data Flow**: MQTT sensors → Ingestor → MinIO (Bronze) → Spark Streaming → Schema Inference → Enrichment → Neo4j/Gold Layer → Dashboard

> **Instructions are split by domain.** This root file contains universal conventions. Domain-specific details are in `.github/instructions/`:
> - `backend.instructions.md` → Backend architecture, patterns, code conventions
> - `frontend.instructions.md` → Frontend architecture, hooks, components
> - `ingestor.instructions.md` → Ingestor architecture, connectors, dual DB
> - `api-reference.instructions.md` → All API endpoint tables
> - `infrastructure.instructions.md` → K8s, Terraform, CI/CD, troubleshooting
> - `data-pipeline.instructions.md` → Data flow, enrichment, metrics

## Established Good Practices (FOLLOW THESE)

**Based on comprehensive codebase analysis, the following patterns are already established and MUST be maintained:**

### ✅ Dependency Injection Excellence
- Uses `@lru_cache()` for singleton instances (backend); manual `_instance` globals (ingestor)
- Type aliases provide both DI and type hints: `SparkManagerDep`, `Neo4jManagerDep`, `ConfigDep`, `MinioClientDep`
- Centralized configuration in `AppConfig` (backend) and `IngestorConfig` (ingestor)

### ✅ Explicit Error Handling
- All error functions return `HTTPException` - callers must `raise` them explicitly
- Specific error types: `bad_request_error()`, `not_found_error()`, `conflict_error()`, `forbidden_error()`, `internal_server_error()`
- Database rollback pattern in all exception handlers
- **Note**: Ingestor uses a different pattern — returns `ApiResponse` with error status instead of raising `HTTPException`

### ✅ Comprehensive Logging with Emojis
- Standardized emoji prefixes: ✅ (success), ❌ (error), ⚠️ (warning), 🔍 (debug), 🚀 (starting), 📊 (metrics)
- Context-rich logging with user/operation details
- Consistent logger creation: `logger = get_logger(__name__)`
- Logging decorators: `@log_execution_time()`, `@log_exceptions()`, `@log_function_calls()`

### ✅ Response Model Consistency
- ALWAYS use `response_model=ApiResponse[T]` or `ApiListResponse[T]`
- `ApiListResponse` includes pagination: `total`, `page`, `page_size`
- Generic typing ensures frontend type safety
- Meaningful success messages in all responses

### ✅ Import Organization Standards
- Predictable import order: stdlib → FastAPI → SQLAlchemy → src modules
- Type alias usage for dependency injection
- Consistent utility imports

### ✅ Database Transaction Patterns
- Input validation before database operations
- Explicit transaction management with rollback
- User context tracking in all mutations (`created_by`/`updated_by`)
- Every model has `to_dict()` method for serialization

### ✅ Router Structure Conventions
- HTTP methods in logical order: GET (list, single) → POST → PATCH → DELETE
- Consistent endpoint naming and prefixing
- Action endpoints placed after CRUD operations

### ✅ Ownership Tracking
- All Pydantic Create models require `created_by: str = Field(...)`
- All Pydantic Update models require `updated_by: str = Field(...)`
- All mutable SQLAlchemy models have `created_at`/`updated_at` with `func.now()`

### ✅ Custom Hooks for Data Extraction (Frontend)
- Page-level data fetching, state, and refresh logic encapsulated in custom hooks
- Page components remain thin — rendering only
- `useDashboardData()` and `usePipelineData()` are the established pattern

### ✅ Multi-Layer Error Handling (Frontend)
- `ErrorContext` (toasts via react-toastify) → `networkErrorHandler` (HTTP-level) → `useErrorCapture` (component-level) → `errors.ts` (queue + backend reporting) → `devTools` (dev instrumentation)
- Client errors batched and flushed to backend via `/api/errors`

## Feature Checklist

When implementing new features, always:

1. **API Development**:
   - Add router to appropriate module and register in `main.py`
   - Use dependency injection pattern (see `dependencies.py`)
   - Include proper error handling with `raise error_function()` pattern
   - Add `response_model=ApiResponse[T]` or `ApiListResponse[T]`
   - Add OpenAPI documentation with response models
   - Consider sensitivity/RBAC requirements

2. **Database Changes**:
   - Update SQLAlchemy models in `/database/models.py` with `to_dict()` method
   - Add column migration in `main.py` startup (use `ensure_*_columns()` pattern)
   - Include `created_by`/`updated_by` and `created_at`/`updated_at` fields
   - Test with both SQLite (dev) and production setup

3. **Spark Integration**:
   - Use enrichment manager pattern for data pipeline changes
   - Add enrichment logic to `/spark/enrichment/`
   - Use `@profile_step` decorator on pipeline steps
   - Consider streaming vs batch processing needs

4. **Frontend Integration**:
   - Add API functions to `backendRequests.tsx` using `doFetch<T>()` pattern
   - Add TypeScript types to `/frontend/src/types/` (avoid type duplication with `backendRequests.tsx`)
   - Extract data fetching into custom hooks (follow `useDashboardData`/`usePipelineData` pattern)
   - Use React Bootstrap for consistent styling
   - Use `useAuth().username` for user attribution
   - Use `extractErrorMessage()` from `utils/errorHandling.ts` for error display

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
- [ ] `HTTPException` re-raised before catching generic `Exception`
- [ ] Database rollback in all exception handlers
- [ ] Specific error types used (not generic `HTTPException`)

### ✅ Logging
- [ ] Uses `get_logger(__name__)` for logger creation
- [ ] Emoji prefixes: ✅ ❌ ⚠️ 🔍 🚀 📊
- [ ] Context included in business logic logs (user, operation details)
- [ ] `@log_execution_time()` on long-running operations

### ✅ Response Models
- [ ] `response_model=ApiResponse[T]` or `ApiListResponse[T]` specified
- [ ] Generic typing used for type safety
- [ ] Meaningful success messages included

### ✅ Code Organization
- [ ] Imports organized: stdlib → FastAPI → SQLAlchemy → src modules
- [ ] Router endpoints ordered: GET → POST → PATCH → DELETE
- [ ] Database operations include input validation and user context
- [ ] `created_by`/`updated_by` in all mutation payloads

### ✅ Frontend
- [ ] API calls use `doFetch<T>()` pattern in `backendRequests.tsx`
- [ ] Data fetching extracted into custom hooks (not inline in components)
- [ ] Errors extracted with `extractErrorMessage()` utilities
- [ ] `useAuth().username` used for attribution

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
- Run `gh workflow run "Cleanup Resources"` without "DESTROY" confirmation (destroys Azure resources)

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
- **For Azure CLI commands, always use tenant ID**: `az login --tenant a0867c7c-7aeb-44cb-96ed-32fa642ebe73`

## Quick Dev Commands (Windows PowerShell)

```powershell
# Full dev environment
skaffold dev --trigger=polling --watch-poll-interval=5000 --default-repo=localhost:5000/soam

# Run services locally
cd backend && pipenv shell && uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
cd frontend && npm run dev
cd ingestor && pipenv shell && python src/main.py

# Frontend tools
cd frontend && npm run lint && npm run build
```
