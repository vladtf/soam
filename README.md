# SOAM: An Ontology-Driven Middleware Platform for Integrating Heterogeneous Data in Smart Cities


## Table of Contents

- [SOAM: An Ontology-Driven Middleware Platform for Integrating Heterogeneous Data in Smart Cities](#soam-an-ontology-driven-middleware-platform-for-integrating-heterogeneous-data-in-smart-cities)
  - [Table of Contents](#table-of-contents)
    - [Overview](#overview)
    - [Project Structure](#project-structure)
    - [Summary of Local Pages:](#summary-of-local-pages)
    - [Architecture Diagram](#architecture-diagram)
    - [Local Development](#local-development)
      - [Pre-requisites](#pre-requisites)
  - [Documentation](#documentation)
      - [Docker compose](#docker-compose)
      - [Skaffold](#skaffold)
    - [Azure Deployment (Production)](#azure-deployment-production)
      - [Prerequisites](#prerequisites)
      - [Quick Start (Automated)](#quick-start-automated)
      - [Manual Deployment](#manual-deployment)
        - [Step 1: Azure Authentication](#step-1-azure-authentication)
        - [Step 2: Deploy Azure Infrastructure (AKS + ACR)](#step-2-deploy-azure-infrastructure-aks--acr)
        - [Step 3: Build and Push Docker Images](#step-3-build-and-push-docker-images)
        - [Step 4: Deploy Kubernetes Resources](#step-4-deploy-kubernetes-resources)
        - [Step 5: Access the Application](#step-5-access-the-application)
      - [Deploy Script Commands](#deploy-script-commands)
      - [Cost Estimation](#cost-estimation)
      - [Troubleshooting](#troubleshooting)

### Overview

SOAM is a smart-city data platform that ingests heterogeneous sensor streams, normalizes data against an ontology, and provides analytics and observability. It includes:

- Backend: FastAPI + PySpark + SQLAlchemy, with MinIO S3 integration, Neo4j, and structured logging
- Frontend: React + Vite + React-Bootstrap, for browsing data, rules, and health
- Streaming: MQTT ingestion, Spark batch/streaming jobs, Delta Lake storage on MinIO
- Monitoring: Prometheus + Grafana, cAdvisor
- **🤖 AI Copilot: Azure OpenAI-powered computation generation using natural language**

### Project Structure

```
soam/
├─ backend/                # FastAPI service with Spark helpers and DB models
│  ├─ Dockerfile
│  └─ src/
│     ├─ api/              # FastAPI routers (health, minio, feedback, normalization)
│     ├─ database/         # SQLAlchemy models and DB helpers
│     ├─ logging_config.py # JSON logging configuration
│     ├─ middleware.py     # Request ID middleware
│     ├─ neo4j/            # Neo4j routes/integration
│     ├─ spark/            # Spark utilities (cleaner, usage tracker, routes)
│     └─ main.py           # FastAPI app entrypoint
├─ frontend/               # React (Vite) app
│  ├─ Dockerfile
│  └─ src/
│     ├─ api/              # API client for backend endpoints
│     ├─ components/       # UI building blocks
│     ├─ pages/            # Main pages (Dashboard, Normalization Rules, etc.)
│     └─ context/          # React contexts (config, error)
├─ ingestor/               # MQTT and REST API ingestion service
├─ simulator/              # MQTT test publishers
├─ rest-api-simulator/     # REST API data source with auto-registration
├─ grafana/                # Grafana setup and dashboards
├─ prometheus/             # Prometheus setup
├─ k8s/                    # Kubernetes manifests for core services
├─ spark/                  # Spark image and configs
├─ skaffold.yaml           # Skaffold config (build + deploy)
├─ docker-compose.yml      # Local Mosquitto for quick tests
└─ tests/                  # Test scripts/utilities
```

### Summary of Local Pages:

- **[Frontend](http://localhost:3000):** Accessible at `http://localhost:3000`
- **[Backend](http://localhost:8000):** Accessible at `http://localhost:8000`
- **[Spark Master UI](http://localhost:8080):** Accessible at `http://localhost:8080`
- **[MinIO S3 API](http://localhost:9000):** Accessible at `http://localhost:9000`
- **[MinIO Web Console](http://localhost:9090):** Accessible at `http://localhost:9090`
- **[Neo4j Web UI](http://localhost:7474):** Accessible at `http://localhost:7474`
- **[Cadvisor Web UI](http://localhost:8089/metrics):** Accessible at `http://localhost:8089/metrics`
- **[Prometheus Web UI](http://localhost:9091):** Accessible at `http://localhost:9091`
- **[Grafana Web UI](http://localhost:3001):** Accessible at `http://localhost:3001`

### Architecture Diagram

<div style="border: 2px solid black; padding: 10px; display: inline-block;">
    <img src="assets/architecture.png" alt="Architecture" width="100%"/>
</div>

### Local Development

#### Pre-requisites

- Start local registry for Skaffold:

```powershell
# Start a local Docker registry
docker run -d -p 5000:5000 --name registry registry:2

# Set Skaffold default repository
skaffold config set default-repo localhost:5000/soam
```

## Documentation

For detailed feature-specific documentation, see the `docs/` folder:

- **🤖 [AI Copilot Setup Guide](docs/copilot-setup.md)** - Azure OpenAI-powered computation generation
- More feature docs coming soon...

#### Docker compose

> [!NOTE]
> Docker compose is used for local development with Docker. Ensure you have Docker installed and running.

```bash
docker-compose up -d
```

#### Skaffold

> [!NOTE]
> Skaffold is used for local development with Kubernetes. Ensure you have a local K8s cluster running (e.g., Minikube or Docker Desktop).

```bash
skaffold dev
```

or

```bash
skaffold dev --trigger=polling --watch-poll-interval=5000 --default-repo=localhost:5000/soam
```

### Azure Deployment (Production)

Deploy SOAM to Azure Kubernetes Service (AKS) using Terraform for a production-ready environment.

The deployment is split into **two Terraform configurations**:
1. **Step 1**: Create Azure infrastructure (AKS + ACR)
2. **Step 2**: Deploy Kubernetes resources (after images are pushed)

#### Prerequisites

1. **Azure CLI** - Install from [Microsoft Docs](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
2. **Terraform** - Install from [Terraform Downloads](https://www.terraform.io/downloads) (version >= 1.0.0)
3. **Docker** - For building and pushing container images
4. **Azure Subscription** - With permissions to create resources

#### Quick Start (Automated)

Use the provided PowerShell script for a fully automated deployment:

```powershell
# Login to Azure first
az login

# Configure Step 1 variables
cd terraform/01-azure-infrastructure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars - set subscription_id and acr_name

# Run full deployment (Azure + Images + Kubernetes)
cd ..
.\deploy.ps1 -Action deploy

# Check deployment status
.\deploy.ps1 -Action status

# Destroy everything when done
.\deploy.ps1 -Action destroy
```

#### Manual Deployment

##### Step 1: Azure Authentication

```powershell
# Login to Azure
az login

# Set your subscription (if you have multiple)
az account set --subscription "your-subscription-id"

# Verify your subscription
az account show
```

##### Step 2: Deploy Azure Infrastructure (AKS + ACR)

```powershell
cd terraform/01-azure-infrastructure

# Copy and configure variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars - set subscription_id and acr_name (must be unique)

# Deploy Azure infrastructure (~10-15 minutes)
terraform init
terraform plan
terraform apply
```

Key variables for Step 1:

| Variable | Description | Required |
|----------|-------------|----------|
| `subscription_id` | Your Azure subscription ID | ✅ Yes |
| `acr_name` | Unique ACR name (alphanumeric only) | ✅ Yes |
| `location` | Azure region (e.g., "West Europe") | Optional |
| `aks_node_count` | Number of AKS nodes (default: 3) | Optional |

##### Step 3: Build and Push Docker Images

```powershell
# Get ACR info from Step 1
cd terraform/01-azure-infrastructure
$ACR_SERVER = terraform output -raw acr_login_server
$ACR_NAME = terraform output -raw acr_name

# Login to ACR
az acr login --name $ACR_NAME

# Build and push all images (from project root)
cd ../..

docker build -t "$ACR_SERVER/backend:latest" ./backend
docker push "$ACR_SERVER/backend:latest"

docker build -t "$ACR_SERVER/frontend:latest" ./frontend
docker push "$ACR_SERVER/frontend:latest"

docker build -t "$ACR_SERVER/ingestor:latest" ./ingestor
docker push "$ACR_SERVER/ingestor:latest"

docker build -t "$ACR_SERVER/mosquitto:latest" ./mosquitto
docker push "$ACR_SERVER/mosquitto:latest"

docker build -t "$ACR_SERVER/spark:latest" ./spark
docker push "$ACR_SERVER/spark:latest"

docker build -t "$ACR_SERVER/simulator:latest" ./simulator
docker push "$ACR_SERVER/simulator:latest"
```

##### Step 4: Deploy Kubernetes Resources

```powershell
cd terraform/02-kubernetes-resources

# Copy example config (optional - script auto-generates from Step 1)
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars for app-specific settings (passwords, replicas, etc.)

# Get AKS credentials from Step 1 and add to terraform.tfvars
# The deploy.ps1 script does this automatically, or manually:
cd ../01-azure-infrastructure
$AKS_HOST = terraform output -raw aks_host
$AKS_CERT = terraform output -raw aks_client_certificate
$AKS_KEY = terraform output -raw aks_client_key
$AKS_CA = terraform output -raw aks_cluster_ca_certificate
$ACR_SERVER = terraform output -raw acr_login_server

# Add these to 02-kubernetes-resources/terraform.tfvars

# Deploy Kubernetes resources
cd ../02-kubernetes-resources
terraform init
terraform plan
terraform apply
```

Key variables for Step 2:

| Variable | Description | Default |
|----------|-------------|---------|
| `minio_root_password` | MinIO password (min 8 chars) | `minio123` |
| `neo4j_password` | Neo4j password | `verystrongpassword` |
| `spark_worker_count` | Spark workers | `2` |
| `deploy_simulator` | Deploy MQTT simulator | `true` |
| `deploy_monitoring` | Deploy Prometheus+Grafana | `false` |
| `azure_openai_*` | AI Copilot configuration | (empty) |

##### Step 5: Access the Application

```powershell
cd terraform/02-kubernetes-resources

# Get application URLs
terraform output frontend_url      # SOAM Dashboard
terraform output backend_url       # Backend API
terraform output backend_docs_url  # Swagger API Documentation

# Configure kubectl for the cluster
cd ../01-azure-infrastructure
az aks get-credentials --resource-group $(terraform output -raw resource_group_name) --name $(terraform output -raw aks_cluster_name)

# Verify pods are running
kubectl get pods -n soam
```

#### Deploy Script Commands

```powershell
# Full deployment
.\deploy.ps1 -Action deploy

# Deploy only Azure infrastructure (Step 1)
.\deploy.ps1 -Action deploy -Step 1

# Deploy only Kubernetes resources (Step 2, requires Step 1)
.\deploy.ps1 -Action deploy -Step 2

# Redeploy Kubernetes without rebuilding images
.\deploy.ps1 -Action deploy -Step 2 -SkipImages

# Rebuild and push images only
.\deploy.ps1 -Action images-only

# Check deployment status
.\deploy.ps1 -Action status

# Destroy everything
.\deploy.ps1 -Action destroy

# Destroy only Kubernetes resources (keep Azure infra)
.\deploy.ps1 -Action destroy -Step 2
```

#### Cost Estimation

Approximate monthly costs for default configuration (West Europe):

| Resource | SKU | Estimated Cost |
|----------|-----|----------------|
| AKS (3 nodes) | Standard_DS2_v2 | ~$300/month |
| ACR | Basic | ~$5/month |
| Storage (PVCs) | Premium SSD | ~$20/month |
| Load Balancers | Standard | ~$50/month |
| **Total** | | **~$375/month** |

> [!TIP]
> For development/testing, reduce costs by:
> - Using `Standard_B2s` VMs (~$60/month for 3 nodes)
> - Setting `aks_node_count = 2`
> - Disabling monitoring stack

#### Troubleshooting

**Connect to AKS Cluster from Local Machine:**
```powershell
# Login to Azure (if not already logged in)
az login

# Get AKS credentials (merges into ~/.kube/config)
az aks get-credentials --resource-group soam-rg --name soam-aks-cluster

# Verify connection
kubectl get nodes
kubectl cluster-info

# Switch context if you have multiple clusters
kubectl config get-contexts
kubectl config use-context soam-aks-cluster
```

**Port Forward Services to Local Machine:**
```powershell
# Frontend (local:3000 -> nginx:80)
kubectl port-forward svc/frontend 3000:80 -n soam

# Backend API (local:8000)
kubectl port-forward svc/backend-external 8000:8000 -n soam

# Ingestor (local:8001)
kubectl port-forward svc/ingestor-external 8001:8001 -n soam

# MinIO Console (local:9090) and API (local:9000)
kubectl port-forward svc/minio 9000:9000 9090:9090 -n soam

# Neo4j Browser (local:7474) and Bolt (local:7687)
kubectl port-forward svc/neo4j 7474:7474 7687:7687 -n soam

# Spark Master UI (local:8080)
kubectl port-forward svc/soam-spark-master-svc 8080:80 -n soam

# Run multiple port-forwards in background (PowerShell)
Start-Job { kubectl port-forward svc/frontend 3000:80 -n soam }
Start-Job { kubectl port-forward svc/backend-external 8000:8000 -n soam }
Start-Job { kubectl port-forward svc/minio 9000:9000 9090:9090 -n soam }
Start-Job { kubectl port-forward svc/neo4j 7474:7474 7687:7687 -n soam }

# Check running jobs
Get-Job

# Stop all port-forward jobs (if started with Start-Job)
Get-Job | Stop-Job; Get-Job | Remove-Job

# Stop all kubectl port-forward processes
Get-Process kubectl -ErrorAction SilentlyContinue | Stop-Process
```

**Images not found:**
```powershell
# Check if images exist in ACR
az acr repository list --name <acr-name> --output table

# View all tags for a specific image
az acr repository show-tags --name <acr-name> --repository backend --output table
```

**Pods not starting:**
```powershell
# List all pods in soam namespace
kubectl get pods -n soam

# Describe a specific pod for events and errors
kubectl describe pod <pod-name> -n soam

# View pod logs
kubectl logs <pod-name> -n soam

# View previous container logs (if pod restarted)
kubectl logs <pod-name> -n soam --previous

# Follow logs in real-time
kubectl logs -f <pod-name> -n soam
```

**Load Balancer IP pending:**
```powershell
# Wait for external IP (can take 2-5 minutes)
kubectl get svc -n soam -w
```

**Check cluster resources:**
```powershell
# View resource usage per pod
kubectl top pods -n soam

# View resource usage per node
kubectl top nodes

# Check PVC status
kubectl get pvc -n soam

# Check storage classes available
kubectl get storageclass

# View events (useful for debugging)
kubectl get events -n soam --sort-by='.lastTimestamp'
```

**Restart a deployment/statefulset:**
```powershell
kubectl rollout restart deployment/<name> -n soam
kubectl rollout restart statefulset/<name> -n soam
```

**Execute commands inside a pod:**
```powershell
# Get a shell inside a pod
kubectl exec -it <pod-name> -n soam -- /bin/bash

# Run a single command
kubectl exec <pod-name> -n soam -- <command>
```

