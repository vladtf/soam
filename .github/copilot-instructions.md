# SOAM Development Guide for GitHub Copilot

## Project Overview

SOAM is a smart city IoT platform built with Python/FastAPI backend, React/TypeScript frontend, and microservices architecture. The system ingests MQTT sensor data, processes it with Spark streaming, stores in MinIO/Neo4j, and provides real-time dashboards. Development uses Skaffold + Kubernetes for local deployment with Docker containers.

The architecture includes: MQTT broker (Mosquitto), data ingestion service, Spark-based enrichment pipeline, schema inference system, Neo4j graph database, MinIO object storage, and monitoring stack (Grafana/Prometheus). All services run in Kubernetes with StatefulSets for stateful components.

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
- `backend/src/schema_inference/` - Schema inference package (new modular system)
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

### Python (Backend/Ingestor)
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

## Safe Ops Rules

### NEVER (without confirmation):
- `kubectl delete` on production-like resources
- `docker system prune -a` (use project cleanup script instead)
- Modify StatefulSet volumes without data backup
- Change Spark cluster configuration without understanding impact

### ALWAYS:
- Show commands before execution in destructive operations
- Use `kubectl describe` and `kubectl logs` for investigation first
- Test API changes with curl/PowerShell before frontend integration
- Check resource limits when adding new containers
- Use `pipenv shell` before running Python scripts
- Verify port-forwarding is active before API testing

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
from src.api.models import ApiResponse
from src.api.response_utils import success_response

router = APIRouter(prefix="/api/feature", tags=["feature"])

@router.get("/endpoint", response_model=ApiResponse)
async def get_data():
    return success_response(data={"result": "value"})
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
