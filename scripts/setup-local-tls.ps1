<#
.SYNOPSIS
    Sets up self-signed TLS certificates for the API Gateway using openssl.

.DESCRIPTION
    1. Generates a self-signed cert + key for localhost via openssl
    2. Creates a Kubernetes TLS secret (api-gateway-tls) in the default namespace

.EXAMPLE
    .\scripts\setup-local-tls.ps1
#>

param(
    [string]$Namespace = "default",
    [string]$SecretName = "api-gateway-tls",
    [string]$CertDir = "$PSScriptRoot\..\certs"
)

$ErrorActionPreference = "Stop"

# ── Helpers ──────────────────────────────────────────────────
function Write-Step  { param($msg) Write-Host "🔧 $msg" -ForegroundColor Cyan }
function Write-Ok    { param($msg) Write-Host "✅ $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "⚠️  $msg" -ForegroundColor Yellow }

# ── 1. Check openssl availability ───────────────────────────
$certFile = Join-Path $CertDir "localhost.pem"
$keyFile  = Join-Path $CertDir "localhost-key.pem"

if (-not (Test-Path $CertDir)) {
    New-Item -ItemType Directory -Path $CertDir -Force | Out-Null
}

Write-Step "Checking openssl installation..."
$openssl = Get-Command openssl -ErrorAction SilentlyContinue
if (-not $openssl) {
    Write-Error "❌ openssl not found in PATH. Install Git for Windows (includes openssl) or add openssl to PATH."
    exit 1
}
Write-Ok "openssl found at $($openssl.Source)"

# ── 2. Generate self-signed certificate ─────────────────────
Write-Step "Generating self-signed certificate for localhost..."
openssl req -x509 -newkey rsa:2048 -nodes `
    -keyout $keyFile `
    -out $certFile `
    -days 365 `
    -subj "/CN=localhost" `
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:::1"

if (-not (Test-Path $certFile) -or -not (Test-Path $keyFile)) {
    Write-Error "❌ Certificate generation failed"
    exit 1
}
Write-Ok "Certificates generated: $certFile, $keyFile"

# ── 3. Create Kubernetes TLS secret ─────────────────────────
Write-Step "Creating Kubernetes TLS secret '$SecretName' in namespace '$Namespace'..."

# Delete existing secret if present
kubectl delete secret $SecretName -n $Namespace 2>$null

kubectl create secret tls $SecretName `
    --cert=$certFile `
    --key=$keyFile `
    -n $Namespace

Write-Ok "TLS secret '$SecretName' created"

# ── Done ────────────────────────────────────────────────────
Write-Host ""
Write-Ok "Local TLS setup complete!"
Write-Host ""
Write-Host "  Frontend:    https://localhost:3000" -ForegroundColor White
Write-Host "  API Gateway: https://localhost:4000" -ForegroundColor White
Write-Host "  Certs:       $CertDir" -ForegroundColor Gray
Write-Host ""
Write-Warn "Browsers will show a security warning — click 'Advanced' → 'Proceed' to continue."
Write-Host "  To regenerate certs, just run this script again." -ForegroundColor Gray
