#!/usr/bin/env pwsh
param(
    [string]$Rates = "1000,5000,10000,15000,20000",
    [int]$Duration = 120,
    [int]$CooldownSeconds = 60,
    [string]$Namespace = "default",
    [int]$Pods = 2,
    [int]$Threads = 10,
    [switch]$Local,
    [string]$BackendUrl = "http://localhost:8000",
    [string]$PrometheusUrl = "http://localhost:9091",
    [string]$BrokerHost = "localhost",
    [string]$Username = "admin",
    [string]$Password = "admin",
    [string]$OutputFile = "tests/baseline/load_curve_results.csv"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$RateList = $Rates -split "," | ForEach-Object { [int]$_.Trim() }
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path (Split-Path $ScriptRoot)
$PerfTestScript = Join-Path $RepoRoot "tests" "perf_test_mqtt.py"
$JobManifest = Join-Path $RepoRoot "tests" "perf" "perf-test-job.yaml"
$script:AuthToken = $null
$JobName = "loadcurve-perf-test"
$ConfigMapName = "loadcurve-perf-script"

$OutputDir = Split-Path $OutputFile
if ($OutputDir -and !(Test-Path $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null }

function Get-AuthToken {
    Write-Host "`u{1F511} Authenticating..." -ForegroundColor Yellow
    try {
        $body = @{ username = $Username; password = $Password } | ConvertTo-Json
        $response = Invoke-RestMethod -Uri "$BackendUrl/api/auth/login" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 10
        $script:AuthToken = $response.data.access_token
        if (-not $script:AuthToken) { throw "No token" }
        Write-Host "`u{2705} Authenticated" -ForegroundColor Green
    } catch { Write-Warning "Auth failed: $_"; throw "Cannot proceed" }
}

function Get-AuthHeaders {
    if (-not $script:AuthToken) { Get-AuthToken }
    return @{ "Authorization" = "Bearer $($script:AuthToken)"; "Content-Type" = "application/json" }
}

function Test-Connectivity {
    Write-Host "`n`u{1F50D} Pre-flight checks..." -ForegroundColor Cyan
    $allOk = $true
    try { $r = curl.exe -s -m 5 "$BackendUrl/api/health" 2>&1 | ConvertFrom-Json; if ($r) { Write-Host "   `u{2705} Backend" -ForegroundColor Green } else { throw "empty" } } catch { Write-Host "   `u{274C} Backend ($BackendUrl)" -ForegroundColor Red; $allOk = $false }
    try { $p = curl.exe -s -m 5 "$PrometheusUrl/-/healthy" 2>&1; if ($p -match "Healthy") { Write-Host "   `u{2705} Prometheus" -ForegroundColor Green } else { throw "bad" } } catch { Write-Host "   `u{274C} Prometheus ($PrometheusUrl)" -ForegroundColor Red; $allOk = $false }
    if ($Local) { try { $tcp = New-Object System.Net.Sockets.TcpClient; $tcp.Connect($BrokerHost, 1883); $tcp.Close(); Write-Host "   `u{2705} MQTT" -ForegroundColor Green } catch { Write-Host "   `u{274C} MQTT" -ForegroundColor Red; $allOk = $false } }
    else { $m = kubectl get pods -n $Namespace -l app=mosquitto --field-selector=status.phase=Running -o name 2>$null; if ($m) { Write-Host "   `u{2705} MQTT (in-cluster)" -ForegroundColor Green } else { Write-Host "   `u{274C} MQTT not running" -ForegroundColor Red; $allOk = $false } }
    if (-not $allOk) { throw "Connectivity failed" }
    Write-Host ""
}

function Query-Prometheus {
    param([string]$Query)
    try {
        $encoded = [System.Uri]::EscapeDataString($Query)
        $raw = curl.exe -s "$PrometheusUrl/api/v1/query?query=$encoded" 2>&1
        $response = $raw -join '' | ConvertFrom-Json
        if ($response.status -eq "success" -and $response.data.result.Count -gt 0) {
            $total = 0.0; foreach ($r in $response.data.result) { $val = [string]$r.value[1]; if ($val -ne "NaN" -and $val -ne "") { $total += [double]$val } }; return $total
        }
        return $null
    } catch { Write-Warning "Prometheus: $_"; return $null }
}

function Reset-Pipeline {
    Write-Host "`u{1F504} Restarting pipeline..." -ForegroundColor Yellow
    try { $h = Get-AuthHeaders; Invoke-RestMethod -Uri "$BackendUrl/api/config/enrichment/restart" -Method Post -Headers $h -TimeoutSec 30 | Out-Null; Write-Host "`u{2705} Restarted" -ForegroundColor Green } catch { Write-Warning "Restart failed: $_" }
}

function Ensure-WildcardDevice {
    Write-Host "`u{1F4CB} Ensuring wildcard device..." -ForegroundColor Yellow
    try {
        $h = Get-AuthHeaders; $devices = Invoke-RestMethod -Uri "$BackendUrl/api/devices?page_size=100" -Method Get -Headers $h -TimeoutSec 10
        foreach ($d in $devices.data) { if ($null -eq $d.ingestion_id) { Write-Host "`u{2705} Wildcard exists" -ForegroundColor Green; return } }
        $body = @{ name = "perf-test-wildcard"; description = "Wildcard for load curve"; enabled = $true; sensitivity = "internal"; created_by = $Username } | ConvertTo-Json
        Invoke-RestMethod -Uri "$BackendUrl/api/devices" -Method Post -Body $body -Headers $h -TimeoutSec 10 | Out-Null
        Write-Host "`u{2705} Wildcard registered" -ForegroundColor Green
    } catch { Write-Warning "Wildcard failed: $_" }
}

function Start-LocalPublisher { param([int]$TestRate); Write-Host "`u{1F4E8} Local publisher at $TestRate msg/s..." -ForegroundColor Yellow; return Start-Process -FilePath "python" -ArgumentList "$PerfTestScript --rate $TestRate --duration $Duration --broker $BrokerHost" -PassThru -NoNewWindow }
function Wait-LocalPublisher { param($Process); $Process | Wait-Process | Out-Null }

function Start-ClusterPublisher {
    param([int]$TestRate)
    $ratePerPod = [math]::Ceiling($TestRate / $Pods)
    Write-Host "`u{1F4E8} Deploying $Pods pods at $ratePerPod msg/s each..." -ForegroundColor Yellow
    kubectl delete job $JobName -n $Namespace 2>$null | Out-Null; kubectl delete pods -n $Namespace -l app=$JobName 2>$null | Out-Null; kubectl delete configmap $ConfigMapName -n $Namespace 2>$null | Out-Null; Start-Sleep 3
    kubectl create configmap $ConfigMapName -n $Namespace --from-file=perf_test_mqtt.py=$PerfTestScript 2>&1 | Out-Null
    $manifest = Get-Content $JobManifest -Raw
    $manifest = $manifest -replace 'name: mqtt-perf-test', "name: $JobName" -replace 'app: mqtt-perf-test', "app: $JobName" -replace 'parallelism: 2', "parallelism: $Pods" -replace 'completions: 2', "completions: $Pods" -replace '"1500"', "`"$ratePerPod`"" -replace '"300"', "`"$Duration`"" -replace '"10"', "`"$Threads`"" -replace 'perf-test-script', $ConfigMapName
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
$mode = if ($Local) { "LOCAL" } else { "CLUSTER ($Pods pods in '$Namespace')" }
Write-Host "`n`u{1F4CA} SOAM Load Curve Experiment" -ForegroundColor Cyan
Write-Host "=" * 60
Write-Host "   Mode:         $mode"
Write-Host "   Rates:        $($RateList -join ', ') msg/s"
Write-Host "   Duration:     ${Duration}s"
Write-Host "   Cooldown:     ${CooldownSeconds}s"
Write-Host "   Namespace:    $Namespace"
Write-Host "   Output:       $OutputFile"
Write-Host "=" * 60

Test-Connectivity; Get-AuthToken; Ensure-WildcardDevice

$csvLines = @("target_rate_msg_s,achieved_enrichment_rate,batch_latency_p95_s,batch_latency_avg_s,ingestor_buffer_msgs,test_duration_s,timestamp")

foreach ($rate in $RateList) {
    Write-Host "`n`u{1F680} === Test: $rate msg/s for ${Duration}s ===" -ForegroundColor Cyan
    Reset-Pipeline | Out-Null; Start-Sleep 10
    $preCount = Query-Prometheus 'enrichment_records_processed_total'

    if ($Local) { $proc = Start-LocalPublisher -TestRate $rate; Wait-LocalPublisher -Process $proc } else { Start-ClusterPublisher -TestRate $rate; Wait-ClusterPublisher; Cleanup-ClusterPublisher }

    Write-Host "`u{23F3} Waiting ${CooldownSeconds}s for drain..." -ForegroundColor Yellow; Start-Sleep $CooldownSeconds

    $tp = Query-Prometheus 'rate(enrichment_records_processed_total[5m])'
    $p95 = Query-Prometheus 'histogram_quantile(0.95, rate(spark_batch_processing_latency_seconds_bucket[5m]))'
    $avg = Query-Prometheus 'rate(spark_batch_processing_latency_seconds_sum[5m]) / rate(spark_batch_processing_latency_seconds_count[5m])'
    $buf = Query-Prometheus 'sum(ingestor_buffer_size_messages)'
    $postCount = Query-Prometheus 'enrichment_records_processed_total'
    $total = if ($preCount -ne $null -and $postCount -ne $null) { [math]::Round($postCount - $preCount, 0) } else { "N/A" }
    $tpR = if ($tp) { [math]::Round($tp, 1) } else { "N/A" }
    $p95R = if ($p95) { [math]::Round($p95, 3) } else { "N/A" }
    $avgR = if ($avg) { [math]::Round($avg, 3) } else { "N/A" }
    $bufR = if ($buf) { [math]::Round($buf, 0) } else { "N/A" }
    $ts = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"

    Write-Host "`n`u{1F4C8} Results for $rate msg/s:" -ForegroundColor Green
    Write-Host "   Enrichment rate: $tpR records/s"
    Write-Host "   p95 latency:     $p95R s"
    Write-Host "   Avg latency:     $avgR s"
    Write-Host "   Buffer:          $bufR msgs"
    Write-Host "   Total processed: $total records"

    $csvLines += "$rate,$tpR,$p95R,$avgR,$bufR,$Duration,$ts"
}

$csvLines | Out-File -FilePath $OutputFile -Encoding UTF8
Write-Host "`n`u{2705} Results saved to $OutputFile" -ForegroundColor Green
Write-Host "`n`u{1F4CA} Summary:" -ForegroundColor Cyan
Write-Host "-" * 80
Write-Host ("{0,-15} {1,-20} {2,-18} {3,-18} {4,-15}" -f "Rate", "Enrichment", "p95 (s)", "Avg (s)", "Buffer")
Write-Host "-" * 80
for ($i = 1; $i -lt $csvLines.Count; $i++) { $p = $csvLines[$i] -split ","; Write-Host ("{0,-15} {1,-20} {2,-18} {3,-18} {4,-15}" -f $p[0], $p[1], $p[2], $p[3], $p[4]) }
Write-Host "-" * 80
