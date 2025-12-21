# GitHub Actions CI/CD Pipeline Setup

This document describes how to set up and use the GitHub Actions CI/CD pipelines for SOAM.

## Overview

The CI/CD pipeline consists of four manual workflows:

| Workflow | Purpose |
|----------|---------|
| **1️⃣ Deploy Infrastructure** | Create Azure resources (AKS + ACR) via Terraform |
| **2️⃣ Deploy Application** | Build images + deploy K8s resources via Terraform |
| **3️⃣ Update Images** | Rebuild specific images and restart pods |
| **4️⃣ Cleanup (Destroy All)** | Delete all Azure resources |

## Prerequisites

### 1. Create Azure Service Principal

You can use the setup script or create manually:

**Option A: Use Setup Script (Recommended)**
```powershell
.\scripts\setup-github-actions.ps1 -GitHubRepo "vladtf/soam"
```

This script will:
- Create an Azure Service Principal
- Output the JSON credentials for GitHub
- Optionally set the secret automatically (if GitHub CLI is installed)

**Option B: Create Manually**

Create a service principal for GitHub Actions to authenticate with Azure:

```bash
# Login to Azure
az login

# Get your subscription ID
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Create service principal with Contributor role on subscription level
az ad sp create-for-rbac \
  --name "soam-github-actions" \
  --role contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID \
  --sdk-auth
```

Save the JSON output - you'll need it for the `AZURE_CREDENTIALS` secret.

> [!TIP]
> To check existing secrets via GitHub CLI:
> ```bash
> gh secret list
> ```

### 2. Configure GitHub Secrets

Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret Name | Description |
|-------------|-------------|
| `AZURE_CREDENTIALS` | Service principal JSON from step above |

## Workflows

### 1️⃣ Deploy Infrastructure

Creates the foundational Azure resources using Terraform Step 1.

**Parameters:**
- `location`: Azure region (default: West Europe)
- `aks_node_count`: Number of AKS nodes (default: 3)

**What it creates:**
- Azure Resource Group (`soam-rg`)
- Azure Container Registry (ACR)
- Azure Kubernetes Service (AKS)

```powershell
gh workflow run "1️⃣ Deploy Infrastructure"; gh run watch
```

### 2️⃣ Deploy Application

Builds all Docker images, pushes to ACR, and deploys Kubernetes resources.

**Parameters:**
- `skip_image_build`: Skip building images, use existing (default: false)

**What it does:**
1. Gets infrastructure info from Terraform Step 1
2. Builds and pushes all service images to ACR
3. Deploys all Kubernetes resources via Terraform Step 2

```powershell
gh workflow run "2️⃣ Deploy Application"; gh run watch
```

### 3️⃣ Update Images

Rebuilds specific images and optionally restarts the corresponding pods.

**Parameters:**
- `images`: Comma-separated list of images (default: backend,frontend,ingestor)
- `restart_pods`: Restart pods after push (default: true)

**Available images:**
- `backend`, `frontend`, `ingestor`
- `spark`, `simulator`, `rest-api-simulator`
- `mosquitto`, `grafana`, `prometheus`

```powershell
gh workflow run "3️⃣ Update Images" -f images=backend,frontend -f restart_pods=true; gh run watch
```

### 4️⃣ Cleanup (Destroy All)

⚠️ **DANGER**: Destroys all Azure resources!

**Parameters:**
- `confirm`: Must type "DESTROY" to proceed
- `delete_step`: What to delete (all, kubernetes-only, infrastructure-only)

```powershell
gh workflow run "4️⃣ Cleanup (Destroy All)" -f confirm=DESTROY -f delete_step=all; gh run watch
```

## Deployment Flow

```
┌─────────────────────────────────────┐
│  1️⃣ Deploy Infrastructure           │
│  (Creates AKS + ACR)                │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  2️⃣ Deploy Application              │
│  (Builds images + K8s resources)   │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  3️⃣ Update Images (as needed)       │
│  (Rebuild + restart specific pods) │
└─────────────────────────────────────┘
```

## Docker Caching

Images use ACR registry caching for faster builds:

```yaml
cache-from: type=registry,ref=acr.azurecr.io/image:buildcache
cache-to: type=registry,ref=acr.azurecr.io/image:buildcache,mode=max
```

**Benefits:**
- Shared across all workflow runs
- Persists indefinitely in ACR
- Significantly faster rebuilds

## Troubleshooting

### "Resource already exists" Error

If you see an error like:
```
Error: A resource with the ID "..." already exists - to be managed via Terraform this resource needs to be imported into the State.
```

This happens when Azure resources exist but Terraform doesn't know about them (state mismatch). Solutions:

**Option A: Delete existing resources (recommended for fresh start)**
```bash
# Delete the resource group and all contents
az group delete --name soam-rg --yes --no-wait

# Wait for deletion to complete
az group wait --name soam-rg --deleted

# Then re-run the workflow
```

**Option B: Import existing resources into state**

This is complex and requires running Terraform locally. See [Terraform Import](https://developer.hashicorp.com/terraform/cli/import) documentation.

### Terraform State

The workflows use Azure Storage to persist Terraform state:
- **Resource Group:** `soam-tfstate-rg`
- **Storage Account:** `soamtfstate<subscription-id-prefix>`
- **Container:** `tfstate`
- **State files:** `01-infrastructure.tfstate`, `02-kubernetes.tfstate`

This ensures state persists across workflow runs and multiple team members can deploy.

### Check Deployment Status

```bash
# Get AKS credentials
az aks get-credentials --resource-group soam-rg --name soam-aks-cluster

# Check pods
kubectl get pods -n soam

# Check logs
kubectl logs -f deployment/backend -n soam
```

### Image Push Failures

```bash
# Check ACR permissions
az aks check-acr --name soam-aks-cluster --resource-group soam-rg --acr <acr-name>.azurecr.io
```

### Terraform State Issues

If Terraform state gets corrupted, you may need to:
1. Delete state files in the GitHub runner (they're ephemeral anyway)
2. Import existing resources or destroy and recreate

### Terraform State Lock Issues

If a workflow fails while holding the state lock, you'll see an error like:
```
Error: Error acquiring the state lock
Error message: state blob is already locked
```

The workflows now **automatically release the lock on failure**, but if you need to manually unlock:

```powershell
# Login to Azure
az login --tenant a0867c7c-7aeb-44cb-96ed-32fa642ebe73

# Break the lease on the locked state file (replace filename as needed)
# For kubernetes state:
az storage blob lease break --blob-name "02-kubernetes.tfstate" --container-name "tfstate" --account-name "soamtfstate60344ef8" --auth-mode key

# For infrastructure state:
az storage blob lease break --blob-name "01-infrastructure.tfstate" --container-name "tfstate" --account-name "soamtfstate60344ef8" --auth-mode key
```

> **Note:** Replace `soamtfstate60344ef8` with your actual storage account name (first 8 chars of subscription ID).

## Quick Reference

```powershell
# Deploy everything from scratch
gh workflow run "1️⃣ Deploy Infrastructure"; gh run watch
gh workflow run "2️⃣ Deploy Application"; gh run watch

# Update specific services
gh workflow run "3️⃣ Update Images" -f images=backend,ingestor; gh run watch

# Destroy everything
gh workflow run "4️⃣ Cleanup (Destroy All)" -f confirm=DESTROY; gh run watch
```
