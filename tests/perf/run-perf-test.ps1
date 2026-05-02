# MQTT Performance Test Runner for AKS
# Deploys N parallel pods in the cluster, each sending messages at the specified rate
#
# Usage:
#   .\tests\perf\run-perf-test.ps1                                # defaults: 2 pods, 1500 rate, 300s, 10 threads
#   .\tests\perf\run-perf-test.ps1 -Pods 4 -Rate 1000 -Duration 600
#   .\tests\perf\run-perf-test.ps1 -Local -Namespace default      # local cluster (uses localhost registry)
#
# Aditionally you can scale down the pods that are not required for the test to free up cluster resources, e.g.:
#  kubectl scale deploy -n soam frontend cadvisor grafana prometheus neo4j simulator-temperature --replicas=0
# Restore with:
#  kubectl scale deploy -n soam frontend cadvisor grafana prometheus neo4j simulator-temperature --replicas=1
# 
# Check the status of the test with: kubectl get pods -n soam -l app=mqtt-perf-test

param(
    [int]$Pods = 2,
    [int]$Rate = 1500,
    [int]$Duration = 3000,
    [int]$Threads = 10,
    [string]$Namespace = "soam",
    [string]$MetricsWindow = "3m",
    [int]$CooldownSeconds = 60,
    [string]$OutputFile = "",
    [switch]$Local
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$JobName = "mqtt-perf-test"
$ConfigMapName = "perf-test-script"
$ScriptPath = "$PSScriptRoot\..\..\tests\perf_test_mqtt.py"
$JobManifest = "$PSScriptRoot\perf-test-job.yaml"

if (-not $OutputFile) {
    $OutputFile = "$PSScriptRoot\result_perf_${Rate}r_${Duration}s.json"
}

function Query-Prometheus {
    param([string]$Query)
    try {
        $promPod = kubectl get pods -n $Namespace -l app=prometheus -o jsonpath="{.items[0].metadata.name}" 2>$null
        if (-not $promPod) { return $null }
        $raw = kubectl exec $promPod -n $Namespace -- sh -c "wget -qO- 'http://localhost:9090/api/v1/query?query=$Query' 2>/dev/null" 2>$null
        if (-not $raw) { return $null }
        $response = $raw | ConvertFrom-Json
        if ($response.status -eq "success" -and $response.data.result.Count -gt 0) {
            $total = 0.0
            foreach ($r in $response.data.result) {
                $val = [string]$r.value[1]
                if ($val -ne "NaN" -and $val -ne "") { $total += [double]$val }
            }
            return $total
        }
        return $null
    } catch { return $null }
}

function Capture-Metrics {
    Write-Host ""
    Write-Host "📊 Capturing enrichment throughput from Prometheus..." -ForegroundColor Yellow

    $script:throughputVal = 0
    $script:ingestVal = 0
    $script:effectiveThroughput = 0
    $script:totalProcessed = 0

    $throughput = Query-Prometheus "rate(enrichment_records_processed_total[$MetricsWindow])"
    $ingestRate = Query-Prometheus "sum(rate(ingestor_messages_received_total[$MetricsWindow]))"
    $script:throughputVal = if ($throughput) { [math]::Round($throughput, 1) } else { 0 }
    $script:ingestVal = if ($ingestRate) { [math]::Round($ingestRate, 1) } else { 0 }

    Write-Host "  Enrichment rate ($MetricsWindow): $($script:throughputVal) rec/s" -ForegroundColor Cyan
    Write-Host "  Ingestor recv rate ($MetricsWindow): $($script:ingestVal) msg/s" -ForegroundColor Cyan

    if ($CooldownSeconds -gt 0) {
        Write-Host "⏳ Waiting ${CooldownSeconds}s for pipeline drain..." -ForegroundColor Yellow
        Start-Sleep $CooldownSeconds
    }

    $postCount = Query-Prometheus 'enrichment_records_processed_total'
    $script:totalProcessed = if ($null -ne $script:preCount -and $null -ne $postCount) { [math]::Round($postCount - $script:preCount, 0) } else { 0 }
    $script:effectiveThroughput = if ($script:totalProcessed -gt 0 -and $Duration -gt 0) { [math]::Round($script:totalProcessed / $Duration, 1) } else { 0 }

    $result = [ordered]@{
        test_type            = "Synthetic MQTT"
        target_rate          = $Rate * $Pods
        duration_seconds     = $Duration
        cooldown_seconds     = $CooldownSeconds
        pods                 = $Pods
        namespace            = $Namespace
        enrichment_rate      = $script:throughputVal
        ingestor_rate        = $script:ingestVal
        effective_throughput  = $script:effectiveThroughput
        total_processed      = $script:totalProcessed
        timestamp            = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
    }

    $script:resultJson = $result | ConvertTo-Json -Depth 3
    $script:resultJson | Out-File -FilePath $OutputFile -Encoding UTF8
    Write-Host "📊 Results saved to: $OutputFile" -ForegroundColor Green
}

function Cleanup-TestResources {
    Write-Host "`n🛑 Cleaning up test resources..." -ForegroundColor Yellow
    kubectl delete jobs -n $Namespace -l app=mqtt-perf-test 2>$null | Out-Null
    # Delete any perf-related pods/jobs that may be lingering
    $perfJobs = kubectl get jobs -n $Namespace -o jsonpath="{.items[*].metadata.name}" 2>$null
    foreach ($j in ($perfJobs -split " ")) { if ($j -match "perf") { kubectl delete job $j -n $Namespace --force --grace-period=0 2>$null | Out-Null } }
    $perfPods = kubectl get pods -n $Namespace -o jsonpath="{.items[*].metadata.name}" 2>$null
    foreach ($p in ($perfPods -split " ")) { if ($p -match "perf") { kubectl delete pod $p -n $Namespace --force --grace-period=0 2>$null | Out-Null } }
    kubectl delete configmap $ConfigMapName -n $Namespace 2>$null | Out-Null
    Write-Host "✅ Cleanup complete" -ForegroundColor Green
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host " MQTT Performance Test (AKS)" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Rate per pod : $Rate msg/s"
Write-Host "  Pods         : $Pods (parallel)"
Write-Host "  Total target : $($Rate * $Pods) msg/s"
Write-Host "  Duration     : ${Duration}s"
Write-Host "  Threads/pod  : $Threads"
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Clean up previous runs
Write-Host "[1/4] Cleaning up previous test resources..." -ForegroundColor Yellow
kubectl delete job $JobName -n $Namespace 2>$null
kubectl delete pods -n $Namespace -l app=mqtt-perf-test 2>$null
kubectl delete configmap $ConfigMapName -n $Namespace 2>$null
Start-Sleep -Seconds 5

# Step 2: Upload test script as ConfigMap
Write-Host "[2/4] Uploading test script to cluster..." -ForegroundColor Yellow
kubectl create configmap $ConfigMapName -n $Namespace --from-file=perf_test_mqtt.py=$ScriptPath
if ($LASTEXITCODE -ne 0) { Write-Host "Failed to create ConfigMap" -ForegroundColor Red; exit 1 }

# Step 3: Patch job manifest with params and apply
Write-Host "[3/4] Deploying $Pods perf test pods (rate=$Rate, duration=$Duration, threads=$Threads)..." -ForegroundColor Yellow

# Read the manifest and substitute values
$manifest = Get-Content $JobManifest -Raw
$manifest = $manifest -replace 'parallelism: 2', "parallelism: $Pods"
$manifest = $manifest -replace 'completions: 2', "completions: $Pods"
$manifest = $manifest -replace '"1500"', "`"$Rate`""
$manifest = $manifest -replace '"300"', "`"$Duration`""
$manifest = $manifest -replace '"10"', "`"$Threads`""
if ($Local) {
    $manifest = $manifest -replace 'soamregistry\.azurecr\.io/simulator:latest', 'localhost:5000/soam/simulator:latest'
}

$manifest | kubectl apply -n $Namespace -f -
if ($LASTEXITCODE -ne 0) { Write-Host "Failed to create Job" -ForegroundColor Red; exit 1 }

# Step 4: Wait for pods to start
Write-Host "[4/4] Waiting for pods to start..." -ForegroundColor Yellow

$waitTimeout = 120
$elapsed = 0
while ($elapsed -lt $waitTimeout) {
    $running = kubectl get pods -n $Namespace -l app=mqtt-perf-test --field-selector=status.phase=Running -o name 2>$null
    $count = if ($running) { ($running | Measure-Object).Count } else { 0 }
    if ($count -ge $Pods) { break }
    Start-Sleep -Seconds 3
    $elapsed += 3
}

if ($elapsed -ge $waitTimeout) {
    Write-Host "❌ Timed out waiting for pods to start" -ForegroundColor Red
    kubectl get pods -n $Namespace -l app=mqtt-perf-test
    exit 1
}

$podNames = kubectl get pods -n $Namespace -l app=mqtt-perf-test -o jsonpath="{.items[*].metadata.name}"
$podList = $podNames -split " "

Write-Host ""
Write-Host "Test pods running:" -ForegroundColor Green
foreach ($pod in $podList) {
    Write-Host "  - $pod"
}

# Capture pre-test enrichment count
$script:preCount = Query-Prometheus 'enrichment_records_processed_total'
if ($null -eq $script:preCount) { $script:preCount = 0 }
Write-Host "  📊 Pre-test enrichment count: $($script:preCount)" -ForegroundColor DarkGray

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host " Streaming logs from pod: $($podList[0])" -ForegroundColor Cyan
Write-Host " (Ctrl+C to stop watching, test continues in cluster)" -ForegroundColor DarkGray
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Poll logs while waiting for the job to complete
Write-Host "Polling logs every 15s (~${Duration}s test)..." -ForegroundColor DarkGray
Write-Host ""

$pollInterval = 15
$lastLines = @{}
try {
while ($true) {
    # Check if job completed
    $status = kubectl get job $JobName -n $Namespace -o jsonpath="{.status.conditions[?(@.type=='Complete')].status}" 2>$null
    if ($status -eq "True") { break }

    $failed = kubectl get job $JobName -n $Namespace -o jsonpath="{.status.conditions[?(@.type=='Failed')].status}" 2>$null
    if ($failed -eq "True") {
        Write-Host "❌ Job failed!" -ForegroundColor Red
        break
    }

    # Show latest stats line from each pod
    foreach ($pod in $podList) {
        $tail = kubectl logs $pod -n $Namespace --tail=1 2>$null
        if ($tail -and $tail -ne $lastLines[$pod]) {
            $lastLines[$pod] = $tail
            $shortName = $pod.Substring($pod.Length - [Math]::Min(8, $pod.Length))
            Write-Host "  [$shortName] $tail" -ForegroundColor DarkGray
        }
    }

    Start-Sleep -Seconds $pollInterval
}
} finally {
    Capture-Metrics
    Cleanup-TestResources
}

# Show results from all pods
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host " RESULTS" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

foreach ($pod in $podList) {
    Write-Host ""
    Write-Host "--- $pod ---" -ForegroundColor Green
    kubectl logs $pod -n $Namespace --tail=20
}

# Combined summary
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host " COMBINED SUMMARY" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Pods used          : $($podList.Count)"
Write-Host "  Rate per pod       : $Rate msg/s"
Write-Host "  Total target       : $($Rate * $Pods) msg/s"
Write-Host "  Enrichment rate    : $($script:throughputVal) rec/s"
Write-Host "  Ingestor recv rate : $($script:ingestVal) msg/s"
Write-Host "  Effective throughput: $($script:effectiveThroughput) rec/s"
Write-Host "  Total processed    : $($script:totalProcessed)"
Write-Host ""
Write-Host $script:resultJson -ForegroundColor DarkGray
Write-Host "======================================" -ForegroundColor Cyan
