<#
.SYNOPSIS
    Setup GitHub Actions secrets for SOAM CI/CD

.DESCRIPTION
    This script helps configure the necessary GitHub secrets for the CI/CD pipeline.
    It creates an Azure Service Principal and outputs the required secret value.

.PARAMETER GitHubRepo
    The GitHub repository in format 'owner/repo'

.PARAMETER ResourceGroup
    Azure resource group name (default: soam-rg)

.PARAMETER SubscriptionId
    Azure subscription ID (if not provided, uses current subscription)

.EXAMPLE
    .\setup-github-actions.ps1 -GitHubRepo "myorg/soam"
    .\setup-github-actions.ps1 -GitHubRepo "myorg/soam" -ResourceGroup "soam-rg"

.NOTES
    Prerequisites:
    - Azure CLI installed and logged in
    - GitHub CLI installed and authenticated (optional, for automatic secret creation)
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$GitHubRepo,

    [string]$ResourceGroup = "soam-rg",

    [string]$SubscriptionId = ""
)

$ErrorActionPreference = "Stop"

# Colors
function Write-Header { param($msg) Write-Host "`n========================================" -ForegroundColor Cyan; Write-Host $msg -ForegroundColor Cyan; Write-Host "========================================" -ForegroundColor Cyan }
function Write-Step { param($msg) Write-Host "`n>> $msg" -ForegroundColor Yellow }
function Write-Success { param($msg) Write-Host "✅ $msg" -ForegroundColor Green }
function Write-Info { param($msg) Write-Host "ℹ️  $msg" -ForegroundColor Blue }

Write-Header "SOAM GitHub Actions Setup"

# Check Azure CLI
Write-Step "Checking Azure CLI..."
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Azure CLI not found." -ForegroundColor Red
    Write-Host "Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli" -ForegroundColor Gray
    exit 1
}

# Check if logged in to Azure
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Info "Not logged in to Azure."
    $doLogin = Read-Host "Login to Azure now? (y/n)"
    if ($doLogin -eq "y") {
        Write-Step "Opening Azure login..."
        az login
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Azure login failed" -ForegroundColor Red
            exit 1
        }
        $account = az account show | ConvertFrom-Json
        Write-Success "Logged in to Azure"
    } else {
        Write-Host "❌ Azure login required. Run 'az login' first." -ForegroundColor Red
        exit 1
    }
}
Write-Info "Logged in as: $($account.user.name)"

# Get subscription ID
if (-not $SubscriptionId) {
    $SubscriptionId = $account.id
}
Write-Info "Subscription: $SubscriptionId"

# Check if resource group exists
Write-Step "Checking resource group..."
$rgExists = az group exists --name $ResourceGroup | ConvertFrom-Json
if (-not $rgExists) {
    Write-Info "Resource group '$ResourceGroup' does not exist."
    Write-Info "Run 'terraform apply' in terraform/01-azure-infrastructure first."
    
    $createRg = Read-Host "Create resource group now? (y/n)"
    if ($createRg -eq "y") {
        az group create --name $ResourceGroup --location "West Europe"
        Write-Success "Resource group created"
    } else {
        exit 1
    }
}

# Create Service Principal
Write-Step "Creating Azure Service Principal..."
$spName = "soam-github-actions-$([guid]::NewGuid().ToString().Substring(0,8))"

# Assign Contributor at SUBSCRIPTION level (required for creating resource groups, AKS, ACR)
$spCredentials = az ad sp create-for-rbac `
    --name $spName `
    --role contributor `
    --scopes "/subscriptions/$SubscriptionId" `
    --sdk-auth 2>$null

if (-not $spCredentials) {
    Write-Error "Failed to create service principal"
    exit 1
}

Write-Success "Service Principal created: $spName"

# Parse credentials
$creds = $spCredentials | ConvertFrom-Json

