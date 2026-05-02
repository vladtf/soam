# AoT (Array of Things) Real Data Performance Test Runner
# Deploys N parallel pods in the cluster, each publishing real AoT sensor data at the specified rate
#
# Usage (local — Rancher Desktop / k3d):
#   .\tests\aot\run-aot-test.ps1 -Local -Namespace default
#   .\tests\aot\run-aot-test.ps1 -Local -Namespace default -Pods 4 -Rate 500 -Duration 600
#
# Usage (AKS):
#   .\tests\aot\run-aot-test.ps1 -Namespace soam
#   .\tests\aot\run-aot-test.ps1 -Namespace soam -Pods 4 -Rate 1000 -Duration 900
#
# Data: Uses the committed aot_slice.json (1,500 messages from 3 subsystems, 29 sensors).
#       For larger data, run extract_aot_data.py first, then use -DataFile.
#
# Check the status of the test with: kubectl get pods -n <namespace> -l app=aot-perf-test

param(
    [int]$Pods = 2,
    [int]$Rate = 100,
    [int]$Duration = 300,
    [int]$Threads = 5,
    [string]$Namespace = "soam",
    [string]$DataFile = "",
    [string]$Username = "admin",
    [string]$Password = "admin",
    [switch]$Local
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$JobName = "aot-perf-test"
$ScriptConfigMap = "aot-test-script"
$DataConfigMap = "aot-data"
$ScriptPath = "$PSScriptRoot\perf_test_aot.py"
$JobManifest = "$PSScriptRoot\aot-replay-job.yaml"

function Cleanup-TestResources {
    Write-Host "`n🛑 Cleaning up test resources..." -ForegroundColor Yellow
    kubectl delete jobs -n $Namespace -l app=aot-perf-test 2>$null | Out-Null
    # Delete any perf-related pods/jobs that may be lingering
    $perfJobs = kubectl get jobs -n $Namespace -o jsonpath="{.items[*].metadata.name}" 2>$null
    foreach ($j in ($perfJobs -split " ")) { if ($j -match "perf") { kubectl delete job $j -n $Namespace --force --grace-period=0 2>$null | Out-Null } }
    $perfPods = kubectl get pods -n $Namespace -o jsonpath="{.items[*].metadata.name}" 2>$null
    foreach ($p in ($perfPods -split " ")) { if ($p -match "perf") { kubectl delete pod $p -n $Namespace --force --grace-period=0 2>$null | Out-Null } }
    kubectl delete configmap $ScriptConfigMap $DataConfigMap -n $Namespace 2>$null | Out-Null
    Write-Host "✅ Cleanup complete" -ForegroundColor Green
}

# Default to committed slice
if (-not $DataFile) {
    $DataFile = "$PSScriptRoot\data\aot_slice.json"
}

if (-not (Test-Path $DataFile)) {
    Write-Host "❌ Data file not found: $DataFile" -ForegroundColor Red
    Write-Host "   Run extract_aot_data.py first, or use the committed aot_slice.json" -ForegroundColor Red
    exit 1
}

$dataSize = (Get-Item $DataFile).Length
$dataSizeKB = [math]::Round($dataSize / 1024)
$msgCount = (python -c "import json; print(len(json.load(open(r'$DataFile'))))")

$modeLabel = if ($Local) { "LOCAL ($Namespace)" } else { "AKS ($Namespace)" }

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host " AoT Real Data Performance Test" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Cluster      : $modeLabel"
Write-Host "  Rate per pod : $Rate msg/s"
Write-Host "  Pods         : $Pods (parallel)"
Write-Host "  Total target : $($Rate * $Pods) msg/s"
Write-Host "  Duration     : ${Duration}s"
Write-Host "  Threads/pod  : $Threads"
Write-Host "  Data file    : $(Split-Path $DataFile -Leaf) ($dataSizeKB KB, $msgCount msgs)"
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# ConfigMap size check (~1MB limit)
if ($dataSize -gt 900000) {
    Write-Host "❌ Data file too large for ConfigMap ($dataSizeKB KB > 900 KB)" -ForegroundColor Red
    Write-Host "   Use aot_slice.json or sample.json instead" -ForegroundColor Red
    exit 1
}

# Step 1: Clean up previous runs
Write-Host "[1/6] Cleaning up previous test resources..." -ForegroundColor Yellow
kubectl delete job $JobName -n $Namespace 2>$null
kubectl delete pods -n $Namespace -l app=aot-perf-test 2>$null
kubectl delete configmap $ScriptConfigMap -n $Namespace 2>$null
kubectl delete configmap $DataConfigMap -n $Namespace 2>$null
Start-Sleep -Seconds 5

# Step 2: Disable other simulators to isolate AoT data
Write-Host "[2/6] Scaling down other simulators..." -ForegroundColor Yellow
$allDeploys = kubectl get deploy -n $Namespace -o jsonpath="{.items[*].metadata.name}" 2>$null
$simulators = ($allDeploys -split " ") | Where-Object { $_ -match "simulator" }
foreach ($sim in $simulators) {
    $current = kubectl get deploy $sim -n $Namespace -o jsonpath="{.spec.replicas}" 2>$null
    if ($LASTEXITCODE -eq 0 -and $current -ne "0") {
        kubectl scale deploy $sim -n $Namespace --replicas=0 2>$null
        Write-Host "  ⏸️ Scaled down $sim (was $current)" -ForegroundColor DarkGray
    }
}
if ($simulators) {
    Write-Host "  ✅ Simulators disabled — only AoT data will flow" -ForegroundColor Green
    Write-Host ""
    Write-Host "  To restore after test:" -ForegroundColor DarkGray
    Write-Host "  kubectl scale deploy -n $Namespace $($simulators -join ' ') --replicas=1" -ForegroundColor DarkGray
} else {
    Write-Host "  ℹ️ No simulator deployments found" -ForegroundColor DarkGray
}

# Stop non-MQTT data source connectors on the ingestor (REST API, CoAP)
# so they don't produce errors when their backends are scaled down
$ingestorPod = kubectl get pods -n $Namespace -l app=ingestor -o jsonpath="{.items[0].metadata.name}" 2>$null
if ($ingestorPod) {
    Write-Host "  🔌 Deleting non-MQTT data sources on ingestor..." -ForegroundColor DarkGray
    $sourcesRaw = kubectl exec $ingestorPod -n $Namespace -- `
        python -c "import urllib.request,json; print(json.dumps(json.loads(urllib.request.urlopen('http://localhost:8001/api/data-sources?enabled_only=false').read())))" 2>$null
    if ($sourcesRaw) {
        $allSources = ($sourcesRaw | ConvertFrom-Json).data
        foreach ($ds in $allSources) {
            if ($ds.type_name -ne "mqtt") {
                kubectl exec $ingestorPod -n $Namespace -- `
                    python -c "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://localhost:8001/api/data-sources/$($ds.id)',method='DELETE'))" 2>$null | Out-Null
                Write-Host "    🗑️ Deleted $($ds.name) ($($ds.type_name))" -ForegroundColor DarkGray
            }
        }
    }
}
Write-Host ""

