# Ontology Schema Validation — Functional Test

This document provides a step-by-step procedure to verify that sensor data with fields **not defined in the OWL ontology** triggers a warning alert through the enrichment pipeline.

---

## Overview

| Attribute     | Value                                |
| ------------- | ------------------------------------ |
| **Mechanism** | Ontology-based Schema Validation     |
| **Metric**    | Functional                           |
| **Target**    | Alert raised for unknown fields      |
| **Result**    | *(fill in after testing)*            |

### How It Works

1. Sensor data is ingested via MQTT → stored in MinIO (Bronze layer)
2. Spark enrichment reads Bronze data and writes to Silver (Enriched) layer
3. When a user calls `GET /api/alerts`, the `ontology_alert_checker` fetches all known field names from the ingestor metadata, applies normalization rules, and compares them against DatatypeProperties defined in the ontology (`ontology.owl`)
4. Fields not in the ontology are returned as alerts in the API response and displayed in the frontend dashboard

### Known Ontology Fields

The ontology defines these DatatypeProperties (valid sensor data fields):

| Field             | Domain            |
| ----------------- | ----------------- |
| `temperature`     | TemperatureSensor |
| `humidity`        | HumiditySensor    |
| `pressure`        | PressureSensor    |
| `measurementTime` | Sensor            |
| `street`          | Address           |
| `city`            | Address           |
| `country`         | Address           |

Structural fields (`sensorId`, `sensor_id`, `timestamp`, etc.) are excluded from validation.

---

## Prerequisites

- Skaffold dev environment is running
- MQTT broker is accessible within the cluster (no port-forward needed)
- Backend pod has the ontology ConfigMap mounted at `/app/ontology.owl`
- Spark streaming is active (enrichment stream running)

### Verify Prerequisites

```powershell
# 1. Confirm ontology is mounted in backend
kubectl exec statefulset/backend -- ls -la /app/ontology.owl

# 2. Confirm ontology is loaded (check logs)
kubectl logs statefulset/backend --tail=200 | Select-String "Ontology validator loaded"

# 3. Confirm enrichment stream is running
Invoke-RestMethod -Uri "http://localhost:8000/api/spark/streams-status" | ConvertTo-Json -Depth 3
```

> **If `sensor_data_enrichment` is not listed as active**, the enrichment stream failed to start (e.g. no data/schema when backend booted). Trigger a retry by calling any Spark data endpoint:
> ```powershell
> Invoke-RestMethod -Uri "http://localhost:8000/api/spark/average-temperature"
> ```
> Then re-check streams status — all 3 streams (`sensor_data_enrichment`, `temperature_5min_averages`, `temperature_alert_detector`) should be active.

---

## Test Procedure

### Step 0 — Authenticate

All API calls require a JWT token. Login and store it for subsequent requests:

```powershell
$response = Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" `
    -Method POST -ContentType "application/json" `
    -Body '{"username": "admin", "password": "admin"}'
$token = $response.data.access_token
$headers = @{ "Authorization" = "Bearer $token" }
Write-Host "Token received: $($token.Substring(0,20))..."
```

---

### Step 1 — Start Publishing Messages with Unknown Fields (Background)

Start a background process inside the ingestor container that continuously publishes messages with fields **not defined** in the ontology, reusing a single MQTT connection:

```powershell
$POD = kubectl get pods -l app=ingestor -o jsonpath="{.items[0].metadata.name}"
kubectl exec $POD -- sh -c 'cat > /tmp/bogus_publisher.py << "EOF"
import paho.mqtt.client as mqtt
import json, datetime, time

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect("mosquitto", 1883)
print("Connected to MQTT broker", flush=True)

while True:
    msg = {
        "sensor_id": "test_bogus_sensor",
        "temperature": 22.5,
        "radiation": 999.9,
        "wind_speed": 12.3,
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
    }
    client.publish("smartcity/sensors/bogus-temperature", json.dumps(msg))
    ts = msg["timestamp"]
    print(f"Published bogus message at {ts}", flush=True)
    time.sleep(1)
EOF
nohup python /tmp/bogus_publisher.py > /tmp/bogus_publisher.log 2>&1 &'
Write-Host "Bogus publisher running inside container $POD"
```

Wait ~30 seconds for messages to be ingested into Bronze.

---

### Step 2 — Register the Sensor as a Device

The enrichment pipeline only processes data from **registered devices**. This script automatically discovers the `ingestion_id` from Bronze and registers the device:

