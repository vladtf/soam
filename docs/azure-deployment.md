# Azure Deployment Guide

Deploy SOAM to Azure Kubernetes Service (AKS) using Terraform.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Manual Deployment](#manual-deployment)
- [Deploy Script Reference](#deploy-script-reference)
- [Cost Estimation](#cost-estimation)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Tool | Installation |
|------|-------------|
| **Azure CLI** | [Microsoft Docs](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli) |
| **Terraform** | [Terraform Downloads](https://www.terraform.io/downloads) (>= 1.0.0) |
| **Docker** | For building container images |
| **kubectl** | `az aks install-cli` |

## Quick Start

```powershell
# 1. Login to Azure
az login

# 2. Configure variables
cd terraform/01-azure-infrastructure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars - set subscription_id and acr_name

# 3. Deploy everything
cd ..
.\deploy.ps1 -Action deploy

# 4. Check status
.\deploy.ps1 -Action status

# 5. Destroy when done
.\deploy.ps1 -Action destroy
```

---

## Manual Deployment

The deployment has **two Terraform configurations**:
1. **Step 1**: Azure infrastructure (AKS + ACR)
2. **Step 2**: Kubernetes resources

### Step 1: Deploy Azure Infrastructure

```powershell
# Login and set subscription
az login
az account set --subscription "your-subscription-id"

# Deploy AKS + ACR (~10-15 minutes)
cd terraform/01-azure-infrastructure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars

terraform init
terraform apply
```

**Key Variables:**

| Variable | Description | Required |
|----------|-------------|:--------:|
| `subscription_id` | Azure subscription ID | ✅ |
| `acr_name` | Unique ACR name (alphanumeric) | ✅ |
| `location` | Azure region | ❌ |
| `aks_node_count` | Number of nodes (default: 3) | ❌ |

### Step 2: Build and Push Docker Images

```powershell
# Get ACR credentials
cd terraform/01-azure-infrastructure
$ACR_SERVER = terraform output -raw acr_login_server
$ACR_NAME = terraform output -raw acr_name

# Login to ACR
az acr login --name $ACR_NAME

# Build and push all images
cd ../..
$images = @("backend", "frontend", "ingestor", "mosquitto", "spark", "simulator")
foreach ($img in $images) {
    docker build -t "$ACR_SERVER/${img}:latest" ./$img
    docker push "$ACR_SERVER/${img}:latest"
}
```

### Step 3: Deploy Kubernetes Resources

```powershell
cd terraform/02-kubernetes-resources
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars (passwords, replicas, etc.)

terraform init
terraform apply
```

**Key Variables:**

| Variable | Description | Default |
|----------|-------------|---------|
| `minio_root_password` | MinIO password (min 8 chars) | `minio123` |
| `neo4j_password` | Neo4j password | `verystrongpassword` |
| `spark_worker_count` | Number of Spark workers | `2` |
| `deploy_simulator` | Deploy MQTT simulator | `true` |
| `deploy_monitoring` | Deploy Prometheus+Grafana | `false` |

### Step 4: Access the Application

```powershell
# Get URLs
cd terraform/02-kubernetes-resources
terraform output frontend_url
terraform output backend_url

# Connect kubectl to cluster
cd ../01-azure-infrastructure
az aks get-credentials --resource-group soam-rg --name soam-aks-cluster --overwrite-existing

# Verify deployment
kubectl get pods -n soam
```

---

## Deploy Script Reference

```powershell
# Full deployment
.\deploy.ps1 -Action deploy

# Deploy only infrastructure (Step 1)
.\deploy.ps1 -Action deploy -Step 1

# Deploy only Kubernetes (Step 2)
.\deploy.ps1 -Action deploy -Step 2

# Skip image rebuild
.\deploy.ps1 -Action deploy -Step 2 -SkipImages

# Rebuild images only
.\deploy.ps1 -Action images-only

# Check status
.\deploy.ps1 -Action status

# Destroy everything
.\deploy.ps1 -Action destroy

# Destroy only Kubernetes (keep infra)
.\deploy.ps1 -Action destroy -Step 2
```

---

## Cost Estimation

| Resource | SKU | Monthly Cost |
|----------|-----|-------------:|
| AKS (3 nodes) | Standard_DS2_v2 | ~$300 |
| ACR | Basic | ~$5 |
| Storage (PVCs) | Premium SSD | ~$20 |
| Load Balancers | Standard | ~$50 |
| **Total** | | **~$375** |

> 💡 **Cost Savings**: Use `Standard_B2s` VMs and 2 nodes for dev/testing (~$60/month)

---

## Troubleshooting

### Connect to AKS Cluster

```powershell
# Get credentials
az aks get-credentials --resource-group soam-rg --name soam-aks-cluster --overwrite-existing

# Verify connection
kubectl cluster-info
kubectl get nodes

# Switch contexts (if multiple clusters)
kubectl config get-contexts
kubectl config use-context soam-aks-cluster
```

### Port Forward to Local Machine

```powershell
# Individual services
kubectl port-forward svc/frontend 3000:80 -n soam
kubectl port-forward svc/backend-external 8000:8000 -n soam
kubectl port-forward svc/ingestor-external 8001:8001 -n soam
kubectl port-forward svc/minio 9000:9000 9090:9090 -n soam
kubectl port-forward svc/neo4j 7474:7474 7687:7687 -n soam
kubectl port-forward svc/soam-spark-master-svc 8080:80 -n soam

# Multiple in background
Start-Job { kubectl port-forward svc/frontend 3000:80 -n soam }
Start-Job { kubectl port-forward svc/backend-external 8000:8000 -n soam }
Start-Job { kubectl port-forward svc/minio 9000:9000 9090:9090 -n soam }

# Stop all port-forwards
Get-Process kubectl -ErrorAction SilentlyContinue | Stop-Process
```

### Check Pod Status

```powershell
# List pods
kubectl get pods -n soam

# Get all resources
kubectl get all -n soam

# Watch pods in real-time
kubectl get pods -n soam -w
```

### Debug Failing Pods

```powershell
# Describe pod (shows events and errors)
kubectl describe pod <pod-name> -n soam

# View logs
kubectl logs <pod-name> -n soam

# View previous container logs (crashed pods)
kubectl logs <pod-name> -n soam --previous

# Follow logs in real-time
kubectl logs -f <pod-name> -n soam

# Get shell inside pod
kubectl exec -it <pod-name> -n soam -- /bin/bash
```

### Check Images in ACR

```powershell
# List all repositories
az acr repository list --name <acr-name> -o table

# List tags for specific image
az acr repository show-tags --name <acr-name> --repository backend -o table

# Check if image exists
az acr repository show --name <acr-name> --image backend:latest
```

### Check Services and Load Balancers

```powershell
# List services (shows external IPs)
kubectl get svc -n soam

# Wait for external IP assignment
kubectl get svc -n soam -w

# Describe service for endpoint details
kubectl describe svc backend-external -n soam
```

### Check Storage (PVCs)

```powershell
# List PVCs
kubectl get pvc -n soam

# Describe PVC (shows binding status)
kubectl describe pvc <pvc-name> -n soam

# List storage classes
kubectl get storageclass
```

### Check Cluster Events

```powershell
# Recent events (sorted by time)
kubectl get events -n soam --sort-by='.lastTimestamp'

# Events for specific pod
kubectl get events -n soam --field-selector involvedObject.name=<pod-name>

# All events in cluster
kubectl get events -A --sort-by='.lastTimestamp'
```

### Check Resource Usage

```powershell
# Pod resource usage
kubectl top pods -n soam

# Node resource usage
kubectl top nodes

# Detailed pod metrics
kubectl describe pod <pod-name> -n soam | Select-String -Pattern "cpu|memory" -Context 0,2
```

### Restart Services

```powershell
# Restart deployment
kubectl rollout restart deployment/<name> -n soam

# Restart statefulset
kubectl rollout restart statefulset/<name> -n soam

# Check rollout status
kubectl rollout status deployment/<name> -n soam
```

### Common Issues

**Pod stuck in Pending:**
```powershell
# Check events for scheduling issues
kubectl describe pod <pod-name> -n soam | Select-String -Pattern "Events:" -Context 0,20
# Usually: insufficient resources or PVC not bound
```

**Pod in CrashLoopBackOff:**
```powershell
# Check logs from crashed container
kubectl logs <pod-name> -n soam --previous
# Check if image exists and is accessible
```

**ImagePullBackOff:**
```powershell
# Verify image exists in ACR
az acr repository show --name <acr-name> --image <image>:latest
# Check AKS has ACR pull permissions
az aks check-acr --name soam-aks-cluster --resource-group soam-rg --acr <acr-name>.azurecr.io
```

**Service has no external IP:**
```powershell
# Wait longer (can take 2-5 minutes)
kubectl get svc -n soam -w
# Check Azure load balancer in portal if stuck
```

**PVC stuck in Pending:**
```powershell
# Check storage class exists
kubectl get storageclass
# PVCs with WaitForFirstConsumer bind when pod is scheduled
kubectl describe pvc <pvc-name> -n soam
```

### Terraform Issues

```powershell
# View Terraform state
cd terraform/02-kubernetes-resources
terraform state list

# Refresh state from cluster
terraform refresh

# Force recreation of resource
terraform taint <resource-address>
terraform apply

# Import existing resource
terraform import <resource-address> <resource-id>
```

### Reset Everything

```powershell
# Delete all pods (they will restart)
kubectl delete pods --all -n soam

# Delete and recreate namespace (CAUTION: deletes all data)
kubectl delete namespace soam
cd terraform/02-kubernetes-resources
terraform apply

# Full destroy and redeploy
cd terraform
.\deploy.ps1 -Action destroy
.\deploy.ps1 -Action deploy
```
