<#
.SYNOPSIS
    SOAM Azure Deployment Script

.DESCRIPTION
    This script orchestrates the deployment of SOAM to Azure:
    1. Creates Azure infrastructure (AKS + ACR) using Terraform
    2. Builds and pushes Docker images to ACR
    3. Deploys Kubernetes resources using Terraform

.PARAMETER Action
    The action to perform: 'deploy', 'destroy', 'status', 'images-only', or 'port-forward'

.PARAMETER SkipImages
    Skip building and pushing Docker images (use existing images)

.PARAMETER Step
    Run only a specific step: '1' (Azure), '2' (Kubernetes), or 'all' (default)

.EXAMPLE
    .\deploy.ps1 -Action deploy
    .\deploy.ps1 -Action deploy -SkipImages
    .\deploy.ps1 -Action deploy -Step 1
    .\deploy.ps1 -Action destroy
    .\deploy.ps1 -Action status
    .\deploy.ps1 -Action port-forward

.NOTES
    Prerequisites:
    - Azure CLI installed and logged in (az login)
    - Terraform >= 1.0.0
    - Docker Desktop running
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('deploy', 'destroy', 'status', 'images-only', 'port-forward')]
    [string]$Action,

    [switch]$SkipImages,

    [ValidateSet('1', '2', 'all')]
    [string]$Step = 'all'
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptRoot
$Step1Dir = Join-Path $ScriptRoot "01-azure-infrastructure"
$Step2Dir = Join-Path $ScriptRoot "02-kubernetes-resources"

# Colors for output
function Write-Header { param($msg) Write-Host "`n========================================" -ForegroundColor Cyan; Write-Host $msg -ForegroundColor Cyan; Write-Host "========================================" -ForegroundColor Cyan }
function Write-Step { param($msg) Write-Host "`n>> $msg" -ForegroundColor Yellow }
function Write-Success { param($msg) Write-Host "✅ $msg" -ForegroundColor Green }
function Write-Error { param($msg) Write-Host "❌ $msg" -ForegroundColor Red }
function Write-Info { param($msg) Write-Host "ℹ️  $msg" -ForegroundColor Blue }

# Check prerequisites
function Test-Prerequisites {
    Write-Step "Checking prerequisites..."
    
    # Check Azure CLI
    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        Write-Error "Azure CLI not found. Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
        exit 1
    }
    
    # Check if logged in to Azure
    $account = az account show 2>$null | ConvertFrom-Json
    if (-not $account) {
        Write-Error "Not logged in to Azure. Run 'az login' first."
        exit 1
    }
    Write-Info "Logged in as: $($account.user.name) (Subscription: $($account.name))"
    
    # Check Terraform
    if (-not (Get-Command terraform -ErrorAction SilentlyContinue)) {
        Write-Error "Terraform not found. Install from: https://www.terraform.io/downloads"
        exit 1
    }
    $tfVersion = terraform version -json | ConvertFrom-Json
    Write-Info "Terraform version: $($tfVersion.terraform_version)"
    
    # Check Docker
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error "Docker not found. Install Docker Desktop."
        exit 1
    }
    
    # Check if Docker is running
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker is not running. Start Docker Desktop first."
        exit 1
    }
    Write-Info "Docker is running"
    
    Write-Success "All prerequisites met"
}

# Deploy Step 1: Azure Infrastructure
function Deploy-AzureInfrastructure {
    Write-Header "Step 1: Deploying Azure Infrastructure (AKS + ACR)"
    
    Push-Location $Step1Dir
    try {
        # Check for terraform.tfvars
        if (-not (Test-Path "terraform.tfvars")) {
            if (Test-Path "terraform.tfvars.example") {
                Write-Error "terraform.tfvars not found. Copy terraform.tfvars.example to terraform.tfvars and configure it."
                exit 1
            }
        }
        
        Write-Step "Initializing Terraform..."
        terraform init
        if ($LASTEXITCODE -ne 0) { throw "Terraform init failed" }
        
        Write-Step "Planning infrastructure..."
        terraform plan -out=tfplan
        if ($LASTEXITCODE -ne 0) { throw "Terraform plan failed" }
        
        Write-Step "Applying infrastructure (this may take 10-15 minutes)..."
        terraform apply tfplan
        if ($LASTEXITCODE -ne 0) { throw "Terraform apply failed" }
        
        # Clean up plan file
        Remove-Item tfplan -ErrorAction SilentlyContinue
        
        Write-Success "Azure infrastructure deployed successfully"
        
        # Show outputs
        Write-Step "Infrastructure outputs:"
        terraform output
    }
    finally {
        Pop-Location
    }
}

