#!/usr/bin/env pwsh
# Runs a single throughput test (with or without bypass) and outputs results as JSON.
#
# Usage:
#   .\tests\baseline\run_single_test.ps1 -Namespace soam -Rate 10000 -Duration 900 -Pods 4 -OutputFile dynamic.json
#   .\tests\baseline\run_single_test.ps1 -Namespace soam -Rate 10000 -Duration 900 -Pods 4 -Bypass -OutputFile bypass.json
#   .\tests\baseline\compare_results.ps1 -DynamicFile dynamic.json -BypassFile bypass.json
param(
    [int]$Rate = 10000,
    [int]$Duration = 900,
    [int]$CooldownSeconds = 90,
    [string]$Namespace = "default",
    [int]$Pods = 2,
    [int]$Threads = 10,
    [switch]$Local,
    [switch]$Bypass,
    [string]$BackendUrl = "http://localhost:8000",
    [string]$PrometheusUrl = "http://localhost:9091",
    [string]$BrokerHost = "localhost",
    [string]$Username = "admin",
    [string]$Password = "admin",
    [string]$MetricsWindow = "3m",
    [string]$OutputFile = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path (Split-Path $ScriptRoot)
$PerfTestScript = Join-Path $RepoRoot "tests" "perf_test_mqtt.py"
$JobManifest = Join-Path $RepoRoot "tests" "perf" "perf-test-job.yaml"
$script:AuthToken = $null
$JobName = "single-perf-test"
$ConfigMapName = "single-perf-script"
$script:PortForwardPids = @()
$ModeName = if ($Bypass) { "Fixed schema (bypass)" } else { "Dynamic schema inference" }
# Cleanup port-forwards on Ctrl+C
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    Get-Process -Name kubectl* -ErrorAction SilentlyContinue | ForEach-Object {
        try { $cmd = (Get-CimInstance Win32_Process -Filter \"ProcessId = $($_.Id)\" -ErrorAction SilentlyContinue).CommandLine; if ($cmd -match 'port-forward') { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue } } catch { }
    }
}
try { [Console]::TreatControlCAsInput = $false } catch { }
$null = Register-ObjectEvent -InputObject ([Console]) -EventName CancelKeyPress -Action {
    Write-Host \"`n`u{1F6D1} Ctrl+C — cleaning up port-forwards...\" -ForegroundColor Red
    Get-Process -Name kubectl* -ErrorAction SilentlyContinue | ForEach-Object {
        try { $cmd = (Get-CimInstance Win32_Process -Filter \"ProcessId = $($_.Id)\" -ErrorAction SilentlyContinue).CommandLine; if ($cmd -match 'port-forward') { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue } } catch { }
    }
}
# Default output file name based on mode
if (-not $OutputFile) {
    $tag = if ($Bypass) { "bypass" } else { "dynamic" }
    $OutputFile = "tests/baseline/result_${tag}_${Rate}r_${Duration}s.json"
}

$OutputDir = Split-Path $OutputFile
if ($OutputDir -and !(Test-Path $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null }

# --- Helpers (same as run_baseline_comparison.ps1) ---

function Stop-AllPortForwards {
    Get-Process -Name kubectl* -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
            if ($cmdLine -match 'port-forward') { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
        } catch { }
    }
    $script:PortForwardPids = @()
}

function Start-PortForwards {
    if ($Local) { return }
    Write-Host "`u{1F517} Starting port-forwards for '$Namespace'..." -ForegroundColor Yellow
    Stop-AllPortForwards; Start-Sleep 2
    kubectl wait --for=condition=ready pod -l app=backend -n $Namespace --timeout=120s 2>&1 | Out-Null
    $pf1 = Start-Process -FilePath kubectl -ArgumentList "port-forward svc/backend-external 8000:8000 -n $Namespace" -PassThru -WindowStyle Hidden
    $pf2 = Start-Process -FilePath kubectl -ArgumentList "port-forward svc/prometheus 9091:9090 -n $Namespace" -PassThru -WindowStyle Hidden
    $script:PortForwardPids = @($pf1.Id, $pf2.Id)
    for ($i = 1; $i -le 20; $i++) {
        Start-Sleep 2
        $alive = try { Get-Process -Id $pf1.Id -ErrorAction Stop; $true } catch { $false }
        if (-not $alive) { $pf1 = Start-Process -FilePath kubectl -ArgumentList "port-forward svc/backend-external 8000:8000 -n $Namespace" -PassThru -WindowStyle Hidden; $script:PortForwardPids = @($pf1.Id, $pf2.Id); continue }
        try { $c = curl.exe -s -m 2 "$BackendUrl/api/health" 2>&1; if ($c -and ($c | ConvertFrom-Json -ErrorAction SilentlyContinue)) { Write-Host "   `u{2705} Port-forwards ready" -ForegroundColor Green; return } } catch { }
    }
    Write-Warning "Port-forwards may not be ready"
}

function Stop-PortForwards { Stop-AllPortForwards }

function Get-AuthToken {
    Write-Host "`u{1F511} Authenticating..." -ForegroundColor Yellow
    $body = @{ username = $Username; password = $Password } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "$BackendUrl/api/auth/login" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 10
    $script:AuthToken = $response.data.access_token
    if (-not $script:AuthToken) { throw "No access_token" }
    Write-Host "`u{2705} Authenticated" -ForegroundColor Green
}

function Get-AuthHeaders {
    if (-not $script:AuthToken) { Get-AuthToken }
    return @{ "Authorization" = "Bearer $($script:AuthToken)"; "Content-Type" = "application/json" }
}

function Test-Connectivity {
    Write-Host "`u{1F50D} Connectivity checks..." -ForegroundColor Cyan
    $allOk = $true
    try { $r = curl.exe -s -m 5 "$BackendUrl/api/health" 2>&1 | ConvertFrom-Json; if ($r) { Write-Host "   `u{2705} Backend" -ForegroundColor Green } else { throw "e" } } catch { Write-Host "   `u{274C} Backend ($BackendUrl)" -ForegroundColor Red; $allOk = $false }
    try { $p = curl.exe -s -m 5 "$PrometheusUrl/-/healthy" 2>&1; if ($p -match "Healthy") { Write-Host "   `u{2705} Prometheus" -ForegroundColor Green } else { throw "e" } } catch { Write-Host "   `u{274C} Prometheus ($PrometheusUrl)" -ForegroundColor Red; $allOk = $false }
    if ($Local) { try { $t = New-Object System.Net.Sockets.TcpClient; $t.Connect($BrokerHost, 1883); $t.Close(); Write-Host "   `u{2705} MQTT" -ForegroundColor Green } catch { Write-Host "   `u{274C} MQTT" -ForegroundColor Red; $allOk = $false } }
    else { $m = kubectl get pods -n $Namespace -l app=mosquitto --field-selector=status.phase=Running -o name 2>$null; if ($m) { Write-Host "   `u{2705} MQTT (in-cluster)" -ForegroundColor Green } else { Write-Host "   `u{274C} MQTT" -ForegroundColor Red; $allOk = $false } }
    if (-not $allOk) { throw "Connectivity failed" }
}

function Query-Prometheus {
    param([string]$Query)
    try {
        $encoded = [System.Uri]::EscapeDataString($Query)
        $raw = curl.exe -s "$PrometheusUrl/api/v1/query?query=$encoded" 2>&1
        $response = $raw -join '' | ConvertFrom-Json
        if ($response.status -eq "success" -and $response.data.result.Count -gt 0) {
            $total = 0.0
            foreach ($r in $response.data.result) { $val = [string]$r.value[1]; if ($val -ne "NaN" -and $val -ne "") { $total += [double]$val } }
            return $total
        }
        return $null
    } catch { return $null }
}

function Ensure-WildcardDevice {
    try {
        $h = Get-AuthHeaders
        $devices = Invoke-RestMethod -Uri "$BackendUrl/api/devices?page_size=100" -Method Get -Headers $h -TimeoutSec 10
        foreach ($d in $devices.data) { if ($null -eq $d.ingestion_id) { Write-Host "`u{2705} Wildcard exists" -ForegroundColor Green; return } }
        $body = @{ name = "perf-test-wildcard"; description = "Wildcard for testing"; enabled = $true; sensitivity = "internal"; created_by = $Username } | ConvertTo-Json
        Invoke-RestMethod -Uri "$BackendUrl/api/devices" -Method Post -Body $body -Headers $h -TimeoutSec 10 | Out-Null
        Write-Host "`u{2705} Wildcard registered" -ForegroundColor Green
    } catch { Write-Warning "Wildcard failed: $_" }
}

function Reset-Pipeline {
    try { $h = Get-AuthHeaders; Invoke-RestMethod -Uri "$BackendUrl/api/config/enrichment/restart" -Method Post -Headers $h -TimeoutSec 30 | Out-Null } catch { Write-Warning "Restart failed: $_" }
}

function Start-LocalPublisher { param([int]$R); return Start-Process -FilePath "python" -ArgumentList "$PerfTestScript --rate $R --duration $Duration --broker $BrokerHost" -PassThru -NoNewWindow }

function Start-ClusterPublisher {
    param([int]$R)
    $rpp = [math]::Ceiling($R / $Pods)
    Write-Host "`u{1F4E8} Deploying $Pods pods at $rpp msg/s each (~$R total)..." -ForegroundColor Yellow
    kubectl delete job $JobName -n $Namespace 2>$null | Out-Null; kubectl delete pods -n $Namespace -l app=$JobName 2>$null | Out-Null; kubectl delete configmap $ConfigMapName -n $Namespace 2>$null | Out-Null; Start-Sleep 3
    kubectl create configmap $ConfigMapName -n $Namespace --from-file=perf_test_mqtt.py=$PerfTestScript 2>&1 | Out-Null
    $manifest = Get-Content $JobManifest -Raw
    $manifest = $manifest -replace 'name: mqtt-perf-test', "name: $JobName" -replace 'app: mqtt-perf-test', "app: $JobName" -replace 'parallelism: 2', "parallelism: $Pods" -replace 'completions: 2', "completions: $Pods" -replace '"1500"', "`"$rpp`"" -replace '"300"', "`"$Duration`"" -replace '"10"', "`"$Threads`"" -replace 'perf-test-script', $ConfigMapName
    if ($Namespace -eq "default") { $manifest = $manifest -replace 'soamregistry\.azurecr\.io/simulator:latest', 'localhost:5000/soam/simulator:latest' }
    $manifest | kubectl apply -n $Namespace -f - 2>&1 | Out-Null
    $elapsed = 0; while ($elapsed -lt 120) { $running = kubectl get pods -n $Namespace -l app=$JobName --field-selector=status.phase=Running -o name 2>$null; if ($running -and ($running | Measure-Object).Count -ge $Pods) { break }; Start-Sleep 3; $elapsed += 3 }
    Write-Host "`u{2705} Pods running" -ForegroundColor Green
}

function Wait-ClusterPublisher {
    Write-Host "`u{23F3} Waiting for job (~${Duration}s)..." -ForegroundColor Yellow
    while ($true) {
        $c = kubectl get job $JobName -n $Namespace -o jsonpath="{.status.conditions[?(@.type=='Complete')].status}" 2>$null; if ($c -eq "True") { break }
        $f = kubectl get job $JobName -n $Namespace -o jsonpath="{.status.conditions[?(@.type=='Failed')].status}" 2>$null; if ($f -eq "True") { Write-Warning "Job failed!"; break }
        $pod = kubectl get pods -n $Namespace -l app=$JobName -o jsonpath="{.items[0].metadata.name}" 2>$null
        if ($pod) { $tail = kubectl logs $pod -n $Namespace --tail=1 2>$null; if ($tail) { Write-Host "  [$($pod.Substring([Math]::Max(0,$pod.Length-8)))] $tail" -ForegroundColor DarkGray } }
        Start-Sleep 15
    }
    Write-Host "`u{2705} Job completed" -ForegroundColor Green
}

function Cleanup-ClusterPublisher { kubectl delete job $JobName -n $Namespace 2>$null | Out-Null; kubectl delete configmap $ConfigMapName -n $Namespace 2>$null | Out-Null }

# --- Main ---
$modeLabel = if ($Local) { "LOCAL" } else { "CLUSTER ($Pods pods in '$Namespace')" }
$bypassLabel = if ($Bypass) { "BYPASS (fixed schema)" } else { "DYNAMIC (schema inference)" }

Write-Host "`n`u{1F9EA} SOAM Single Test Run" -ForegroundColor Cyan
Write-Host "=" * 60
Write-Host "   Mode:         $modeLabel"
Write-Host "   Pipeline:     $bypassLabel"
Write-Host "   Rate:         $Rate msg/s"
Write-Host "   Duration:     ${Duration}s"
Write-Host "   Cooldown:     ${CooldownSeconds}s"
Write-Host "   Output:       $OutputFile"
Write-Host "=" * 60

Start-PortForwards
Test-Connectivity
Get-AuthToken
Ensure-WildcardDevice

# Set bypass mode based on -Bypass flag
$bypassValue = if ($Bypass) { "true" } else { "false" }
Write-Host "`u{1F527} Setting SPARK_BYPASS_ENRICHMENT=$bypassValue..." -ForegroundColor Yellow
kubectl set env statefulset/backend SPARK_BYPASS_ENRICHMENT=$bypassValue -n $Namespace 2>&1 | Out-Null
kubectl rollout status statefulset/backend -n $Namespace --timeout=120s 2>&1 | Out-Null
Write-Host "`u{2705} Backend restarted with SPARK_BYPASS_ENRICHMENT=$bypassValue" -ForegroundColor Green
Stop-PortForwards
Start-PortForwards
Get-AuthToken
Ensure-WildcardDevice

# Restart pipeline
Write-Host "`u{1F504} Restarting pipeline..." -ForegroundColor Yellow
Reset-Pipeline | Out-Null
Start-Sleep 15

$preCount = Query-Prometheus 'enrichment_records_processed_total'

# Run publisher
if ($Local) {
    $proc = Start-LocalPublisher -R $Rate
    $proc | Wait-Process | Out-Null
} else {
    Start-ClusterPublisher -R $Rate
    Wait-ClusterPublisher
    Cleanup-ClusterPublisher
}

# Capture throughput immediately (before idle dilutes rate)
Write-Host "`u{1F4CA} Capturing throughput..." -ForegroundColor Yellow
$throughput = Query-Prometheus "rate(enrichment_records_processed_total[$MetricsWindow])"

# Drain
Write-Host "`u{23F3} Waiting ${CooldownSeconds}s for drain..." -ForegroundColor Yellow
Start-Sleep $CooldownSeconds

$postCount = Query-Prometheus 'enrichment_records_processed_total'
$totalProcessed = if ($preCount -ne $null -and $postCount -ne $null) { [math]::Round($postCount - $preCount, 0) } else { 0 }
$effectiveThroughput = if ($totalProcessed -gt 0 -and $Duration -gt 0) { [math]::Round($totalProcessed / $Duration, 1) } else { 0 }
$throughputVal = if ($throughput) { [math]::Round($throughput, 1) } else { 0 }

Stop-PortForwards

# Build result
$result = [ordered]@{
    mode                = $ModeName
    bypass              = [bool]$Bypass
    target_rate         = $Rate
    duration_seconds    = $Duration
    cooldown_seconds    = $CooldownSeconds
    pods                = $Pods
    namespace           = $Namespace
    throughput_rate     = $throughputVal
    effective_throughput = $effectiveThroughput
    total_processed     = $totalProcessed
    timestamp           = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
}

# Output
$json = $result | ConvertTo-Json -Depth 3
$json | Out-File -FilePath $OutputFile -Encoding UTF8

Write-Host "`n`u{1F4CA} Results:" -ForegroundColor Cyan
Write-Host $json
Write-Host "`n`u{2705} Saved to $OutputFile" -ForegroundColor Green
