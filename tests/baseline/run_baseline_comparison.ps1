#!/usr/bin/env pwsh
param(
    [int]$Rate = 10000,
    [int]$Duration = 300,
    [int]$CooldownSeconds = 90,
    [string]$Namespace = "default",
    [int]$Pods = 2,
    [int]$Threads = 10,
    [switch]$Local,
    [string]$BackendUrl = "http://localhost:8000",
    [string]$PrometheusUrl = "http://localhost:9091",
    [string]$BrokerHost = "localhost",
    [string]$Username = "admin",
    [string]$Password = "admin",
    [string]$OutputFile = "tests/baseline/baseline_comparison_results.csv"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path (Split-Path $ScriptRoot)
$PerfTestScript = Join-Path $RepoRoot "tests" "perf_test_mqtt.py"
$JobManifest = Join-Path $RepoRoot "tests" "perf" "perf-test-job.yaml"
$script:AuthToken = $null
$JobName = "baseline-perf-test"
$ConfigMapName = "baseline-perf-script"
$RatePerPod = [math]::Ceiling($Rate / $Pods)

$OutputDir = Split-Path $OutputFile
if ($OutputDir -and !(Test-Path $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null }

function Get-AuthToken {
    Write-Host "`u{1F511} Authenticating with backend..." -ForegroundColor Yellow
    try {
        $body = @{ username = $Username; password = $Password } | ConvertTo-Json
        $response = Invoke-RestMethod -Uri "$BackendUrl/api/auth/login" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 10
        $script:AuthToken = $response.data.access_token
        if (-not $script:AuthToken) { throw "No access_token" }
        Write-Host "`u{2705} Authenticated as $Username" -ForegroundColor Green
    } catch { Write-Warning "Auth failed: $_"; throw "Cannot proceed without authentication" }
}

function Get-AuthHeaders {
    if (-not $script:AuthToken) { Get-AuthToken }
    return @{ "Authorization" = "Bearer $($script:AuthToken)"; "Content-Type" = "application/json" }
}

function Test-Connectivity {
    Write-Host "`n`u{1F50D} Pre-flight connectivity checks..." -ForegroundColor Cyan
    $allOk = $true
    try {
        $r = curl.exe -s -m 5 "$BackendUrl/api/health" 2>&1 | ConvertFrom-Json
        if ($r) { Write-Host "   `u{2705} Backend ($BackendUrl)" -ForegroundColor Green } else { throw "empty" }
    } catch { Write-Host "   `u{274C} Backend ($BackendUrl)" -ForegroundColor Red; $allOk = $false }
    try {
        $promCheck = curl.exe -s -m 5 "$PrometheusUrl/-/healthy" 2>&1
        if ($promCheck -match "Prometheus Server is Healthy") { Write-Host "   `u{2705} Prometheus ($PrometheusUrl)" -ForegroundColor Green } else { throw "unexpected" }
    } catch { Write-Host "   `u{274C} Prometheus ($PrometheusUrl)" -ForegroundColor Red; $allOk = $false }
    if ($Local) {
        try { $tcp = New-Object System.Net.Sockets.TcpClient; $tcp.Connect($BrokerHost, 1883); $tcp.Close(); Write-Host "   `u{2705} MQTT ($BrokerHost`:1883)" -ForegroundColor Green } catch { Write-Host "   `u{274C} MQTT ($BrokerHost`:1883)" -ForegroundColor Red; $allOk = $false }
    } else {
        $mqttPod = kubectl get pods -n $Namespace -l app=mosquitto --field-selector=status.phase=Running -o name 2>$null
        if ($mqttPod) { Write-Host "   `u{2705} MQTT (in-cluster)" -ForegroundColor Green } else { Write-Host "   `u{274C} MQTT not running in ns $Namespace" -ForegroundColor Red; $allOk = $false }
    }
    if (-not $allOk) {
        if (-not $Local) { Write-Host "   Port-forwards needed: backend-external 8000, prometheus 9091" -ForegroundColor DarkYellow }
        throw "Connectivity pre-check failed"
    }
    Write-Host ""
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
    } catch { Write-Warning "Prometheus query failed: $_"; return $null }
}

function Reset-Pipeline {
    Write-Host "`u{1F504} Restarting enrichment pipeline..." -ForegroundColor Yellow
    try { $headers = Get-AuthHeaders; Invoke-RestMethod -Uri "$BackendUrl/api/config/enrichment/restart" -Method Post -Headers $headers -TimeoutSec 30 | Out-Null; Write-Host "`u{2705} Pipeline restarted" -ForegroundColor Green } catch { Write-Warning "Pipeline restart failed: $_" }
}

function Ensure-WildcardDevice {
    Write-Host "`u{1F4CB} Ensuring wildcard device..." -ForegroundColor Yellow
    try {
        $headers = Get-AuthHeaders
        $devices = Invoke-RestMethod -Uri "$BackendUrl/api/devices?page_size=100" -Method Get -Headers $headers -TimeoutSec 10
        foreach ($d in $devices.data) { if ($null -eq $d.ingestion_id) { Write-Host "`u{2705} Wildcard already registered" -ForegroundColor Green; return } }
        $body = @{ name = "perf-test-wildcard"; description = "Wildcard for baseline testing"; enabled = $true; sensitivity = "internal"; created_by = $Username } | ConvertTo-Json
        Invoke-RestMethod -Uri "$BackendUrl/api/devices" -Method Post -Body $body -Headers $headers -TimeoutSec 10 | Out-Null
        Write-Host "`u{2705} Wildcard device registered" -ForegroundColor Green
    } catch { Write-Warning "Wildcard registration failed: $_" }
}

function Set-BypassMode {
    param([bool]$Enabled)
    $value = if ($Enabled) { "true" } else { "false" }
    Write-Host "`u{1F527} Setting SPARK_BYPASS_ENRICHMENT=$value..." -ForegroundColor Yellow
    try {
        kubectl set env statefulset/backend SPARK_BYPASS_ENRICHMENT=$value -n $Namespace 2>&1 | Out-Null
        kubectl rollout status statefulset/backend -n $Namespace --timeout=120s 2>&1 | Out-Null
        Write-Host "`u{2705} Backend restarted" -ForegroundColor Green
        Write-Host "`u{23F3} Waiting for backend..." -ForegroundColor Yellow
        for ($i = 1; $i -le 60; $i++) {
            try { $check = curl.exe -s -m 3 "$BackendUrl/api/health" 2>&1; if ($check -and ($check | ConvertFrom-Json -ErrorAction SilentlyContinue)) { Write-Host "`u{2705} Backend reachable (attempt $i)" -ForegroundColor Green; return } } catch { }
            if ($i % 10 -eq 0) { Write-Host "   Still waiting... ($i/60)" -ForegroundColor DarkYellow }
            Start-Sleep -Seconds 5
        }
        Read-Host "Press Enter once backend is accessible"
    } catch { Write-Warning "kubectl set env failed: $_"; Read-Host "Press Enter once backend restarted" }
}

function Start-LocalPublisher { param([int]$TestRate); Write-Host "`u{1F4E8} Local publisher at $TestRate msg/s..." -ForegroundColor Yellow; return Start-Process -FilePath "python" -ArgumentList "$PerfTestScript --rate $TestRate --duration $Duration --broker $BrokerHost" -PassThru -NoNewWindow }
function Wait-LocalPublisher { param($Process); $Process | Wait-Process | Out-Null }

function Start-ClusterPublisher {
    param([int]$TestRate)
    $ratePerPod = [math]::Ceiling($TestRate / $Pods)
    Write-Host "`u{1F4E8} Deploying $Pods pods at $ratePerPod msg/s each (~$TestRate total)..." -ForegroundColor Yellow
    kubectl delete job $JobName -n $Namespace 2>$null | Out-Null; kubectl delete pods -n $Namespace -l app=$JobName 2>$null | Out-Null; kubectl delete configmap $ConfigMapName -n $Namespace 2>$null | Out-Null; Start-Sleep 3
    kubectl create configmap $ConfigMapName -n $Namespace --from-file=perf_test_mqtt.py=$PerfTestScript 2>&1 | Out-Null
    $manifest = Get-Content $JobManifest -Raw
    $manifest = $manifest -replace 'name: mqtt-perf-test', "name: $JobName" -replace 'app: mqtt-perf-test', "app: $JobName" -replace 'parallelism: 2', "parallelism: $Pods" -replace 'completions: 2', "completions: $Pods" -replace '"1500"', "`"$ratePerPod`"" -replace '"300"', "`"$Duration`"" -replace '"10"', "`"$Threads`"" -replace 'perf-test-script', $ConfigMapName
    if ($Namespace -eq "default") { $manifest = $manifest -replace 'soamregistry\.azurecr\.io/simulator:latest', 'localhost:5000/soam/simulator:latest' }
    $manifest | kubectl apply -n $Namespace -f - 2>&1 | Out-Null
    $elapsed = 0; while ($elapsed -lt 120) { $running = kubectl get pods -n $Namespace -l app=$JobName --field-selector=status.phase=Running -o name 2>$null; if ($running -and ($running | Measure-Object).Count -ge $Pods) { break }; Start-Sleep 3; $elapsed += 3 }
    Write-Host "`u{2705} Publisher pods running" -ForegroundColor Green
}

function Wait-ClusterPublisher {
    Write-Host "`u{23F3} Waiting for publisher job (~${Duration}s)..." -ForegroundColor Yellow
    while ($true) {
        $complete = kubectl get job $JobName -n $Namespace -o jsonpath="{.status.conditions[?(@.type=='Complete')].status}" 2>$null; if ($complete -eq "True") { break }
        $failed = kubectl get job $JobName -n $Namespace -o jsonpath="{.status.conditions[?(@.type=='Failed')].status}" 2>$null; if ($failed -eq "True") { Write-Warning "Job failed!"; break }
        $podName = kubectl get pods -n $Namespace -l app=$JobName -o jsonpath="{.items[0].metadata.name}" 2>$null
        if ($podName) { $tail = kubectl logs $podName -n $Namespace --tail=1 2>$null; if ($tail) { Write-Host "  [$($podName.Substring([Math]::Max(0,$podName.Length-8)))] $tail" -ForegroundColor DarkGray } }
        Start-Sleep 15
    }
    Write-Host "`u{2705} Publisher job completed" -ForegroundColor Green
}

function Cleanup-ClusterPublisher { kubectl delete job $JobName -n $Namespace 2>$null | Out-Null; kubectl delete configmap $ConfigMapName -n $Namespace 2>$null | Out-Null }

function Run-Test {
    param([string]$ModeName)
    Write-Host "`n`u{1F680} Running: $ModeName at $Rate msg/s for ${Duration}s" -ForegroundColor Cyan
    Reset-Pipeline | Out-Null; Start-Sleep 15
    $preCount = Query-Prometheus 'enrichment_records_processed_total'
    if ($Local) { $proc = Start-LocalPublisher -TestRate $Rate; Wait-LocalPublisher -Process $proc } else { Start-ClusterPublisher -TestRate $Rate; Wait-ClusterPublisher; Cleanup-ClusterPublisher }
    Write-Host "`u{23F3} Waiting ${CooldownSeconds}s for drain..." -ForegroundColor Yellow; Start-Sleep $CooldownSeconds
    $throughput = Query-Prometheus 'rate(enrichment_records_processed_total[5m])'
    $p95 = Query-Prometheus 'histogram_quantile(0.95, rate(spark_batch_processing_latency_seconds_bucket[5m]))'
    $avg = Query-Prometheus 'rate(spark_batch_processing_latency_seconds_sum[5m]) / rate(spark_batch_processing_latency_seconds_count[5m])'
    $postCount = Query-Prometheus 'enrichment_records_processed_total'
    $totalProcessed = if ($preCount -ne $null -and $postCount -ne $null) { [math]::Round($postCount - $preCount, 0) } else { "N/A" }
    $result = @{ Mode = $ModeName; TargetRate = $Rate; Throughput = if ($throughput) { [math]::Round($throughput, 1) } else { "N/A" }; LatencyP95 = if ($p95) { [math]::Round($p95, 3) } else { "N/A" }; LatencyAvg = if ($avg) { [math]::Round($avg, 3) } else { "N/A" }; TotalProcessed = $totalProcessed; Timestamp = Get-Date -Format "yyyy-MM-ddTHH:mm:ss" }
    return $result
}

# --- Main ---
$mode = if ($Local) { "LOCAL" } else { "CLUSTER ($Pods pods in '$Namespace')" }
Write-Host "`n`u{1F9EA} SOAM Baseline Comparison" -ForegroundColor Cyan
Write-Host "=" * 60
Write-Host "   Mode:         $mode"
Write-Host "   Total Rate:   $Rate msg/s"
Write-Host "   Duration/run: ${Duration}s"
Write-Host "   Cooldown:     ${CooldownSeconds}s"
Write-Host "   Namespace:    $Namespace"
Write-Host "   Output:       $OutputFile"
Write-Host "=" * 60

Test-Connectivity; Get-AuthToken; Ensure-WildcardDevice

Write-Host "`n`u{1F4CB} Run 1: Dynamic schema inference" -ForegroundColor Cyan
$dynamicResult = Run-Test -ModeName "Dynamic schema inference"

Set-BypassMode -Enabled $true; Get-AuthToken; Ensure-WildcardDevice
$fixedResult = Run-Test -ModeName "Fixed schema (baseline)"

Write-Host "`n`u{1F527} Restoring dynamic schema mode..." -ForegroundColor Yellow
Set-BypassMode -Enabled $false

Write-Host "`n"; Write-Host "=" * 70; Write-Host "`u{1F4CA} BASELINE COMPARISON RESULTS" -ForegroundColor Cyan; Write-Host "=" * 70
Write-Host ""; Write-Host ("{0,-30} {1,-20} {2,-20}" -f "Metric", "Dynamic Schema", "Fixed Schema"); Write-Host "-" * 70
Write-Host ("{0,-30} {1,-20} {2,-20}" -f "Throughput (records/s)", $dynamicResult.Throughput, $fixedResult.Throughput)
Write-Host ("{0,-30} {1,-20} {2,-20}" -f "Batch Latency p95 (s)", $dynamicResult.LatencyP95, $fixedResult.LatencyP95)
Write-Host ("{0,-30} {1,-20} {2,-20}" -f "Batch Latency avg (s)", $dynamicResult.LatencyAvg, $fixedResult.LatencyAvg)
Write-Host ("{0,-30} {1,-20} {2,-20}" -f "Total Records Processed", $dynamicResult.TotalProcessed, $fixedResult.TotalProcessed)
Write-Host "-" * 70; Write-Host ""

if ($dynamicResult.Throughput -ne "N/A" -and $fixedResult.Throughput -ne "N/A" -and $fixedResult.Throughput -gt 0) {
    $overhead = [math]::Round((1 - $dynamicResult.Throughput / $fixedResult.Throughput) * 100, 1)
    if ($overhead -le 5) { Write-Host "`u{2705} Dynamic schema overhead: ${overhead}% - NEGLIGIBLE" -ForegroundColor Green } else { Write-Host "`u{26A0}`u{FE0F} Dynamic schema overhead: ${overhead}%" -ForegroundColor Yellow }
}

$csv = @("mode,target_rate,throughput_records_per_sec,batch_latency_p95_s,batch_latency_avg_s,total_processed,timestamp"; "$($dynamicResult.Mode),$($dynamicResult.TargetRate),$($dynamicResult.Throughput),$($dynamicResult.LatencyP95),$($dynamicResult.LatencyAvg),$($dynamicResult.TotalProcessed),$($dynamicResult.Timestamp)"; "$($fixedResult.Mode),$($fixedResult.TargetRate),$($fixedResult.Throughput),$($fixedResult.LatencyP95),$($fixedResult.LatencyAvg),$($fixedResult.TotalProcessed),$($fixedResult.Timestamp)")
$csv | Out-File -FilePath $OutputFile -Encoding UTF8
Write-Host "`n`u{2705} Results saved to $OutputFile" -ForegroundColor Green