# Get outputs from Step 1
function Get-Step1Outputs {
    Push-Location $Step1Dir
    try {
        $outputs = @{
            acr_login_server           = terraform output -raw acr_login_server 2>$null
            acr_name                   = terraform output -raw acr_name 2>$null
            aks_host                   = terraform output -raw aks_host 2>$null
            aks_client_certificate     = terraform output -raw aks_client_certificate 2>$null
            aks_client_key             = terraform output -raw aks_client_key 2>$null
            aks_cluster_ca_certificate = terraform output -raw aks_cluster_ca_certificate 2>$null
            resource_group_name        = terraform output -raw resource_group_name 2>$null
            aks_cluster_name           = terraform output -raw aks_cluster_name 2>$null
        }
        return $outputs
    }
    finally {
        Pop-Location
    }
}

# Build and push Docker images
function Build-AndPushImages {
    param($AcrServer, $AcrName)
    
    Write-Header "Building and Pushing Docker Images"
    
    # Login to ACR
    Write-Step "Logging in to ACR..."
    az acr login --name $AcrName
    if ($LASTEXITCODE -ne 0) { throw "ACR login failed" }
    
    # Define images to build
    $images = @(
        @{ Name = "backend"; Path = "backend" },
        @{ Name = "frontend"; Path = "frontend" },
        @{ Name = "ingestor"; Path = "ingestor" },
        @{ Name = "mosquitto"; Path = "mosquitto" },
        @{ Name = "spark"; Path = "spark" },
        @{ Name = "simulator"; Path = "simulator" },
        @{ Name = "prometheus"; Path = "prometheus" },
        @{ Name = "grafana"; Path = "grafana" }
    )
    
    Push-Location $ProjectRoot
    try {
        foreach ($image in $images) {
            $imageName = $image.Name
            $imagePath = $image.Path
            $fullImageName = "$AcrServer/${imageName}:latest"
            
            if (-not (Test-Path $imagePath)) {
                Write-Info "Skipping $imageName (path not found: $imagePath)"
                continue
            }
            
            Write-Step "Building $imageName..."
            docker build -t $fullImageName "./$imagePath"
            if ($LASTEXITCODE -ne 0) { throw "Failed to build $imageName" }
            
            Write-Step "Pushing $imageName..."
            docker push $fullImageName
            if ($LASTEXITCODE -ne 0) { throw "Failed to push $imageName" }
            
            Write-Success "$imageName pushed to ACR"
        }
    }
    finally {
        Pop-Location
    }
    
    Write-Success "All images built and pushed successfully"
}

