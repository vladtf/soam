#!/usr/bin/env pwsh
# Load Curve: Gradually increases message rate to find throughput saturation.
# Outputs a table + JSON showing where the pipeline peaks.
#
# Usage:
#   .\tests\baseline\run_load_curve.ps1 -Namespace soam -Rates "1000,5000,10000,15000,20000" -Duration 300 -Pods 4
#   .\tests\baseline\run_load_curve.ps1 -Local -Rates "500,1000,2000,5000" -Duration 120
param(
    [string]$Rates = "1000,5000,10000,15000,20000",
    [int]$Duration = 300,
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
    [string]$MetricsWindow = "3m",
    [string]$OutputFile = "tests/baseline/load_curve_results.json"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$RateList = ($Rates -split "," | ForEach-Object { [int]$_.Trim() }) | Sort-Object
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path (Split-Path $ScriptRoot)
$PerfTestScript = Join-Path $RepoRoot "tests" "perf_test_mqtt.py"
$JobManifest = Join-Path $RepoRoot "tests" "perf" "perf-test-job.yaml"
$script:AuthToken = $null
$JobName = "loadcurve-perf-test"
$ConfigMapName = "loadcurve-perf-script"
$script:PortForwardPids = @()

$OutputDir = Split-Path $OutputFile
if ($OutputDir -and !(Test-Path $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null }

# Ctrl+C cleanup
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    Get-Process -Name kubectl* -ErrorAction SilentlyContinue | ForEach-Object {
        try { $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine; if ($cmd -match 'port-forward') { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue } } catch { }
    }
}

# --- Helpers ---

function Stop-AllPortForwards {
    Get-Process -Name kubectl* -ErrorAction SilentlyContinue | ForEach-Object {
        try { $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine; if ($cmdLine -match 'port-forward') { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue; Write-Host "   Killed PID $($_.Id)" -ForegroundColor DarkGray } } catch { }
    }
    $script:PortForwardPids = @()
}

function Start-PortForwards {
    if ($Local) { return }
    Write-Host "`u{1F517} Starting port-forwards..." -ForegroundColor Yellow
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

function Ensure-BackendReachable {
    try { $c = curl.exe -s -m 3 "$BackendUrl/api/health" 2>&1; if ($c -and ($c | ConvertFrom-Json -ErrorAction SilentlyContinue)) { return } } catch { }
    Write-Host "   Backend unreachable, restarting port-forwards..." -ForegroundColor DarkYellow
    Stop-PortForwards; Start-PortForwards
}

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
    } catch { return $null }
}

function Reset-Pipeline {
    Ensure-BackendReachable
    try { $h = Get-AuthHeaders; Invoke-RestMethod -Uri "$BackendUrl/api/config/enrichment/restart" -Method Post -Headers $h -TimeoutSec 30 | Out-Null } catch { Write-Warning "Restart failed: $_" }
}

function Ensure-WildcardDevice {
    try {
        $h = Get-AuthHeaders
        $devices = Invoke-RestMethod -Uri "$BackendUrl/api/devices?page_size=100" -Method Get -Headers $h -TimeoutSec 10
        foreach ($d in $devices.data) { if ($null -eq $d.ingestion_id) { return } }
        $body = @{ name = "perf-test-wildcard"; description = "Wildcard for load curve"; enabled = $true; sensitivity = "internal"; created_by = $Username } | ConvertTo-Json
        Invoke-RestMethod -Uri "$BackendUrl/api/devices" -Method Post -Body $body -Headers $h -TimeoutSec 10 | Out-Null
    } catch { Write-Warning "Wildcard failed: $_" }
}

function Full-Cleanup {
    Write-Host "`u{1F9F9} Full cleanup..." -ForegroundColor Yellow
    Stop-PortForwards
    kubectl delete job $JobName -n $Namespace 2>$null | Out-Null
    kubectl delete configmap $ConfigMapName -n $Namespace 2>$null | Out-Null
    $minioPod = kubectl get pods -n $Namespace -l app=minio -o jsonpath="{.items[0].metadata.name}" 2>$null
    if ($minioPod) {
        kubectl exec -n $Namespace $minioPod -- mc rm --recursive --force local/lake/bronze/ 2>$null | Out-Null
        kubectl exec -n $Namespace $minioPod -- mc rm --recursive --force local/lake/silver/ 2>$null | Out-Null
        kubectl exec -n $Namespace $minioPod -- mc rm --recursive --force local/lake/gold/ 2>$null | Out-Null
        kubectl exec -n $Namespace $minioPod -- mc rm --recursive --force local/lake/_ckpt/ 2>$null | Out-Null
        Write-Host "   `u{2705} MinIO cleared" -ForegroundColor Green
    }
    kubectl delete pod -n $Namespace -l app=backend 2>$null | Out-Null
    kubectl wait --for=condition=ready pod -l app=backend -n $Namespace --timeout=120s 2>&1 | Out-Null
    Write-Host "   `u{2705} Backend restarted" -ForegroundColor Green
    Start-PortForwards
    Get-AuthToken
    Ensure-WildcardDevice
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
    while ($true) {
        $c = kubectl get job $JobName -n $Namespace -o jsonpath="{.status.conditions[?(@.type=='Complete')].status}" 2>$null; if ($c -eq "True") { break }
        $f = kubectl get job $JobName -n $Namespace -o jsonpath="{.status.conditions[?(@.type=='Failed')].status}" 2>$null; if ($f -eq "True") { Write-Warning "Job failed!"; break }
        $pod = kubectl get pods -n $Namespace -l app=$JobName -o jsonpath="{.items[0].metadata.name}" 2>$null
        if ($pod) { $tail = kubectl logs $pod -n $Namespace --tail=1 2>$null; if ($tail) { Write-Host "  [$($pod.Substring([Math]::Max(0,$pod.Length-8)))] $tail" -ForegroundColor DarkGray } }
        Start-Sleep 15
    }
}

