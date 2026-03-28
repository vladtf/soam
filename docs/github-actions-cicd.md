# GitHub Actions CI/CD Pipeline

CI/CD for SOAM uses four **manual** GitHub Actions workflows that deploy to Azure (AKS + ACR) via Terraform.

---

## Table of Contents

- [GitHub Actions CI/CD Pipeline](#github-actions-cicd-pipeline)
  - [Table of Contents](#table-of-contents)
  - [Quick Reference](#quick-reference)
  - [Deployment Flow](#deployment-flow)
  - [Workflows](#workflows)
    - [1️⃣ Deploy Infrastructure](#1️⃣-deploy-infrastructure)
    - [2️⃣ Deploy Application](#2️⃣-deploy-application)
    - [3️⃣ Update Images](#3️⃣-update-images)
    - [4️⃣ Cleanup (Destroy All)](#4️⃣-cleanup-destroy-all)
  - [Initial Setup (One-Time)](#initial-setup-one-time)
    - [Step 1: Create Azure Service Principal](#step-1-create-azure-service-principal)
    - [Step 2: Configure GitHub Secret](#step-2-configure-github-secret)
  - [Docker Caching](#docker-caching)
  - [Troubleshooting](#troubleshooting)
    - [Check Deployment Status](#check-deployment-status)
    - ["Resource already exists" Error](#resource-already-exists-error)
    - [Image Push Failures](#image-push-failures)
    - [Terraform State Lock](#terraform-state-lock)
    - [Terraform State Storage](#terraform-state-storage)

---

## Quick Reference

```powershell
# Full deployment from scratch (run in order)
gh workflow run "1️⃣ Deploy Infrastructure"; gh run watch
gh workflow run "2️⃣ Deploy Application"; gh run watch

# Deploy with custom infrastructure parameters
gh workflow run "1️⃣ Deploy Infrastructure" -f aks_vm_size=Standard_D4s_v5 -f aks_node_count=4; gh run watch

# Update specific services (no infra changes needed)
gh workflow run "3️⃣ Update Images" -f images=backend,ingestor; gh run watch

# Tear down everything
gh workflow run "4️⃣ Cleanup (Destroy All)" -f confirm=DESTROY; gh run watch
```

---

## Deployment Flow

Run the workflows in this order for a fresh deployment:

```
1️⃣ Deploy Infrastructure  ──►  2️⃣ Deploy Application  ──►  3️⃣ Update Images (as needed)
   (AKS + ACR)                   (Build + K8s deploy)         (Rebuild specific pods)
```

After the initial setup, use **3️⃣ Update Images** to push changes without redeploying infrastructure.

---

## Workflows

### 1️⃣ Deploy Infrastructure

Creates the foundational Azure resources using Terraform.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `location` | West Europe | Azure region |
| `aks_node_count` | 3 | Number of AKS nodes |
| `aks_vm_size` | Standard_B2s | AKS node VM size |

**Creates:** Resource Group (`soam-rg`) · Container Registry (ACR) · Kubernetes Service (AKS)

```powershell
gh workflow run "1️⃣ Deploy Infrastructure"; gh run watch

# With custom VM size
gh workflow run "1️⃣ Deploy Infrastructure" -f aks_vm_size=Standard_D4s_v5 -f aks_node_count=4; gh run watch
```

---

### 2️⃣ Deploy Application

Builds all Docker images, pushes to ACR, and deploys Kubernetes resources.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `skip_image_build` | false | Skip building images, use existing |

**Steps:** Get infra info from Terraform → Build & push images to ACR → Deploy K8s resources

```powershell
gh workflow run "2️⃣ Deploy Application"; gh run watch
```

---

### 3️⃣ Update Images

Rebuilds specific images and optionally restarts the corresponding pods.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `images` | backend,frontend,ingestor | Comma-separated list of images to rebuild |
| `restart_pods` | true | Restart pods after push |

**Available images:** `backend` · `frontend` · `ingestor` · `spark` · `simulator` · `rest-api-simulator` · `mosquitto` · `grafana` · `prometheus`

```powershell
gh workflow run "3️⃣ Update Images" -f images=backend,frontend -f restart_pods=true; gh run watch
```

---

### 4️⃣ Cleanup (Destroy All)

> ⚠️ **DANGER**: Destroys all Azure resources. This cannot be undone.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `confirm` | *(required)* | Must type `DESTROY` to proceed |
| `delete_step` | all | What to delete: `all`, `kubernetes-only`, `infrastructure-only` |

```powershell
gh workflow run "4️⃣ Cleanup (Destroy All)" -f confirm=DESTROY -f delete_step=all; gh run watch
```

---

## Initial Setup (One-Time)

Before running any workflow, you need an Azure Service Principal and a GitHub secret.

### Step 1: Create Azure Service Principal

**Option A: Setup Script (Recommended)**

```powershell
.\scripts\setup-github-actions.ps1 -GitHubRepo "vladtf/soam"
```

This creates the service principal and optionally sets the GitHub secret automatically.

**Option B: Manual**

```bash
az login
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

az ad sp create-for-rbac \
  --name "soam-github-actions" \
  --role contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID \
  --sdk-auth
```

Save the JSON output for the next step.

### Step 2: Configure GitHub Secret

Go to **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Secret Name | Value |
|-------------|-------|
| `AZURE_CREDENTIALS` | Service principal JSON from Step 1 |

> [!TIP]
> Verify secrets: `gh secret list`

---

## Docker Caching

All image builds use ACR registry caching for faster rebuilds:

```yaml
cache-from: type=registry,ref=acr.azurecr.io/image:buildcache
cache-to: type=registry,ref=acr.azurecr.io/image:buildcache,mode=max
```

Caches are shared across workflow runs and persist indefinitely in ACR.

---

## Troubleshooting

### Check Deployment Status

```bash
az aks get-credentials --resource-group soam-rg --name soam-aks-cluster
kubectl config set-context --current --namespace=soam
kubectl get pods -n soam
kubectl logs -f statefulset/backend -n soam
```

### "Resource already exists" Error

Azure resources exist but Terraform state doesn't track them. Fix by deleting and recreating:

```bash
az group delete --name soam-rg --yes --no-wait
az group wait --name soam-rg --deleted
# Then re-run the Deploy Infrastructure workflow
```

Alternatively, [import resources into Terraform state](https://developer.hashicorp.com/terraform/cli/import) (advanced).

### Image Push Failures

```bash
az aks check-acr --name soam-aks-cluster --resource-group soam-rg --acr <acr-name>.azurecr.io
```

### Terraform State Lock

If a workflow fails mid-run, the state blob may stay locked:

```
Error: Error acquiring the state lock
Error message: state blob is already locked
```

Locks are **auto-released on failure**, but to manually unlock:

```powershell
az login --tenant a0867c7c-7aeb-44cb-96ed-32fa642ebe73

# Unlock kubernetes state
az storage blob lease break --blob-name "02-kubernetes.tfstate" --container-name "tfstate" --account-name "soamtfstate60344ef8" --auth-mode key

# Unlock infrastructure state
az storage blob lease break --blob-name "01-infrastructure.tfstate" --container-name "tfstate" --account-name "soamtfstate60344ef8" --auth-mode key
```

> **Note:** Replace `soamtfstate60344ef8` with your actual storage account name (first 8 chars of subscription ID).

### Terraform State Storage

State is persisted in Azure Storage so it survives across workflow runs:

| Resource | Value |
|----------|-------|
| Resource Group | `soam-tfstate-rg` |
| Storage Account | `soamtfstate<subscription-id-prefix>` |
| Container | `tfstate` |
| State files | `01-infrastructure.tfstate`, `02-kubernetes.tfstate` |

If state gets corrupted, delete the state files (runners are ephemeral) and either import existing resources or destroy and recreate.