# Deploy Step 2: Kubernetes Resources
function Deploy-KubernetesResources {
    param($Step1Outputs)
    
    Write-Header "Step 2: Deploying Kubernetes Resources"
    
    Push-Location $Step2Dir
    try {
        # Create terraform.tfvars with Step 1 outputs
        Write-Step "Configuring Terraform with AKS credentials..."
        
        # Read existing tfvars if present, or use example
        $existingVars = @{}
        if (Test-Path "terraform.tfvars") {
            Get-Content "terraform.tfvars" | ForEach-Object {
                if ($_ -match '^\s*([a-z_]+)\s*=\s*"?([^"]*)"?\s*$') {
                    $existingVars[$matches[1]] = $matches[2]
                }
            }
        }
        elseif (Test-Path "terraform.tfvars.example") {
            Get-Content "terraform.tfvars.example" | ForEach-Object {
                if ($_ -match '^\s*([a-z_]+)\s*=\s*"?([^"]*)"?\s*$') {
                    $existingVars[$matches[1]] = $matches[2]
                }
            }
        }
        
        # Build tfvars content with Step 1 outputs + existing config
        $tfvarsContent = @"
# Auto-generated from Step 1 outputs
aks_host                   = "$($Step1Outputs.aks_host)"
aks_client_certificate     = "$($Step1Outputs.aks_client_certificate)"
aks_client_key             = "$($Step1Outputs.aks_client_key)"
aks_cluster_ca_certificate = "$($Step1Outputs.aks_cluster_ca_certificate)"
acr_login_server           = "$($Step1Outputs.acr_login_server)"

# Application configuration
kubernetes_namespace = "$($existingVars['kubernetes_namespace'] ?? 'soam')"
minio_root_user      = "$($existingVars['minio_root_user'] ?? 'minio')"
minio_root_password  = "$($existingVars['minio_root_password'] ?? 'minio123')"
minio_storage_size   = "$($existingVars['minio_storage_size'] ?? '10Gi')"
neo4j_password       = "$($existingVars['neo4j_password'] ?? 'verystrongpassword')"
spark_worker_count   = $($existingVars['spark_worker_count'] ?? '2')
frontend_replicas    = $($existingVars['frontend_replicas'] ?? '1')
ingestor_replicas    = $($existingVars['ingestor_replicas'] ?? '1')
deploy_simulator          = $($existingVars['deploy_simulator'] ?? 'true')
deploy_rest_api_simulator = $($existingVars['deploy_rest_api_simulator'] ?? 'false')
deploy_monitoring         = $($existingVars['deploy_monitoring'] ?? 'false')
grafana_admin_password    = "$($existingVars['grafana_admin_password'] ?? 'admin')"
"@
        
        # Add optional Azure OpenAI config if present
        if ($existingVars['azure_openai_endpoint']) {
            $tfvarsContent += "`nazure_openai_endpoint    = `"$($existingVars['azure_openai_endpoint'])`""
        }
        if ($existingVars['azure_openai_key']) {
            $tfvarsContent += "`nazure_openai_key         = `"$($existingVars['azure_openai_key'])`""
        }
        if ($existingVars['azure_openai_api_version']) {
            $tfvarsContent += "`nazure_openai_api_version = `"$($existingVars['azure_openai_api_version'])`""
        }
        
        $tfvarsContent | Out-File -FilePath "terraform.tfvars" -Encoding utf8
        
        Write-Step "Initializing Terraform..."
        terraform init
        if ($LASTEXITCODE -ne 0) { throw "Terraform init failed" }
        
        Write-Step "Planning Kubernetes resources..."
        terraform plan -out=tfplan
        if ($LASTEXITCODE -ne 0) { throw "Terraform plan failed" }
        
        Write-Step "Applying Kubernetes resources..."
        terraform apply tfplan
        if ($LASTEXITCODE -ne 0) { throw "Terraform apply failed" }
        
        # Clean up plan file
        Remove-Item tfplan -ErrorAction SilentlyContinue
        
        Write-Success "Kubernetes resources deployed successfully"
        
        # Show outputs
        Write-Step "Application URLs:"
        terraform output
    }
    finally {
        Pop-Location
    }
}

# Destroy infrastructure
function Destroy-Infrastructure {
    param([string]$TargetStep)
    
    Write-Header "Destroying Infrastructure"
    
    if ($TargetStep -eq 'all' -or $TargetStep -eq '2') {
        if (Test-Path "$Step2Dir/terraform.tfstate") {
            Write-Step "Destroying Kubernetes resources (Step 2)..."
            Push-Location $Step2Dir
            try {
                terraform destroy -auto-approve
            }
            finally {
                Pop-Location
            }
        }
    }
    
    if ($TargetStep -eq 'all' -or $TargetStep -eq '1') {
        if (Test-Path "$Step1Dir/terraform.tfstate") {
            Write-Step "Destroying Azure infrastructure (Step 1)..."
            Push-Location $Step1Dir
            try {
                terraform destroy -auto-approve
            }
            finally {
                Pop-Location
            }
        }
    }
    
    Write-Success "Infrastructure destroyed"
}

# Show deployment status
function Show-Status {
    Write-Header "Deployment Status"
    
    # Step 1 status
    Write-Step "Step 1: Azure Infrastructure"
    if (Test-Path "$Step1Dir/terraform.tfstate") {
        Push-Location $Step1Dir
        try {
            $state = terraform show -json 2>$null | ConvertFrom-Json
            if ($state.values.root_module.resources.Count -gt 0) {
                Write-Success "Deployed"
                Write-Info "Resource Group: $(terraform output -raw resource_group_name 2>$null)"
                Write-Info "ACR: $(terraform output -raw acr_login_server 2>$null)"
                Write-Info "AKS: $(terraform output -raw aks_cluster_name 2>$null)"
            }
            else {
                Write-Info "Not deployed"
            }
        }
        finally {
            Pop-Location
        }
    }
    else {
        Write-Info "Not deployed"
    }
    
    # Step 2 status
    Write-Step "Step 2: Kubernetes Resources"
    if (Test-Path "$Step2Dir/terraform.tfstate") {
        Push-Location $Step2Dir
        try {
            $state = terraform show -json 2>$null | ConvertFrom-Json
            if ($state.values.root_module.resources.Count -gt 0) {
                Write-Success "Deployed"
                Write-Info "Frontend: $(terraform output -raw frontend_url 2>$null)"
                Write-Info "Backend: $(terraform output -raw backend_url 2>$null)"
                Write-Info "Ingestor: $(terraform output -raw ingestor_url 2>$null)"
            }
            else {
                Write-Info "Not deployed"
            }
        }
        finally {
            Pop-Location
        }
    }
    else {
        Write-Info "Not deployed"
    }
}

# Port forward all SOAM services to localhost
function Start-PortForward {
    Write-Header "Port Forwarding SOAM Services"
    
    # Get namespace from Step 2 outputs
    Push-Location $Step2Dir
    try {
        $namespace = terraform output -raw namespace 2>$null
        if (-not $namespace) {
            $namespace = "soam"
        }
    }
    finally {
        Pop-Location
    }
    
    Write-Info "Namespace: $namespace"
    Write-Step "Starting port forwards..."
    
    # Define services to forward
    $portForwards = @(
        @{ Name = "Frontend";        Service = "svc/frontend";         LocalPort = 3000;  RemotePort = 80 },
        @{ Name = "Backend";         Service = "svc/backend-external"; LocalPort = 8000;  RemotePort = 8000 },
        @{ Name = "Ingestor";        Service = "svc/ingestor";         LocalPort = 8001;  RemotePort = 8001 },
        @{ Name = "MinIO API";       Service = "svc/minio";            LocalPort = 9000;  RemotePort = 9000 },
        @{ Name = "MinIO Console";   Service = "svc/minio";            LocalPort = 9090;  RemotePort = 9090 },
        @{ Name = "Neo4j Browser";   Service = "svc/neo4j";            LocalPort = 7474;  RemotePort = 7474 },
        @{ Name = "Neo4j Bolt";      Service = "svc/neo4j";            LocalPort = 7687;  RemotePort = 7687 },
        @{ Name = "Spark Master UI"; Service = "svc/soam-spark-master-svc"; LocalPort = 8080;  RemotePort = 80 },
        @{ Name = "Prometheus";      Service = "svc/prometheus";       LocalPort = 9091;  RemotePort = 9090 },
        @{ Name = "Grafana";         Service = "svc/grafana";          LocalPort = 3001;  RemotePort = 3000 }
    )
    
    $jobs = @()
    $successfulForwards = @()
    
    foreach ($pf in $portForwards) {
        Write-Host "  Starting $($pf.Name) (localhost:$($pf.LocalPort) -> $($pf.RemotePort))..." -NoNewline
        
        # Start kubectl port-forward as a background job
        $job = Start-Job -ScriptBlock {
            param($namespace, $service, $localPort, $remotePort)
            kubectl port-forward -n $namespace $service "${localPort}:${remotePort}" 2>&1
        } -ArgumentList $namespace, $pf.Service, $pf.LocalPort, $pf.RemotePort
        
        # Wait a moment to check if it started successfully
        Start-Sleep -Milliseconds 500
        
        if ($job.State -eq "Running") {
            Write-Host " ✅" -ForegroundColor Green
            $jobs += $job
            $successfulForwards += $pf
        }
        else {
            Write-Host " ⚠️  (service may not exist)" -ForegroundColor Yellow
            Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
        }
    }
    
    if ($jobs.Count -eq 0) {
        Write-Error "No port forwards could be started. Is the cluster deployed?"
        return
    }
    
    Write-Host ""
    Write-Success "Port forwarding active for $($jobs.Count) services"
    Write-Host ""
    Write-Host "Available endpoints:" -ForegroundColor Cyan
    foreach ($pf in $successfulForwards) {
        $url = if ($pf.LocalPort -eq 7687) { "bolt://localhost:$($pf.LocalPort)" } else { "http://localhost:$($pf.LocalPort)" }
        Write-Host "  • $($pf.Name.PadRight(16)) -> $url" -ForegroundColor White
    }
    Write-Host ""
    Write-Host "Press Ctrl+C to stop all port forwards..." -ForegroundColor Yellow
    Write-Host ""
    
    # Register cleanup handler for Ctrl+C
    $null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
        Get-Job | Where-Object { $_.State -eq "Running" } | Stop-Job -PassThru | Remove-Job -Force
    }
    
    try {
        # Keep script running and monitor jobs
        while ($true) {
            $runningJobs = $jobs | Where-Object { $_.State -eq "Running" }
            if ($runningJobs.Count -eq 0) {
                Write-Warning "All port forwards have stopped"
                break
            }
            Start-Sleep -Seconds 2
        }
    }
    finally {
        Write-Host "`n"
        Write-Step "Stopping port forwards..."
        foreach ($job in $jobs) {
            Stop-Job -Job $job -ErrorAction SilentlyContinue
            Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
        }
        Write-Success "All port forwards stopped"
        
        # Unregister the event handler
        Unregister-Event -SourceIdentifier PowerShell.Exiting -ErrorAction SilentlyContinue
    }
}

# Main execution
try {
    Write-Header "SOAM Azure Deployment"
    Write-Info "Action: $Action"
    if ($Action -eq 'deploy') {
        Write-Info "Step: $Step"
        Write-Info "Skip Images: $SkipImages"
    }
    
    switch ($Action) {
        'deploy' {
            Test-Prerequisites
            
            if ($Step -eq 'all' -or $Step -eq '1') {
                Deploy-AzureInfrastructure
            }
            
            # Get Step 1 outputs (needed for images and Step 2)
            $step1Outputs = Get-Step1Outputs
            if (-not $step1Outputs.acr_login_server) {
                Write-Error "Step 1 outputs not available. Run Step 1 first."
                exit 1
            }
            
            if (-not $SkipImages -and ($Step -eq 'all' -or $Step -eq '2')) {
                Build-AndPushImages -AcrServer $step1Outputs.acr_login_server -AcrName $step1Outputs.acr_name
            }
            
            if ($Step -eq 'all' -or $Step -eq '2') {
                Deploy-KubernetesResources -Step1Outputs $step1Outputs
            }
            
            Write-Header "Deployment Complete!"
            Show-Status
        }
        
        'destroy' {
            Destroy-Infrastructure -TargetStep $Step
        }
        
        'status' {
            Show-Status
        }
        
        'images-only' {
            Test-Prerequisites
            $step1Outputs = Get-Step1Outputs
            if (-not $step1Outputs.acr_login_server) {
                Write-Error "Step 1 must be deployed first to get ACR information."
                exit 1
            }
            Build-AndPushImages -AcrServer $step1Outputs.acr_login_server -AcrName $step1Outputs.acr_name
        }
        
        'port-forward' {
            # Ensure kubectl is connected to the right cluster
            Write-Step "Connecting to AKS cluster..."
            $step1Outputs = Get-Step1Outputs
            if ($step1Outputs.aks_cluster_name -and $step1Outputs.resource_group_name) {
                az aks get-credentials --resource-group $step1Outputs.resource_group_name --name $step1Outputs.aks_cluster_name --overwrite-existing 2>$null
            }
            Start-PortForward
        }
    }
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