function Cleanup-ClusterPublisher { kubectl delete job $JobName -n $Namespace 2>$null | Out-Null; kubectl delete configmap $ConfigMapName -n $Namespace 2>$null | Out-Null }

# --- Main ---
$mode = if ($Local) { "LOCAL" } else { "CLUSTER ($Pods pods in '$Namespace')" }
Write-Host "`n`u{1F4CA} SOAM Load Curve Experiment" -ForegroundColor Cyan
Write-Host "=" * 60
Write-Host "   Mode:         $mode"
Write-Host "   Rates:        $($RateList -join ' -> ') msg/s"
Write-Host "   Duration:     ${Duration}s per rate"
Write-Host "   Cooldown:     ${CooldownSeconds}s"
Write-Host "   Metrics:      rate[${MetricsWindow}]"
Write-Host "   Output:       $OutputFile"
Write-Host "=" * 60

# Initial cleanup
Full-Cleanup

$results = @()
$step = 0

foreach ($rate in $RateList) {
    $step++
    Write-Host "`n`u{1F680} === Step $step/$($RateList.Count): $rate msg/s for ${Duration}s ===" -ForegroundColor Cyan

    $preCount = Query-Prometheus 'enrichment_records_processed_total'
    if ($null -eq $preCount) { $preCount = 0 }

    if ($Local) {
        $proc = Start-LocalPublisher -R $rate
        $proc | Wait-Process | Out-Null
    } else {
        Start-ClusterPublisher -R $rate
        Wait-ClusterPublisher
        Cleanup-ClusterPublisher
    }

    # Capture throughput immediately after test (before idle dilutes)
    Ensure-BackendReachable
    $throughput = Query-Prometheus "rate(enrichment_records_processed_total[$MetricsWindow])"

    # Brief pause between steps (no full drain needed since we just increase rate)
    Write-Host "`u{23F3} Pausing ${CooldownSeconds}s before next rate..." -ForegroundColor Yellow
    Start-Sleep $CooldownSeconds

    Ensure-BackendReachable
    $postCount = Query-Prometheus 'enrichment_records_processed_total'
    $totalProcessed = if ($preCount -ne $null -and $postCount -ne $null) { [math]::Round($postCount - $preCount, 0) } else { 0 }
    $effThroughput = if ($totalProcessed -gt 0 -and $Duration -gt 0) { [math]::Round($totalProcessed / $Duration, 1) } else { 0 }
    $tpRate = if ($throughput) { [math]::Round($throughput, 1) } else { 0 }

    $entry = [ordered]@{
        target_rate          = $rate
        throughput_rate      = $tpRate
        effective_throughput = $effThroughput
        total_processed      = $totalProcessed
        duration_seconds     = $Duration
        timestamp            = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
    }
    $results += $entry

    Write-Host "`n`u{1F4C8} $rate msg/s:" -ForegroundColor Green
    Write-Host "   Throughput (rate):      $tpRate rec/s"
    Write-Host "   Throughput (effective): $effThroughput rec/s"
    Write-Host "   Total processed:        $totalProcessed"
}

Stop-PortForwards

# Output JSON
$jsonOutput = [ordered]@{
    experiment   = "load_curve"
    namespace    = $Namespace
    pods         = $Pods
    duration_per_rate = $Duration
    metrics_window = $MetricsWindow
    timestamp    = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
    results      = $results
}
$jsonOutput | ConvertTo-Json -Depth 5 | Out-File -FilePath $OutputFile -Encoding UTF8

# Summary table
Write-Host "`n`u{1F4CA} Load Curve Summary:" -ForegroundColor Cyan
Write-Host "-" * 70
Write-Host ("{0,-15} {1,-20} {2,-20} {3,-15}" -f "Input (msg/s)", "Rate (rec/s)", "Effective (rec/s)", "Total")
Write-Host "-" * 70
foreach ($r in $results) {
    Write-Host ("{0,-15} {1,-20} {2,-20} {3,-15}" -f $r.target_rate, $r.throughput_rate, $r.effective_throughput, $r.total_processed)
}
Write-Host "-" * 70

# Find saturation point
$maxEff = ($results | ForEach-Object { $_.effective_throughput } | Measure-Object -Maximum).Maximum
$satEntry = $results | Where-Object { $_.effective_throughput -eq $maxEff } | Select-Object -First 1
Write-Host "`n`u{1F3C6} Peak throughput: $maxEff rec/s at $($satEntry.target_rate) msg/s input" -ForegroundColor Green

# Check for saturation (throughput stopped growing)
for ($i = 1; $i -lt $results.Count; $i++) {
    $prev = $results[$i-1].effective_throughput
    $curr = $results[$i].effective_throughput
    if ($prev -gt 0 -and $curr -gt 0) {
        $growth = ($curr - $prev) / $prev * 100
        if ($growth -lt 5 -and $results[$i].target_rate -gt $results[$i-1].target_rate) {
            Write-Host "`u{26A0}`u{FE0F} Saturation detected between $($results[$i-1].target_rate) and $($results[$i].target_rate) msg/s (only $([math]::Round($growth,1))% growth)" -ForegroundColor Yellow
            break
        }
    }
}

Write-Host "`n`u{2705} Results saved to $OutputFile" -ForegroundColor Green
