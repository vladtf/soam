# AoT Open Data — Test Results

## Test Configuration

| Parameter         | Value                                                    |
| ----------------- | -------------------------------------------------------- |
| Cluster           | Azure AKS (Standard_D8s_v5)                              |
| Namespace         | `soam`                                                   |
| Publisher pods    | 4 × 2,500 msg/s = 10,000 msg/s target                    |
| Ingestor replicas | 5 (HPA-scaled)                                           |
| Data source       | AoT Chicago complete archive (2016–2022)                 |
| Data slice        | 500,000 rows extracted, 1,500 committed (aot_slice.json) |

## Data Diversity

Extracted from `AoT_Chicago.complete.2022-08-31/data.csv.gz`:

| MQTT Topic        | Sensors                                                    | Rows        | Units               |
| ----------------- | ---------------------------------------------------------- | ----------- | ------------------- |
| `aot_temperature` | 13 (bmp180, htu21d, pr103j2, tmp112, tsys01, at0–at3, ...) | 189,407     | °C                  |
| `aot_light`       | 7 (apds_9006_020, tsl250rd, mlx75305, ...)                 | 174,296     | lux, μW/cm²         |
| `aot_humidity`    | 4 (hih4030, htu21d, sht25, hih6130)                        | 73,260      | %RH                 |
| `aot_air_quality` | 7 (co, no2, o3, so2, h2s, ...)                             | 35,259      | ppm                 |
| `aot_pressure`    | 2 (bmp180, lps25h)                                         | 27,778      | hPa                 |
| **Total**         | **29 sensors, 3 subsystems**                               | **500,000** | **5 unit families** |

## Schema Inference Results

All verified automatically — no manual schema definitions required:

- **Field discovery**: pipeline detected all payload fields across 5 topics (sensor_id, node_id, subsystem, sensor, parameter, temperature/humidity/pressure/concentration/intensity, unit, value_raw, value_hrf)
- **Multi-sensor normalization**: 13 different temperature sensors unified under canonical `temperature` field via global normalization rule, fed into average-temperature stream
- **Type handling**: mixed value types (integer ADC counts in `value_raw`, float °C in `value_hrf`, `NA` markers) correctly parsed by union schema transformer
- **Topic isolation**: each parameter type routed to a separate MQTT topic → distinct `ingestion_id` → no cross-contamination between temperature/pressure/humidity normalization

## Throughput Results (Prometheus)

Captured live from Prometheus during sustained AoT replay test (4 pods × 2,500 msg/s):

| Metric                 | Query                                             | Value            |
| ---------------------- | ------------------------------------------------- | ---------------- |
| Enrichment rate (3m)   | `rate(enrichment_records_processed_total[3m])`    | **10,974 rec/s** |
| Enrichment rate (5m)   | `rate(enrichment_records_processed_total[5m])`    | **11,083 rec/s** |
| Ingestor receive rate  | `sum(rate(ingestor_messages_received_total[3m]))` | **9,999 msg/s**  |
| Total records enriched | `enrichment_records_processed_total`              | 21,651,900       |

### Extraction command

```powershell
$promPod = kubectl get pods -n soam -l app=prometheus -o jsonpath="{.items[0].metadata.name}"

# Enrichment throughput (3m window)
kubectl exec $promPod -n soam -- sh -c 'wget -qO- "http://localhost:9090/api/v1/query?query=rate(enrichment_records_processed_total[3m])" 2>/dev/null'

# Enrichment throughput (5m window)
kubectl exec $promPod -n soam -- sh -c 'wget -qO- "http://localhost:9090/api/v1/query?query=rate(enrichment_records_processed_total[5m])" 2>/dev/null'

# Total records enriched
kubectl exec $promPod -n soam -- sh -c 'wget -qO- "http://localhost:9090/api/v1/query?query=enrichment_records_processed_total" 2>/dev/null'

# Ingestor receive rate (sum across all replicas)
kubectl exec $promPod -n soam -- sh -c 'wget -qO- "http://localhost:9090/api/v1/query?query=sum(rate(ingestor_messages_received_total[3m]))" 2>/dev/null'
```

## Throughput Comparison

| Metric                     | Synthetic data | AoT real data |
| -------------------------- | -------------- | ------------- |
| Payload fields             | 6              | 13            |
| MQTT topics                | 1              | 5             |
| Distinct sensor types      | 1              | 29            |
| Enrichment rate (rec/s)    | ~10,255        | ~10,974       |
| Ingestor recv rate (msg/s) | ~10,000        | ~9,999        |
| Schema inference overhead  | <2%            | <2%           |

Real data throughput matches synthetic — larger payloads and multi-topic ingestion do not degrade performance. The enrichment pipeline sustains ~11K rec/s with heterogeneous AoT data, comparable to the ~10.3K rec/s measured with synthetic single-topic data.

## How to Reproduce

```powershell
# AKS
.\tests\aot\run-aot-test.ps1 -Namespace soam -Pods 4 -Rate 2500 -Duration 900

# Local (Rancher Desktop)
.\tests\aot\run-aot-test.ps1 -Local -Namespace default -Pods 2 -Rate 500 -Duration 300
```

The script automatically:
1. Scales down other simulators
2. Deletes non-MQTT data sources on the ingestor
3. Registers a wildcard device on the backend
4. Deploys publisher pods with the committed `aot_slice.json`
5. Polls logs and cleans up on completion or Ctrl+C
