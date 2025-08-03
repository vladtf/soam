# PowerShell script to test backend API endpoints
$baseUrl = "http://localhost:8000"  # Adjust if using different port

Write-Host "Testing backend API endpoints..." -ForegroundColor Green

# Test endpoints
$endpoints = @(
    @{Name="Health Check"; Url="$baseUrl/health"},
    @{Name="Spark Test"; Url="$baseUrl/test-spark"},
    @{Name="Sensor Data Test"; Url="$baseUrl/test-sensor-data"},
    @{Name="Buildings"; Url="$baseUrl/buildings"},
    @{Name="Running Spark Jobs"; Url="$baseUrl/sparkMasterStatus"},
    @{Name="Average Temperature"; Url="$baseUrl/averageTemperature"},
    @{Name="Temperature Alerts"; Url="$baseUrl/temperatureAlerts?sinceMinutes=60"}
)

foreach ($endpoint in $endpoints) {
    Write-Host "`nTesting $($endpoint.Name)..." -ForegroundColor Yellow
    try {
        $response = Invoke-RestMethod -Uri $endpoint.Url -Method GET -TimeoutSec 10
        Write-Host "✅ SUCCESS: $($endpoint.Name)" -ForegroundColor Green
        Write-Host "Response: $($response | ConvertTo-Json -Depth 2)" -ForegroundColor Gray
    } catch {
        Write-Host "❌ FAILED: $($endpoint.Name)" -ForegroundColor Red
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    }
    Start-Sleep -Seconds 1
}

Write-Host "`nAPI testing complete!" -ForegroundColor Green
