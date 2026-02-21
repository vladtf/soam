---
applyTo: '{k8s/**,terraform/**,.github/workflows/**,scripts/**,skaffold.yaml,spark-values.yaml,grafana/**,prometheus/**,monitoring/**,mosquitto/**,neo4j/**,simulator/**,rest-api-simulator/**}'
---

# Infrastructure & DevOps

## Tech Map / Key Files

### Local Development (Skaffold)
- `skaffold.yaml` - Main dev orchestration, builds 8 services, handles port-forwarding
- `k8s/` - Kubernetes manifests for all services (StatefulSets/Services)
- `spark-values.yaml` - Helm values for Spark cluster deployment
- `utils/cleanup-images.ps1` - PowerShell script for Docker image management

### Azure Cloud Deployment (Terraform)
- `terraform/` - 2-step Terraform deployment to Azure AKS
  - `terraform/01-azure-infrastructure/` - Azure resources (AKS cluster + ACR container registry)
  - `terraform/02-kubernetes-resources/` - All Kubernetes resources (deployments, services, PVCs, Helm charts)
  - `terraform/deploy.ps1` - **CRITICAL**: Orchestration script for full deployment lifecycle
- `docs/azure-deployment.md` - Comprehensive Azure deployment guide with troubleshooting

### GitHub Actions CI/CD
- `.github/workflows/` - Manual CI/CD workflows for Azure AKS deployment
  - `1-deploy-infrastructure.yml` - Creates Azure resources (AKS + ACR) via Terraform Step 1
  - `2-deploy-application.yml` - Builds all images + deploys K8s resources via Terraform Step 2
  - `3-update-images.yml` - Rebuilds specific images and restarts pods
  - `4-cleanup.yml` - Destroys all Azure resources (requires "DESTROY" confirmation)
- `scripts/setup-github-actions.ps1` - Creates Azure Service Principal + configures GitHub secrets
- `docs/github-actions-cicd.md` - Comprehensive CI/CD setup and usage guide

**GitHub Actions Features:**
- Remote Terraform state stored in Azure Storage (`soam-tfstate-rg`)
- Automatic resource group import if pre-existing
- ACR registry caching for faster Docker builds
- Service URLs displayed in workflow summary after deployment
- Service Principal requires: Contributor + User Access Administrator roles

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
- `docs/experimental-results-validation.md` - Experimental results validation
- `docs/github-actions-cicd.md` - CI/CD setup and usage guide
- `docs/testing-dependability-features.md` - Testing guide for dependability features

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

### GitHub Actions CI/CD Deployment

**Initial Setup (One-time):**
```powershell
# 1. Login to Azure (ALWAYS use tenant ID)
az login --tenant a0867c7c-7aeb-44cb-96ed-32fa642ebe73
az account set --subscription "your-subscription-id"

# 2. Run setup script to create Service Principal and configure GitHub secrets
cd scripts
.\setup-github-actions.ps1
# Follow prompts - script creates SP with Contributor + User Access Administrator roles
```

**Deploy via GitHub Actions:**
```powershell
# Deploy infrastructure (Step 1 - creates AKS + ACR)
gh workflow run "Deploy Infrastructure" --ref main; gh run watch

# Deploy application (Step 2 - builds images + deploys K8s resources)
gh workflow run "Deploy Application" --ref main; gh run watch

# Update specific images without full redeploy
gh workflow run "Update Images" --ref main -f images="backend,frontend"; gh run watch

# Destroy all Azure resources (requires typing "DESTROY")
gh workflow run "Cleanup Resources" --ref main -f confirm_destroy="DESTROY"; gh run watch
```

**Workflow Features:**
- **Remote Terraform State**: Stored in Azure Storage (`soam-tfstate-rg`) for persistence
- **Automatic RG Import**: Handles pre-existing resource groups automatically
- **ACR Registry Caching**: Faster Docker builds using Azure Container Registry cache
- **Service URLs Summary**: After deployment, workflow summary shows all service URLs
- **Monitoring Stack**: Prometheus + Grafana deployed by default

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
