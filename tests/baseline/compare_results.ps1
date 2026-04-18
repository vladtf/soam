#!/usr/bin/env pwsh
# Compare two test results (JSON files from run_single_test.ps1).
#
# Usage:
#   .\tests\baseline\compare_results.ps1 -DynamicFile dynamic.json -BypassFile bypass.json
param(
    [Parameter(Mandatory)][string]$DynamicFile,
    [Parameter(Mandatory)][string]$BypassFile
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $DynamicFile)) { throw "File not found: $DynamicFile" }
if (!(Test-Path $BypassFile)) { throw "File not found: $BypassFile" }

$d = Get-Content $DynamicFile -Raw | ConvertFrom-Json
$b = Get-Content $BypassFile -Raw | ConvertFrom-Json

Write-Host ""
Write-Host "=" * 70
Write-Host "`u{1F4CA} BASELINE COMPARISON RESULTS" -ForegroundColor Cyan
Write-Host "=" * 70
Write-Host ""
Write-Host ("{0,-30} {1,-20} {2,-20}" -f "Metric", "Dynamic Schema", "Fixed Schema")
Write-Host "-" * 70
Write-Host ("{0,-30} {1,-20} {2,-20}" -f "Mode", $d.mode, $b.mode)
Write-Host ("{0,-30} {1,-20} {2,-20}" -f "Target Rate (msg/s)", $d.target_rate, $b.target_rate)
Write-Host ("{0,-30} {1,-20} {2,-20}" -f "Duration (s)", $d.duration_seconds, $b.duration_seconds)
Write-Host ("{0,-30} {1,-20} {2,-20}" -f "Pods", $d.pods, $b.pods)
Write-Host "-" * 70
Write-Host ("{0,-30} {1,-20} {2,-20}" -f "Throughput rate (rec/s)", $d.throughput_rate, $b.throughput_rate)
Write-Host ("{0,-30} {1,-20} {2,-20}" -f "Eff. Throughput (total/dur)", $d.effective_throughput, $b.effective_throughput)
Write-Host ("{0,-30} {1,-20} {2,-20}" -f "Total Records Processed", $d.total_processed, $b.total_processed)
Write-Host "-" * 70
Write-Host ""

# Overhead calculation
if ($d.throughput_rate -gt 0 -and $b.throughput_rate -gt 0) {
    $overhead = [math]::Round((1 - $d.throughput_rate / $b.throughput_rate) * 100, 1)
    Write-Host "Throughput overhead (rate):       " -NoNewline
    if ($overhead -le 5) { Write-Host "${overhead}% - NEGLIGIBLE" -ForegroundColor Green } else { Write-Host "${overhead}%" -ForegroundColor Yellow }
}

if ($d.effective_throughput -gt 0 -and $b.effective_throughput -gt 0) {
    $effOverhead = [math]::Round((1 - $d.effective_throughput / $b.effective_throughput) * 100, 1)
    Write-Host "Throughput overhead (effective):  " -NoNewline
    if ($effOverhead -le 5) { Write-Host "${effOverhead}% - NEGLIGIBLE" -ForegroundColor Green } else { Write-Host "${effOverhead}%" -ForegroundColor Yellow }
}

Write-Host ""
Write-Host "Dynamic run: $DynamicFile ($($d.timestamp))" -ForegroundColor DarkGray
Write-Host "Bypass run:  $BypassFile ($($b.timestamp))" -ForegroundColor DarkGray
