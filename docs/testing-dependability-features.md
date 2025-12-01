# Testing Dependability Features

This document describes how to test the dependability features of the SOAM platform.

---

## 1. Edge Buffer (Offline Tolerance)

**Purpose**: Ensure sensor data is not lost during network outages by buffering messages locally.

**Test Steps**:

1. Scale down the MQTT broker:
   ```powershell
   kubectl scale deployment mosquitto --replicas=0
   ```

2. Watch simulator logs (messages should be buffered):
   ```powershell
   kubectl logs deployment/simulator-temperature --tail=20
   ```
   Expected output:
   ```
   [temp_sensor_1] ⚠️ Disconnected from MQTT, buffering enabled
   [temp_sensor_1] 📦 Buffered message (1 pending)
   ```

3. Restore MQTT broker:
   ```powershell
   kubectl scale deployment mosquitto --replicas=1
   ```

4. Verify replay in logs:
   ```
   [temp_sensor_1] ✅ Connected to MQTT Broker
   [temp_sensor_1] 🔄 Replaying buffered messages...
   [temp_sensor_1] ✅ Replayed 5/5 buffered messages
   ```

---

## 2. Auto-scaling Ingestor

**Purpose**: Dynamically scale ingestor pods based on CPU/memory utilization.

**Prerequisites**: Install Kubernetes Metrics Server:
```powershell
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

**Test Steps**:

1. Apply HPA and verify configuration:
   ```powershell
   kubectl apply -f k8s/ingestor-hpa.yaml
   kubectl get hpa ingestor-hpa
   ```
   Expected output:
   ```
   NAME           REFERENCE             TARGETS           MINPODS   MAXPODS   REPLICAS
   ingestor-hpa   Deployment/ingestor   10%/70%, 15%/80%  1         5         1
   ```

2. Generate load to trigger scale-up:
   ```powershell
   kubectl exec -it deployment/ingestor -- /bin/sh -c '
     apt-get update && apt-get install -y stress
     stress --cpu 1 --timeout 60
   '
   ```

3. Watch pods scale up (in another terminal):
   ```powershell
   kubectl get pods -l app=ingestor
   ```

---

## 3. Data Retention Policies

**Purpose**: Automatically delete old data based on tier (Bronze: 7d, Silver: 30d, Gold: 90d).

**Test Steps**:

1. Apply retention configuration:
   ```powershell
   kubectl apply -f k8s/minio-retention.yaml
   kubectl wait --for=condition=complete job/minio-retention-setup --timeout=120s
   ```

2. Verify lifecycle rules:
   ```powershell
   kubectl port-forward svc/minio 9000:9000
   # In another terminal:
   mc alias set myminio http://localhost:9000 minio minio123
   mc ilm rule list myminio/lake
   ```
   Expected: Rules for `bronze/`, `silver/`, `gold/` prefixes with respective expiration days.

---

## 4. Authentication & Authorization

**Purpose**: JWT-based authentication with role-based access control.

**Test Steps**:

1. Port-forward backend:
   ```powershell
   kubectl port-forward svc/backend-external 8000:8000
   ```

2. Login and get token:
   ```powershell
   $response = Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" `
       -Method POST -ContentType "application/json" `
       -Body '{"username": "admin", "password": "admin"}'
   $token = $response.data.access_token
   ```

3. Access protected endpoint:
   ```powershell
   $headers = @{ "Authorization" = "Bearer $token" }
   Invoke-RestMethod -Uri "http://localhost:8000/api/auth/me" -Headers $headers
   ```
   Expected: Returns user info with roles `["admin", "user", "viewer"]`.

4. Verify unauthorized access is rejected:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8000/api/auth/me"  # No token
   ```
   Expected: 401 Unauthorized.

---

## 5. Data Sensitivity Labeling

**Purpose**: Classify sensor data by sensitivity level for access control.

| Label | Access Level |
|-------|--------------|
| PUBLIC | All users |
| INTERNAL | USER, ADMIN |
| CONFIDENTIAL | ADMIN only |
| RESTRICTED | ADMIN + audit |

**Test Steps**:

1. Register a device with sensitivity label:
   ```powershell
   $headers = @{ "Authorization" = "Bearer $token" }
   $body = @{
       ingestion_id = "test-sensor"
       name = "Test Device"
       sensitivity = "confidential"
       created_by = "admin"
   } | ConvertTo-Json
   
   Invoke-RestMethod -Uri "http://localhost:8000/api/devices" `
       -Method POST -Headers $headers -ContentType "application/json" -Body $body
   ```

2. Verify device has sensitivity label:
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8000/api/devices" -Headers $headers
   ```
   Expected: Device shows `sensitivity: "confidential"`.

---

## Quick Reference

| Feature | Key Files | Verification Command |
|---------|-----------|---------------------|
| Edge Buffer | `simulator/simulators/edge_buffer.py` | `kubectl logs deployment/simulator-temperature` |
| Auto-scaling | `k8s/ingestor-hpa.yaml` | `kubectl get hpa ingestor-hpa` |
| Retention | `k8s/minio-retention.yaml` | `mc ilm rule list myminio/lake` |
| Auth | `backend/src/auth/` | `curl /api/auth/login` |
| Sensitivity | `backend/src/database/models.py` | `curl /api/devices` |
