<#
.SYNOPSIS
    Sets up locally-trusted TLS certificates for the API Gateway using mkcert or openssl.

.DESCRIPTION
    1. Checks for mkcert or openssl
    2. Generates cert + key for localhost
    3. Creates a Kubernetes TLS secret (api-gateway-tls) in the default namespace

.PARAMETER UseOpenssl
    Force using openssl instead of mkcert. Browsers will show a security warning.

.PARAMETER SkipCAInstall
    Skip mkcert CA installation (avoids the UAC/hang issue).
    Certs still work but browsers will show a warning until you trust the CA manually.

.EXAMPLE
    .\scripts\setup-local-tls.ps1
    .\scripts\setup-local-tls.ps1 -UseOpenssl
    .\scripts\setup-local-tls.ps1 -SkipCAInstall
#>

param(
    [string]$Namespace = "default",
    [string]$SecretName = "api-gateway-tls",
    [string]$CertDir = "$PSScriptRoot\..\certs",
    [switch]$UseOpenssl,
    [switch]$SkipCAInstall
)

$ErrorActionPreference = "Stop"

# ── Helpers ──────────────────────────────────────────────────
function Write-Step  { param($msg) Write-Host "🔧 $msg" -ForegroundColor Cyan }
function Write-Ok    { param($msg) Write-Host "✅ $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "⚠️  $msg" -ForegroundColor Yellow }

# ── 1. Check tool availability ──────────────────────────────
$certFile = Join-Path $CertDir "localhost.pem"
$keyFile  = Join-Path $CertDir "localhost-key.pem"

if (-not (Test-Path $CertDir)) {
    New-Item -ItemType Directory -Path $CertDir -Force | Out-Null
}

if ($UseOpenssl) {
    # ── OpenSSL path ────────────────────────────────────────
    Write-Step "Using openssl to generate self-signed certificate..."
    $openssl = Get-Command openssl -ErrorAction SilentlyContinue
    if (-not $openssl) {
        Write-Error "❌ openssl not found in PATH. Install Git for Windows (includes openssl) or add openssl to PATH."
        exit 1
    }
    Write-Ok "openssl found at $($openssl.Source)"

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
    Write-Ok "Certificates generated (self-signed, browsers will show a warning)"
} else {
    # ── mkcert path ─────────────────────────────────────────
    Write-Step "Checking mkcert installation..."
    $mkcert = Get-Command mkcert -ErrorAction SilentlyContinue
    if (-not $mkcert) {
        Write-Warn "mkcert not found. Attempting install via winget..."
        winget install --id FiloSottile.mkcert --accept-package-agreements --accept-source-agreements
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        $mkcert = Get-Command mkcert -ErrorAction SilentlyContinue
        if (-not $mkcert) {
            Write-Error "❌ mkcert installation failed. Install manually: https://github.com/FiloSottile/mkcert"
            exit 1
        }
    }
    Write-Ok "mkcert found at $($mkcert.Source)"

    if (-not $SkipCAInstall) {
        Write-Step "Installing local CA (limit to system store only)..."
        $env:TRUST_STORES = "system"
        mkcert -install
        Write-Ok "Local CA installed"
    } else {
        Write-Warn "Skipping CA install (-SkipCAInstall). Browsers may show a warning."
    }

    Write-Step "Generating certificates for localhost..."
    Push-Location $CertDir
    try {
        mkcert -cert-file localhost.pem -key-file localhost-key.pem localhost 127.0.0.1 ::1
    } finally {
        Pop-Location
    }

    if (-not (Test-Path $certFile) -or -not (Test-Path $keyFile)) {
        Write-Error "❌ Certificate generation failed"
        exit 1
    }
    Write-Ok "Certificates generated: $certFile, $keyFile"
}

# ── 4. Create Kubernetes TLS secret ────────────────────────
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
if ($UseOpenssl -or $SkipCAInstall) {
    Write-Warn "Browsers will show a security warning — click 'Advanced' → 'Proceed' to continue."
}
Write-Host "  To regenerate certs, just run this script again." -ForegroundColor Gray