# Step 3: Register wildcard device and normalization rules on backend
Write-Host "[3/6] Configuring backend (wildcard device + normalization rules)..." -ForegroundColor Yellow

$backendPod = kubectl get pods -n $Namespace -l app=backend -o jsonpath="{.items[0].metadata.name}" 2>$null
if ($backendPod) {
    # Step 3a: Authenticate
    $loginScript = @"
import urllib.request, json
body = json.dumps({"username":"$Username","password":"$Password"}).encode()
req = urllib.request.Request("http://localhost:8000/api/auth/login", data=body, headers={"Content-Type":"application/json"}, method="POST")
resp = json.loads(urllib.request.urlopen(req).read())
print(resp["data"]["access_token"])
"@
    $token = kubectl exec $backendPod -n $Namespace -- python -c $loginScript 2>$null
    if (-not $token) {
        Write-Host "  ⚠️ Authentication failed — cannot configure backend" -ForegroundColor Yellow
    } else {
        Write-Host "  🔑 Authenticated as $Username" -ForegroundColor Green

        # Step 3b: Register wildcard device
        $deviceScript = @"
import urllib.request, json, sys
token = "$token"
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
req = urllib.request.Request("http://localhost:8000/api/devices?page_size=100", headers=headers)
devices = json.loads(urllib.request.urlopen(req).read())
for d in devices.get("data", []):
    if d.get("ingestion_id") is None:
        print(f"EXISTS:{d.get('name','?')}")
        sys.exit(0)
body = json.dumps({"name":"AoT Wildcard (accept all)","description":"Wildcard device for AoT perf test","enabled":True,"sensitivity":"internal","data_retention_days":90,"created_by":"$Username"}).encode()
req = urllib.request.Request("http://localhost:8000/api/devices", data=body, headers=headers, method="POST")
json.loads(urllib.request.urlopen(req).read())
print("CREATED")
"@
        $result = kubectl exec $backendPod -n $Namespace -- python -c $deviceScript 2>$null
        if ($result -match "^EXISTS:") {
            Write-Host "  ✅ Wildcard device already exists: $($result -replace '^EXISTS:','')" -ForegroundColor Green
        } elseif ($result -eq "CREATED") {
            Write-Host "  ✅ Wildcard device registered" -ForegroundColor Green
        } else {
            Write-Host "  ⚠️ Unexpected result: $result" -ForegroundColor Yellow
        }

        # Step 3c: List devices for verification
        $listScript = @"
import urllib.request, json
headers = {"Authorization": "Bearer $token", "Content-Type": "application/json"}
req = urllib.request.Request("http://localhost:8000/api/devices?page_size=100", headers=headers)
devices = json.loads(urllib.request.urlopen(req).read())
for d in devices.get("data", []):
    iid = d.get("ingestion_id") or "(wildcard)"
    enabled = "Y" if d.get("enabled") else "N"
    print(f"{enabled}|{d.get('name','?')}|{iid}")
"@
        Write-Host "  📋 Registered devices:" -ForegroundColor DarkGray
        $deviceList = kubectl exec $backendPod -n $Namespace -- python -c $listScript 2>$null
        if ($deviceList) {
            foreach ($line in $deviceList -split "`n") {
                $parts = $line.Trim() -split '\|'
                if ($parts.Length -ge 3) {
                    $icon = if ($parts[0] -eq "Y") { "✅" } else { "❌" }
                    Write-Host "    $icon $($parts[1]) — $($parts[2])" -ForegroundColor DarkGray
                }
            }
        }
    }
} else {
    Write-Host "  ⚠️ Backend pod not found — skipping configuration" -ForegroundColor Yellow
}
Write-Host ""