```powershell
# Auto-discover the MQTT temperature ingestion_id from Bronze
$bronzeOutput = kubectl exec minio-0 -- sh -c "mc alias set local http://localhost:9000 minio minio123 2>/dev/null; mc ls local/lake/bronze/" 2>$null
$match = $bronzeOutput | Select-String "ingestion_id=([^/]+_smartcity_sensors_bogus-temperature)"
if (-not $match) {
    Write-Host "⚠️ No temperature ingestion_id found in Bronze. Wait for messages to be ingested and retry." -ForegroundColor Yellow
} else {
    $ingestionId = $match.Matches[0].Groups[1].Value
    Write-Host "Found ingestion_id: $ingestionId" -ForegroundColor Green

    $body = @{
        enabled = $true
        sensitivity = "internal"
        ingestion_id = $ingestionId
        name = "Bogus Test Sensor"
        description = "Temporary device for ontology validation testing"
        created_by = "admin"
    } | ConvertTo-Json

    Invoke-RestMethod -Uri "http://localhost:8000/api/devices" `
        -Method POST -Headers $headers -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 3
}
```

---

### Step 3 — Wait for Schema Evolution and Enrichment

The backend runs an **enrichment watchdog** background thread that:
- Ensures all streaming queries are running (every 30 seconds)
- Checks the ingestor schema for new fields (every 60 seconds)
- Automatically restarts the enrichment stream when new fields are detected

Wait ~90 seconds, then check the backend logs for the schema evolution message:

```powershell
kubectl logs statefulset/backend --tail=500 2>$null | Where-Object { $_ -match "Schema evolution|Active schema fields" }
```

**Expected log:**
```
🔄 Schema evolution detected — 2 new field(s): ['radiation', 'wind_speed']. Restarting enrichment stream.
✅ Enrichment stream restarted with updated schema
```

Wait another ~30 seconds for the enrichment to process batches with the new schema.

---

### Step 4 — Verify Data in Bronze and Silver Layers

Confirm the bogus sensor data made it through ingestion and enrichment:

**Bronze layer** (raw ingested data):
```powershell
kubectl exec -it minio-0 -- sh -c "mc alias set local http://localhost:9000 minio minio123 2>/dev/null && mc ls local/lake/bronze/ --recursive" | Select-String "bogus" | Select-Object -Last 10
```

**Silver layer** (enriched data — confirms device filter passed):
```powershell
kubectl exec -it minio-0 -- sh -c "mc alias set local http://localhost:9000 minio minio123 2>/dev/null && mc ls local/lake/silver/enriched/ --recursive" | Select-String "bogus" | Select-Object -Last 10
```

**Expected:** Both layers should show recent Parquet files. If Silver is empty, the device registration `ingestion_id` doesn't match — re-check Bronze and update the device.

---

### Step 5 — Verify Ontology Check in Backend Logs

The ontology check runs on-demand when the alerts API is called (Step 6). After calling the alerts endpoint, check the logs:

```powershell
kubectl logs statefulset/backend --tail=200 | Select-String "Ontology check|ontology_alert_checker"
```

**Expected log output:**
```
🔍 Ontology check: N unrecognized field(s) out of M sensor fields: ['radiation', 'wind_speed', ...]
```

---

### Step 6 — Verify Alerts API

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/alerts" -Headers $headers | Select-Object -ExpandProperty data | Where-Object { $_.message -match "radiation|wind_speed" } | ConvertTo-Json -Depth 3
```

**Expected response** (should include alerts for each unknown field):
```json
{
  "status": "success",
  "data": [
    {
      "id": "ontology-unknown-field-radiation",
      "message": "Sensor field \"radiation\" was detected during enrichment but is not defined in the ontology.",
      "variant": "warning",
      "link": "/ontology",
      "linkText": "View ontology",
      "dismissible": true
    },
    {
      "id": "ontology-unknown-field-wind_speed",
      "message": "Sensor field \"wind_speed\" was detected during enrichment but is not defined in the ontology.",
      "variant": "warning",
      "link": "/ontology",
      "linkText": "View ontology",
      "dismissible": true
    }
  ],
  "message": "..."
}
```

---

### Step 7 — Verify Alerts Appear in the Dashboard

Open the frontend at `http://localhost:3000` and check that warning alerts are displayed in the UI for the unknown fields.

---

### Step 8 — Stop Background Publisher

Kill the bogus publisher process inside the container:

```powershell
kubectl exec $POD -- sh -c "pkill -f bogus_publisher.py"
Write-Host "Background publisher stopped"
```

---

## Proof Screenshot

*(Insert screenshot here after running the test)*

<img src="assets/ontology-validation-test.png" alt="Ontology Validation Test" width="80%"/>

---

## Key Files

| File | Purpose |
| ---- | ------- |
| `backend/src/services/ontology_alert_checker.py` | Compares ingestor fields against ontology, surfaces unknown fields as alerts |
| `backend/src/neo4j/ontology_service.py` | Parses OWL ontology, provides known field names via `get_canonical_property_names()` |
| `backend/src/api/alert_routes.py` | `/api/alerts` endpoint that triggers all alert checkers |
| `backend/src/services/alert_service.py` | Alert registry — collects results from all registered checkers |
| `backend/src/spark/enrichment/cleaner.py` | Normalization rules applied before ontology comparison |
| `k8s/ontology-configmap.yaml` | OWL ontology definition (ConfigMap) |
| `k8s/backend.yaml` | Backend deployment with ontology volume mount |