# Add User Access Administrator role (required for creating role assignments, e.g., AKS -> ACR pull)
Write-Step "Adding User Access Administrator role..."
az role assignment create `
    --assignee $creds.clientId `
    --role "User Access Administrator" `
    --scope "/subscriptions/$SubscriptionId" `
    --output none 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Success "User Access Administrator role assigned"
} else {
    Write-Host "⚠️  Could not assign User Access Administrator role automatically." -ForegroundColor Yellow
    Write-Info "You may need to assign it manually via Azure Portal:"
    Write-Info "  Subscription -> Access control (IAM) -> Add role assignment"
    Write-Info "  Role: User Access Administrator, Assignee: $spName"
}

Write-Host ""
Write-Header "GitHub Secret Configuration"

Write-Host ""
Write-Host "Add the following secret to your GitHub repository:" -ForegroundColor White
Write-Host "Repository: https://github.com/$GitHubRepo/settings/secrets/actions" -ForegroundColor Gray
Write-Host ""
Write-Host "Secret Name: " -NoNewline -ForegroundColor Yellow
Write-Host "AZURE_CREDENTIALS" -ForegroundColor White
Write-Host ""
Write-Host "Secret Value:" -ForegroundColor Yellow
Write-Host $spCredentials -ForegroundColor Gray
Write-Host ""

# Try to use GitHub CLI if available
$ghAvailable = Get-Command gh -ErrorAction SilentlyContinue
if ($ghAvailable) {
    # Check if authenticated with GitHub
    $ghStatus = gh auth status 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Info "GitHub CLI is installed but not authenticated."
        $doGhLogin = Read-Host "Login to GitHub now? (y/n)"
        if ($doGhLogin -eq "y") {
            Write-Step "Opening GitHub login..."
            gh auth login --scopes "repo"
            if ($LASTEXITCODE -ne 0) {
                Write-Host "❌ GitHub login failed" -ForegroundColor Red
                Write-Info "You can set the secret manually via the GitHub web UI."
            } else {
                Write-Success "Logged in to GitHub"
            }
        }
    }
    
    # Re-check auth status after potential login
    gh auth status 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Step "GitHub CLI authenticated. Attempting automatic secret creation..."
        
        $setSecret = Read-Host "Set AZURE_CREDENTIALS secret automatically? (y/n)"
        if ($setSecret -eq "y") {
            $result = $spCredentials | gh secret set AZURE_CREDENTIALS --repo $GitHubRepo 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Secret AZURE_CREDENTIALS set successfully!"
            } else {
                Write-Host "❌ Could not set secret automatically: $result" -ForegroundColor Red
                Write-Info "Please set it manually via the GitHub web UI."
            }
        }
    }
} else {
    Write-Info "GitHub CLI not installed. Set the secret manually via the GitHub web UI."
    Write-Info "Install GitHub CLI from: https://cli.github.com/"
}

# Summary
Write-Host ""
Write-Header "Setup Complete"
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor White
Write-Host "1. Add the AZURE_CREDENTIALS secret to GitHub (if not done automatically)" -ForegroundColor Gray
Write-Host "2. Push changes to trigger CI/CD pipeline" -ForegroundColor Gray
Write-Host "3. Monitor workflow runs at: https://github.com/$GitHubRepo/actions" -ForegroundColor Gray
Write-Host ""

# Save credentials locally (for reference)
$credFile = ".github-sp-credentials.json"
$spCredentials | Out-File -FilePath $credFile -Encoding utf8
Write-Info "Credentials saved to $credFile (add to .gitignore!)"

# Ensure it's in gitignore
$gitignorePath = ".gitignore"
if (Test-Path $gitignorePath) {
    $gitignoreContent = Get-Content $gitignorePath -Raw
    if ($gitignoreContent -notmatch [regex]::Escape($credFile)) {
        Add-Content -Path $gitignorePath -Value "`n# GitHub Actions credentials`n$credFile"
        Write-Info "Added $credFile to .gitignore"
    }
}

Write-Host ""
Write-Success "Setup complete!"