# Step 4: Upload test script and data as ConfigMaps
Write-Host "[4/6] Uploading test script and data to cluster..." -ForegroundColor Yellow
kubectl create configmap $ScriptConfigMap -n $Namespace --from-file=perf_test_aot.py=$ScriptPath
if ($LASTEXITCODE -ne 0) { Write-Host "Failed to create script ConfigMap" -ForegroundColor Red; exit 1 }

$dataFileName = Split-Path $DataFile -Leaf
kubectl create configmap $DataConfigMap -n $Namespace --from-file=$dataFileName=$DataFile
if ($LASTEXITCODE -ne 0) { Write-Host "Failed to create data ConfigMap" -ForegroundColor Red; exit 1 }

# Step 5: Patch job manifest with params and apply
Write-Host "[5/6] Deploying $Pods perf test pods (rate=$Rate, duration=$Duration, threads=$Threads)..." -ForegroundColor Yellow

$manifest = Get-Content $JobManifest -Raw
$manifest = $manifest -replace 'parallelism: 2', "parallelism: $Pods"
$manifest = $manifest -replace 'completions: 2', "completions: $Pods"
$manifest = $manifest -replace '"100"', "`"$Rate`""
$manifest = $manifest -replace '"300"', "`"$Duration`""
$manifest = $manifest -replace '"5"', "`"$Threads`""
if ($Local) {
    $manifest = $manifest -replace 'soamregistry\.azurecr\.io/simulator:latest', 'localhost:5000/soam/simulator:latest'
}

$manifest | kubectl apply -n $Namespace -f -
if ($LASTEXITCODE -ne 0) { Write-Host "Failed to create Job" -ForegroundColor Red; exit 1 }

# Step 6: Wait for pods to start
Write-Host "[6/6] Waiting for pods to start..." -ForegroundColor Yellow

$waitTimeout = 120
$elapsed = 0
while ($elapsed -lt $waitTimeout) {
    $running = kubectl get pods -n $Namespace -l app=aot-perf-test --field-selector=status.phase=Running -o name 2>$null
    $count = if ($running) { ($running | Measure-Object).Count } else { 0 }
    if ($count -ge $Pods) { break }
    Start-Sleep -Seconds 3
    $elapsed += 3
}

if ($elapsed -ge $waitTimeout) {
    Write-Host "❌ Timed out waiting for pods to start" -ForegroundColor Red
    kubectl get pods -n $Namespace -l app=aot-perf-test
    exit 1
}

$podNames = kubectl get pods -n $Namespace -l app=aot-perf-test -o jsonpath="{.items[*].metadata.name}"
$podList = $podNames -split " "

Write-Host ""
Write-Host "Test pods running:" -ForegroundColor Green
foreach ($pod in $podList) {
    Write-Host "  - $pod"
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host " Polling logs (~${Duration}s test)" -ForegroundColor Cyan
Write-Host " (Ctrl+C to stop watching, test continues in cluster)" -ForegroundColor DarkGray
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Poll logs while waiting for the job to complete
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
    kubectl logs $pod -n $Namespace --tail=30
}

# Combined summary
Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host " SUMMARY" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Pods         : $Pods"
Write-Host "  Rate/pod     : $Rate msg/s"
Write-Host "  Total target : $($Rate * $Pods) msg/s"
Write-Host "  Duration     : ${Duration}s"
Write-Host "  Data source  : $(Split-Path $DataFile -Leaf) ($msgCount real AoT messages)"
Write-Host ""
Write-Host "Verify pipeline processing:" -ForegroundColor Cyan
Write-Host "  kubectl logs statefulset/ingestor -n $Namespace --tail=20"
Write-Host "  kubectl port-forward svc/backend 8000:8000 -n $Namespace"
Write-Host "  curl http://localhost:8000/api/schema/stream/status"
Write-Host ""
Write-Host "Restore simulators after test:" -ForegroundColor Yellow
Write-Host "  kubectl get deploy -n $Namespace -o name | Select-String simulator | ForEach-Object { kubectl scale `$_ -n $Namespace --replicas=1 }"
Write-Host "======================================" -ForegroundColor Cyan
