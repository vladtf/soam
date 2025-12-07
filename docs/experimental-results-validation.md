# Experimental Results Validation Document

This document provides detailed test procedures and evidence for each dependability mechanism listed in the experimental results table.

---

## Table of Contents
1. [Availability Mechanisms](#availability-mechanisms)
   - [A1: Local Buffer](#a1-local-buffer)
   - [A2: Auto-scaling](#a2-auto-scaling)
   - [A3: MinIO Cluster](#a3-minio-cluster)
2. [Reliability Mechanisms](#reliability-mechanisms)
   - [R1: Authentication](#r1-authentication)
   - [R2: Retention Policies](#r2-retention-policies)
   - [R3: Data Labeling](#r3-data-labeling)
3. [Performance Metrics](#performance-metrics)
   - [End-to-End Latency](#end-to-end-latency)
   - [Ingestion Throughput](#ingestion-throughput)

---

## Availability Mechanisms

### A1: Local Buffer

| Attribute     | Value                      |
| ------------- | -------------------------- |
| **Mechanism** | Local Buffer (Edge Buffer) |
| **Metric**    | Functional                 |
| **Target**    | Operational                |
| **Result**    | ✅ Verified                 |

#### Test Procedure

1. **Simulate MQTT broker failure** by scaling down the mosquitto deployment:
   ```powershell
   kubectl scale deployment mosquitto --replicas=0
   ```

2. **Observe simulator buffering behavior** in the logs:
   ```powershell
   kubectl logs deployment/simulator-temperature --tail=50
   ```

3. **Restore MQTT broker**:
   ```powershell
   kubectl scale deployment mosquitto --replicas=1
   ```

4. **Verify buffered messages are replayed**:
   ```powershell
   kubectl logs deployment/simulator-temperature --tail=50
   ```

#### Expected Evidence

**During Disconnection:**
```
2025-12-07 06:10:08,477 [INFO] [temp_sensor_84] 📤 Published to smartcity/sensors/temperature: {'temperature': 15.54, 'humidity': 74.8, 'sensor_id': 'temp_sensor_84', 'timestamp': '2025-12-07T06:10:08.477005'}
2025-12-07 06:10:18,648 [WARNING] [temp_sensor_84] ⚠️ Disconnected from MQTT (rc=Unspecified error), buffering enabled
2025-12-07 06:10:19,365 [INFO] [temp_sensor_84] 📦 Buffered message (1 pending)
2025-12-07 06:10:27,010 [INFO] [temp_sensor_84] 📦 Buffered message (2 pending)
2025-12-07 06:10:37,142 [INFO] [temp_sensor_84] 📦 Buffered message (3 pending)
```

**After Reconnection:**
```
2025-12-07 06:10:37,142 [INFO] [temp_sensor_84] 📦 Buffered message (3 pending)
2025-12-07 06:10:42,985 [INFO] [temp_sensor_84] 📦 Buffered message (4 pending)
2025-12-07 06:10:49,654 [INFO] [temp_sensor_84] ✅ Connected to MQTT Broker at mosquitto:1883
2025-12-07 06:10:49,654 [INFO] [temp_sensor_84] 🔄 Replaying 4 buffered messages...
2025-12-07 06:10:49,655 [INFO] [temp_sensor_84] ✅ Replayed 4/4 buffered messages
2025-12-07 06:10:53,001 [INFO] [temp_sensor_84] 📤 Published to smartcity/sensors/temperature: {'temperature': 21.57, 'humidity': 61.17, 'sensor_id': 'temp_sensor_84', 'timestamp': '2025-12-07T06:10:53.001385'}
```

#### Proof Screenshot

<img src="assets/local-buffer-test.png" alt="Local Buffer Test" width="50%"/>

#### Key Files
- `simulator/simulators/edge_buffer.py` - Edge buffer implementation
- `simulator/simulators/base_simulator.py` - Base simulator with buffer integration

---

### A2: Auto-scaling

| Attribute     | Value              |
| ------------- | ------------------ |
| **Mechanism** | Auto-scaling (HPA) |
| **Metric**    | Scale-out time     |
| **Target**    | < 60 seconds       |
| **Result**    | ✅ 15 seconds       |

#### Test Procedure

1. **Verify HPA is configured**:
   ```powershell
   kubectl get hpa ingestor-hpa
   ```

2. **Record initial state** (1 replica):
   ```powershell
   kubectl get pods -l app=ingestor -o wide
   ```

3. **Generate CPU load** to trigger scale-up:
   ```powershell
   # Install stress tool if not present (run entire command inside container shell)
   kubectl exec -it deployment/ingestor -- /bin/sh -c "apt-get update && apt-get install -y stress"
   
   # Generate CPU load for 120 seconds
   kubectl exec -it deployment/ingestor -- /bin/sh -c "stress --cpu 2 --timeout 120"
   ```

4. **Monitor scaling events** (in separate terminal):
   ```powershell
   # Record timestamps when new pods appear
   kubectl get pods -l app=ingestor -w
   ```

5. **Calculate scale-out time**: Time from load start to new pod reaching `Running` state.

#### Expected Evidence

**HPA Configuration:**
```powershell
NAME           REFERENCE             TARGETS                        MINPODS   MAXPODS   REPLICAS   AGE
ingestor-hpa   Deployment/ingestor   cpu: 4%/70%, memory: 48%/80%   1         5         1          6m44s
```

**Scale-out Event Log:**
```powershell
NAME                        READY   STATUS    RESTARTS   AGE
ingestor-59bdb4fddc-f8jrx   1/1     Running   0          28s
ingestor-59bdb4fddc-v4d5v   1/1     Running   0          9m29s
ingestor-59bdb4fddc-js2d9   0/1     Pending   0          0s
ingestor-59bdb4fddc-q4b98   0/1     Pending   0          0s
ingestor-59bdb4fddc-js2d9   0/1     Pending   0          0s
ingestor-59bdb4fddc-q4b98   0/1     Pending   0          0s
ingestor-59bdb4fddc-js2d9   0/1     ContainerCreating   0          0s
ingestor-59bdb4fddc-q4b98   0/1     ContainerCreating   0          0s ← Scale-out start
ingestor-59bdb4fddc-q4b98   1/1     Running             0          1s ← New pod running
ingestor-59bdb4fddc-js2d9   1/1     Running             0          1s
```

**Measurement:** 15 seconds from Pending to Running

#### Proof Screenshot

<img src="assets/auto-scaling-test.png" alt="Auto-scaling Test" width="50%"/>

#### Key Files
- `k8s/ingestor-hpa.yaml` - HPA configuration with CPU/memory thresholds

---

### A3: MinIO Cluster

| Attribute     | Value                |
| ------------- | -------------------- |
| **Mechanism** | MinIO 3-Node Cluster |
| **Metric**    | Functional           |
| **Target**    | Operational          |
| **Result**    | ✅ Verified           |

#### Test Procedure

1. **Verify all 3 MinIO pods are running**:
   ```powershell
   kubectl get pods -l app=minio
   ```

2. **Confirm data is accessible from any node**:
   ```powershell
   kubectl exec -it minio-0 -- sh -c "mc alias set local http://localhost:9000 minio minio123 && mc ls local/lake/gold --recursive | head -20"
   ```

3. **Simulate node failure** by deleting one pod:
   ```powershell
   kubectl delete pod minio-1
   ```

4. **Verify data remains accessible** during pod restart:
   ```powershell
   kubectl exec -it minio-0 -- mc ls local/lake/gold --recursive | head -10
   ```

5. **Confirm pod recovery**:
   ```powershell
   kubectl get pods -l app=minio -w
   ```

#### Expected Evidence

**Healthy Cluster State:**
```powershell
NAME      READY   STATUS    RESTARTS   AGE
minio-0   1/1     Running   0          16m
minio-1   1/1     Running   0          16m
minio-2   1/1     Running   0          16m
```

**Data Accessible During Failure:**
```powershell
➜  kubectl exec -it minio-0 -- sh -c "mc alias set local http://localhost:9000 minio minio123 && mc ls local/lake/ --recursive | head -20"
mc: Configuration written to `/tmp/.mc/config.json`. Please update your access credentials.
mc: Successfully created `/tmp/.mc/share`.
mc: Initialized share uploads `/tmp/.mc/share/uploads.json` file.
mc: Initialized share downloads `/tmp/.mc/share/downloads.json` file.
Added `local` successfully.
[2025-12-07 05:59:28 UTC]    29B STANDARD _ckpt/enrich_stream/commits/.51.d26ba71f-b3b8-4c29-8eb5-83c9c1ac5a1f.tmp
[2025-12-07 05:08:44 UTC]    29B STANDARD _ckpt/enrich_stream/commits/0
[2025-12-07 05:09:01 UTC]    29B STANDARD _ckpt/enrich_stream/commits/1
[2025-12-07 05:18:27 UTC]    29B STANDARD _ckpt/enrich_stream/commits/10
```

**Pod Auto-Recovery:**
```powershell
NAME      READY   STATUS    RESTARTS   AGE                                                                                                                                                                                                           
minio-0   1/1     Running   0   20m                                                                          
minio-1   0/1     Running   0   2s  
minio-2   1/1     Running   0   20m
minio-1   1/1     Running   0   11s  
```

#### Proof Screenshot

<img src="assets/minio-cluster-test.png" alt="MinIO Cluster Test" width="50%"/>

#### Key Files
- `k8s/minio-cluster.yaml` - MinIO StatefulSet with 3 replicas

---

## Reliability Mechanisms

### R1: Authentication

| Attribute     | Value              |
| ------------- | ------------------ |
| **Mechanism** | JWT Authentication |
| **Metric**    | Functional         |
| **Target**    | Operational        |
| **Result**    | ✅ Verified         |

#### Test Procedure

1. **Test successful login** with valid credentials:
   ```powershell
   $response = Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" `
       -Method POST -ContentType "application/json" `
       -Body '{"username": "admin", "password": "admin"}'
   $token = $response.data.access_token
   Write-Host "Token received: $($token.Substring(0,20))..."
   ```

2. **Access protected endpoint** with valid token:
   ```powershell
   $headers = @{ "Authorization" = "Bearer $token" }
   Invoke-RestMethod -Uri "http://localhost:8000/api/auth/me" -Headers $headers
   ```

3. **Verify unauthorized access is rejected** (no token):
   ```powershell
   try {
       Invoke-RestMethod -Uri "http://localhost:8000/api/auth/me"
   } catch {
       Write-Host "Status Code: $($_.Exception.Response.StatusCode.Value__)"
   }
   ```

4. **Test invalid credentials**:
   ```powershell
   try {
       Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" `
           -Method POST -ContentType "application/json" `
           -Body '{"username": "admin", "password": "wrongpassword"}'
   } catch {
       Write-Host "Status Code: $($_.Exception.Response.StatusCode.Value__)"
   }
   ```

#### Expected Evidence

**Successful Login Response:**
```powershell
➜  $response = Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" `                                                                                                                                                                       
>        -Method POST -ContentType "application/json" `
>        -Body '{"username": "admin", "password": "admin"}'
>    $token = $response.data.access_token
>    Write-Host "Token received: $($token.Substring(0,20))..."
Token received: eyJhbGciOiJIUzI1NiIs...

➜  $headers = @{ "Authorization" = "Bearer $token" }
>    Invoke-RestMethod -Uri "http://localhost:8000/api/auth/me" -Headers $headers

status  data    message detail
------  ----    ------- ------
success @{id=1; username=admin; email=admin@soam.local; roles=System.Object[]; is_active=True; created_at=07/12/2025 06:08:30; updated_at=07/12/2025 06:08:30}  User    info retrieved
```


**Unauthorized Access Response:**
```powershell
➜     try {
>        Invoke-RestMethod -Uri "http://localhost:8000/api/auth/me"
>    } catch {
>        Write-Host "Status Code: $($_.Exception.Response.StatusCode.Value__)"
>    }
Status Code: 401
```

**Invalid Credentials Response:**
```powershell
➜     try {
>        Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" `
>            -Method POST -ContentType "application/json" `
>            -Body '{"username": "admin", "password": "wrongpassword"}'
>    } catch {
>        Write-Host "Status Code: $($_.Exception.Response.StatusCode.Value__)"
>    }
Status Code: 400
```

#### Proof Screenshot

<img src="assets/authentication-test.png" alt="Authentication Test" width="50%"/>

#### Key Files
- `backend/src/auth/routes.py` - Authentication endpoints
- `backend/src/auth/security.py` - JWT token creation/verification
- `backend/src/auth/dependencies.py` - Auth middleware

---

### R2: Retention Policies

| Attribute     | Value                   |
| ------------- | ----------------------- |
| **Mechanism** | Data Retention Policies |
| **Metric**    | Functional              |
| **Target**    | Operational             |
| **Result**    | ✅ Verified              |

#### Test Procedure

1. **Apply retention configuration**:
   ```powershell
   kubectl apply -f k8s/minio-retention.yaml
   kubectl wait --for=condition=complete job/minio-retention-setup --timeout=120s
   ```

2. **Verify lifecycle rules are configured**:
   ```powershell
   kubectl exec -it minio-0 -- sh -c "mc alias set local http://localhost:9000 minio minio123 && mc ilm rule list local/lake"
   ```


#### Expected Evidence

**Lifecycle Rules Summary:**
```powershell
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Expiration for latest version (Expiration)                                             │
├──────────────────────┬─────────┬─────────┬──────┬────────────────┬─────────────────────┤
│ ID                   │ STATUS  │ PREFIX  │ TAGS │ DAYS TO EXPIRE │ EXPIRE DELETEMARKER │
├──────────────────────┼─────────┼─────────┼──────┼────────────────┼─────────────────────┤
│ d4qgnccbn9khcnnfth9g │ Enabled │ bronze/ │ -    │              7 │ false               │
│ d4qgnccbn9khcif9ar00 │ Enabled │ silver/ │ -    │             30 │ false               │
│ d4qgnccbn9khddafpu9g │ Enabled │ gold/   │ -    │             90 │ false               │
│ d4qhjh2i2rvpq47clq10 │ Enabled │ bronze/ │ -    │              7 │ false               │
│ d4qhjh2i2rvpqbvqcqm0 │ Enabled │ silver/ │ -    │             30 │ false               │
│ d4qhjh2i2rvpqepr8g6g │ Enabled │ gold/   │ -    │             90 │ false               │
│ d4qi6f92pfu05nb27ulg │ Enabled │ bronze/ │ -    │              7 │ false               │
│ d4qi6f92pfu05afvbc2g │ Enabled │ silver/ │ -    │             30 │ false               │
│ d4qi6f92pfu05d4of200 │ Enabled │ gold/   │ -    │             90 │ false               │
└──────────────────────┴─────────┴─────────┴──────┴────────────────┴─────────────────────┘
┌──────────────────────────────────────────────────────────────────────────────────┐
│ Expiration for older versions (NoncurrentVersionExpiration)                      │
├──────────────────────┬─────────┬─────────┬──────┬────────────────┬───────────────┤
│ ID                   │ STATUS  │ PREFIX  │ TAGS │ DAYS TO EXPIRE │ KEEP VERSIONS │
├──────────────────────┼─────────┼─────────┼──────┼────────────────┼───────────────┤
│ d4qgnccbn9khcnnfth9g │ Enabled │ bronze/ │ -    │              3 │             0 │
│ d4qgnccbn9khcif9ar00 │ Enabled │ silver/ │ -    │              7 │             0 │
│ d4qgnccbn9khddafpu9g │ Enabled │ gold/   │ -    │             14 │             0 │
│ d4qhjh2i2rvpq47clq10 │ Enabled │ bronze/ │ -    │              3 │             0 │
│ d4qhjh2i2rvpqbvqcqm0 │ Enabled │ silver/ │ -    │              7 │             0 │
│ d4qhjh2i2rvpqepr8g6g │ Enabled │ gold/   │ -    │             14 │             0 │
│ d4qi6f92pfu05nb27ulg │ Enabled │ bronze/ │ -    │              3 │             0 │
│ d4qi6f92pfu05afvbc2g │ Enabled │ silver/ │ -    │              7 │             0 │
│ d4qi6f92pfu05d4of200 │ Enabled │ gold/   │ -    │             14 │             0 │
└──────────────────────┴─────────┴─────────┴──────┴────────────────┴───────────────┘
```


#### Proof Screenshot

<img src="assets/retention-policies-test.png" alt="Retention Policies Test" width="50%"/>

#### Key Files
- `k8s/minio-retention.yaml` - Lifecycle rules configuration job

---

### R3: Data Labeling

| Attribute     | Value                     |
| ------------- | ------------------------- |
| **Mechanism** | Data Sensitivity Labeling |
| **Metric**    | Functional                |
| **Target**    | Operational               |
| **Result**    | ✅ Verified                |

#### Test Procedure

1. **Login and get authentication token**:
   ```powershell
   $response = Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" `
       -Method POST -ContentType "application/json" `
       -Body '{"username": "admin", "password": "admin"}'
   $token = $response.data.access_token
   $headers = @{ "Authorization" = "Bearer $token" }
   ```

2. **Register a device with sensitivity label**:
   ```powershell
   $body = @{
         enabled = $true
         sensitivity = "confidential"
         data_retention_days = 90
         ingestion_id = "mqtt_local_simulators_mqtt_5aa60e4d_smartcity_sensors_temperature"
         name = "Confidential Test Device"
         description = ""
         created_by = "admin"
   } | ConvertTo-Json
   
   Invoke-RestMethod -Uri "http://localhost:8000/api/devices" `
       -Method POST -Headers $headers -ContentType "application/json" -Body $body | ConvertTo-Json
   ```

3. **Verify device has correct sensitivity label**:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8000/api/devices" -Headers $headers | ConvertTo-Json
   ```

4. **Test access control based on sensitivity**:
  - Create a computation and tile that use confidential data
  - Verify only authorized users can access the results
  - Verify unauthorized users are denied access

#### Expected Evidence

**Device Registration Response:**
```json
{
  "status": "success",
  "data": {
    "id": 1,
    "ingestion_id": "mqtt_local_simulators_mqtt_5aa60e4d_smartcity_sensors_temperature",
    "name": "Confidential Test Device",
    "description": "",
    "enabled": true,
    "sensitivity": "confidential",
    "data_retention_days": 90,
    "created_at": "2025-12-07T07:02:17",
    "updated_at": "2025-12-07T07:02:17",
    "created_by": "admin",
    "updated_by": null
  },
  "message": "Device registered successfully",
  "detail": null
}
```

**Device List with Sensitivity Labels:**
```json
{
  "status": "success",
  "data": [
    {
      "id": 1,
      "ingestion_id": "mqtt_local_simulators_mqtt_5aa60e4d_smartcity_sensors_temperature",
      "name": "Confidential Test Device",
      "description": "",
      "enabled": true,
      "sensitivity": "confidential",
      "data_retention_days": 90,
      "created_at": "2025-12-07T07:02:17",
      "updated_at": "2025-12-07T07:02:17",
      "created_by": "admin",
      "updated_by": null
    }
  ],
  "total": 1,
  "page": null,
  "page_size": null,
  "message": "Devices retrieved successfully",
  "detail": null
}
```


#### Proof Screenshot

- Authorized Access Test:
  
  <img src="assets/authorized-success-test.png" alt="Authorized Access Test" width="50%"/>

- Unauthorized Access Test:

  <img src="assets/unauthorized-failure-test.png" alt="Unauthorized Access Test" width="50%"/>

#### Key Files
- `backend/src/database/models.py` - `DataSensitivity` enum
- `backend/src/api/device_routes.py` - Device registration with sensitivity
- `backend/src/computations/sensitivity.py` - Sensitivity access control

---

## Performance Metrics

### End-to-End Latency

| Attribute     | Value                                   |
| ------------- | --------------------------------------- |
| **Mechanism** | End-to-End Pipeline                     |
| **Metric**    | Message Latency                         |
| **Target**    | TODO: Define target (e.g., < 5 seconds) |
| **Result**    | TODO: Measure actual latency            |

#### Test Procedure

1. **Instrument a test message with timestamp**:
   ```powershell
   # Publish MQTT message with embedded timestamp
   $timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
   $message = @{
       sensor_id = "latency-test"
       temperature = 25.5
       sent_timestamp = $timestamp
   } | ConvertTo-Json
   
   # Publish to MQTT (requires mosquitto_pub)
   mosquitto_pub -h localhost -p 1883 -t "sensors/temperature" -m $message
   ```

2. **Query data from gold layer** and calculate latency:
   ```powershell
   # Wait for data to appear in gold layer
   Start-Sleep -Seconds 10
   
   # Query via backend API
   $result = Invoke-RestMethod -Uri "http://localhost:8000/api/spark/average-temperature?minutes=1"
   $received_timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
   
   # Calculate latency
   $latency_ms = $received_timestamp - $timestamp
   Write-Host "End-to-End Latency: $latency_ms ms"
   ```

3. **Alternative: Check Spark streaming metrics**:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8000/api/spark/streams-status"
   ```

#### Expected Evidence

**Streaming Query Metrics:**
```json
{
  "streams": [
    {
      "name": "avg_temperature_stream",
      "isActive": true,
      "recentProgress": {
        "inputRowsPerSecond": 10.5,
        "processedRowsPerSecond": 10.5,
        "batchDuration": "2000ms"
      }
    }
  ]
}
```

**Latency Measurement:**
```
End-to-End Latency: TODO ms
```

#### Proof Screenshot

<!-- TODO: Add screenshot showing latency measurement -->
![End-to-End Latency Test](TODO: path/to/screenshot.png)

---

### Ingestion Throughput

| Attribute     | Value                                    |
| ------------- | ---------------------------------------- |
| **Mechanism** | Ingestion Pipeline                       |
| **Metric**    | Throughput                               |
| **Target**    | TODO: Define target (e.g., > 1000 msg/s) |
| **Result**    | TODO: Measure actual throughput          |

#### Test Procedure

1. **Run performance test script**:
   ```powershell
   # Using the existing perf test
   python tests/perf_test_mqtt.py --messages 1000 --rate 100
   ```

2. **Monitor ingestor metrics**:
   ```powershell
   # Check Prometheus metrics
   Invoke-RestMethod -Uri "http://localhost:8001/api/metrics" | Select-String "messages_received"
   ```

3. **Calculate throughput from Grafana/Prometheus**:
   ```powershell
   # Query Prometheus for message rate
   # rate(ingestor_messages_received_total[1m])
   ```

#### Expected Evidence

**Performance Test Output:**
```
Sending 1000 messages at 100 msg/s...
Total messages sent: 1000
Duration: 10.05 seconds
Actual throughput: 99.5 msg/s
Errors: 0
```

**Ingestor Metrics:**
```
# HELP ingestor_messages_received_total Total messages received
# TYPE ingestor_messages_received_total counter
ingestor_messages_received_total{ingestion_id="temp-sensor"} 15234
ingestor_messages_received_total{ingestion_id="air-quality"} 8912
```

**Throughput Measurement:**
```
Measured Throughput: TODO msg/s
```

#### Proof Screenshot

<!-- TODO: Add screenshot showing throughput metrics from Grafana -->
![Ingestion Throughput Test](TODO: path/to/screenshot.png)

#### Key Files
- `tests/perf_test_mqtt.py` - MQTT performance test script
- `ingestor/src/api/routers/health.py` - Prometheus metrics endpoint

---

## Summary Table

| ID  | Mechanism          | Metric          | Target      | Result   | Status |
| --- | ------------------ | --------------- | ----------- | -------- | ------ |
| A1  | Local Buffer       | Functional      | Operational | Verified | ✅      |
| A2  | Auto-scaling       | Scale-out time  | < 60s       | 15s      | ✅      |
| A3  | MinIO Cluster      | Functional      | Operational | Verified | ✅      |
| R1  | Authentication     | Functional      | Operational | Verified | ✅      |
| R2  | Retention Policies | Functional      | Operational | Verified | ✅      |
| R3  | Data Labeling      | Functional      | Operational | Verified | ✅      |
| P1  | End-to-End         | Message latency | TODO        | TODO     | ⏳      |
| P2  | Ingestion          | Throughput      | TODO        | TODO     | ⏳      |

---

## Appendix: Test Environment

| Component  | Version/Configuration |
| ---------- | --------------------- |
| Kubernetes | v1.28+                |
| MinIO      | RELEASE.2024-XX-XX    |
| Spark      | 3.5.0                 |
| Python     | 3.11                  |
| FastAPI    | 0.100+                |

**Cluster Resources:**
- Nodes: TODO (e.g., 3 nodes, 4 vCPU, 16GB RAM each)
- Storage Class: TODO (e.g., managed-premium)

---

## TODO Checklist

- [ ] Add screenshot for A1 (Local Buffer test)
- [ ] Add screenshot for A2 (Auto-scaling test)
- [ ] Add screenshot for A3 (MinIO Cluster test)
- [ ] Add screenshot for R1 (Authentication test)
- [ ] Add screenshot for R2 (Retention Policies test)
- [ ] Add screenshot for R3 (Data Labeling test)
- [ ] Define End-to-End latency target
- [ ] Measure End-to-End latency and add screenshot
- [ ] Define Ingestion throughput target
- [ ] Measure Ingestion throughput and add screenshot
- [ ] Fill in test environment details
