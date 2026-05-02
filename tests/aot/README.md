# AoT (Array of Things) Open Data Validation Tests

## Purpose

These tests validate the SOAM pipeline against **real heterogeneous IoT data** from
the [Array of Things](https://arrayofthings.github.io/) project — a network of ~130
urban sensor nodes deployed across Chicago from 2016–2022.

This addresses the reviewer feedback:
> *"The evaluation relies entirely on generated data. Validation on at least one
> open smart city dataset would strengthen the claims."*

The test demonstrates that schema inference correctly discovers field names and types,
and that normalization rules can map variant sensor names to canonical form.

## Data Provenance

### Source

| Field | Value |
|-------|-------|
| **Project** | Array of Things (AoT), Chicago |
| **Operator** | Argonne National Laboratory / University of Chicago |
| **Dataset** | `AoT_Chicago.complete.latest.tar` |
| **Archive date** | 2022-08-31 |
| **Download URL** | `https://www.mcs.anl.gov/research/projects/waggle/downloads/datasets/AoT_Chicago.complete.latest.tar` |
| **GitHub** | https://github.com/waggle-sensor/waggle/blob/master/data/README.md |
| **License** | Public domain (U.S. DOE / NSF funded) |
| **Original format** | CSV (compressed as `data.csv.gz`, ~34.5 GB) |
| **Time span** | 2016-09-14 → 2022-08-31 |
| **Nodes** | 126 physical sensor nodes |
| **Sensor entries** | 193 (10 subsystems, 63 sensors, 88 parameters) |

### How the data was obtained

```powershell
# 1. Download the complete archive (~36 GB tar)
cd d:\personal\soam\data
curl.exe -L -O "https://www.mcs.anl.gov/research/projects/waggle/downloads/datasets/AoT_Chicago.complete.latest.tar"

# 2. Extract
tar -xf AoT_Chicago.complete.latest.tar
# Produces: AoT_Chicago.complete.2022-08-31/
```

The raw CSV has the following columns:
```
timestamp,node_id,subsystem,sensor,parameter,value_raw,value_hrf
```

### Committed data slice (`aot_slice.json`)

A deterministic 1,500-message slice is committed via **Git LFS** at
`tests/aot/data/aot_slice.json`. This enables reproducible tests without
downloading the full 34.5 GB archive.

| Subsystem | Messages | Sensors | Parameters |
|-----------|----------|---------|------------|
| **chemsense** | 500 | at0, at1, at2, at3, co, h2s, lps25h, no2, o3, oxidizing_gases, reducing_gases, sht25, si1145, so2 | concentration, humidity, ir_intensity, pressure, temperature, uv_intensity, visible_light_intensity |
| **lightsense** | 500 | apds_9006_020, hih6130, ml8511, mlx75305, tmp421, tsl250rd, tsl260rd | humidity, intensity, temperature |
| **metsense** | 500 | bmp180, hih4030, htu21d, pr103j2, spv1840lr5h_b, tmp112, tsl250rd, tsys01 | humidity, intensity, pressure, temperature |

## Heterogeneity Demonstrated

This data exercises the pipeline with:

1. **Same quantity, different sensors** — Temperature is measured by 8+ sensors
   (`bmp180`, `htu21d`, `pr103j2`, `tmp112`, `tsys01`, `at0`–`at3`, `lps25h`,
   `sht25`, `tmp421`, `hih6130`), each with different raw value ranges.

2. **Mixed value types** — `value_raw` can be int, float, or `NA`; `value_hrf`
   can be float or `NA`. Some sensors report only raw (e.g., gas concentrations),
   others only HRF (e.g., bmp180 temperature).

3. **Multiple units** — °C, RH, ppm, hPa, lux, uW/cm², mG, dB, μg/m³.

4. **Multiple MQTT topics** — Data arrives on 3 separate topics:
   `smartcity/sensors/aot_meteorology`, `smartcity/sensors/aot_chemistry`,
   `smartcity/sensors/aot_light`.

## Usage

### Quick local test (uses committed slice, no download needed)

```powershell
# Requires port-forward: kubectl port-forward svc/mosquitto 1883:1883
cd d:\personal\soam
python tests/aot/perf_test_aot.py --rate 100 --duration 30 --data tests/aot/data/aot_slice.json --broker localhost
```

### Cluster test (parallel pods, like perf test)

```powershell
# Uses committed aot_slice.json by default
.\tests\aot\run-aot-test.ps1

# Higher rate with more pods
.\tests\aot\run-aot-test.ps1 -Pods 4 -Rate 500 -Duration 600

# Local cluster (Rancher Desktop)
.\tests\aot\run-aot-test.ps1 -Local -Namespace default
```

### Full extraction for larger tests

```powershell
# 1. Download the dataset (one-time, ~36 GB)
cd d:\personal\soam\data
curl.exe -L -O "https://www.mcs.anl.gov/research/projects/waggle/downloads/datasets/AoT_Chicago.complete.latest.tar"
tar -xf AoT_Chicago.complete.latest.tar

# 2. Extract a diverse slice to JSON (500K rows → ~130 MB)
cd d:\personal\soam
python tests/aot/extract_aot_data.py `
  --input "data/AoT_Chicago.complete.2022-08-31/data.csv.gz" `
  --output "tests/aot/data" `
  --max-rows 500000

# 3. Run with extracted sample (fits ConfigMap < 1MB)
.\tests\aot\run-aot-test.ps1 -DataFile tests\aot\data\sample.json -Rate 200
```

### Runner script options (`run-aot-test.ps1`)

```powershell
.\tests\aot\run-aot-test.ps1
  [-Pods <int>]            # Parallel pods (default: 2)
  [-Rate <int>]            # Messages per second per pod (default: 100)
  [-Duration <int>]        # Test duration in seconds (default: 300)
  [-Threads <int>]         # Publisher threads per pod (default: 5)
  [-DataFile <string>]     # JSON data file (default: aot_slice.json)
  [-Namespace <string>]    # K8s namespace (default: soam)
  [-Local]                 # Use localhost:5000 registry
```

### Perf test script options (`perf_test_aot.py`)

```powershell
python tests/aot/perf_test_aot.py
  --rate <int>             # Target messages per second (default: 100)
  --duration <int>         # Test duration in seconds (default: 60)
  --broker <string>        # MQTT broker hostname (default: mosquitto)
  --port <int>             # MQTT broker port (default: 1883)
  --threads <int>          # Override auto-calculated thread count
  --data <path>            # Path to JSON file or directory (required)
```

### Extraction script options (`extract_aot_data.py`)

```powershell
python tests/aot/extract_aot_data.py
  --input <path>           # Path to data.csv.gz
  --output <dir>           # Output directory (default: tests/aot/data)
  --max-rows <int>         # Max sensing rows to extract (default: 500000)
```

## What to verify after running

1. **Schema inference** — Check that the pipeline discovered all sensor types:
   ```powershell
   # Port-forward backend
   kubectl port-forward svc/backend 8000:8000 -n soam
   # Check stream status
   curl http://localhost:8000/api/schema/stream/status
   ```

2. **Data in MinIO** — Verify bronze-layer files were created for each topic:
   ```
   smartcity_sensors_aot_meteorology/
   smartcity_sensors_aot_chemistry/
   smartcity_sensors_aot_light/
   ```

3. **Normalization** — The 8+ temperature sensors should be mappable to a
   canonical `temperature` field via normalization rules.

## Comparison with perf test (`tests/perf`)

| Aspect | `tests/perf` | `tests/aot` |
|--------|-------------|-------------|
| **Data** | Synthetic (random temp/humidity) | Real AoT Chicago sensors |
| **Topics** | 1 (`smartcity/sensors/perf_test`) | 3 (`aot_meteorology`, `aot_chemistry`, `aot_light`) |
| **Sensors** | 1 type | 29 sensor types across 3 subsystems |
| **Schema** | Fixed fields | Heterogeneous (mixed types, NA values, varying units) |
| **Purpose** | Max throughput testing | Throughput + real heterogeneity validation |
| **Runner** | `run-perf-test.ps1` | `run-aot-test.ps1` |
| **Script** | `perf_test_mqtt.py` | `perf_test_aot.py` |

## File structure

```
tests/aot/
├── README.md               # This file
├── perf_test_aot.py        # Perf test script (rate-limited, multi-threaded)
├── extract_aot_data.py     # CSV → JSON extraction script
├── aot-replay-job.yaml     # K8s Job manifest
├── run-aot-test.ps1        # Cluster test runner (like run-perf-test.ps1)
└── data/
    ├── .gitignore           # Ignores large generated files
    ├── aot_slice.json       # 1,500-message slice (Git LFS) ← committed
    ├── sample.json          # 3,000-message sample (generated)
    ├── metsense.json        # Full extraction (generated, gitignored)
    ├── chemsense.json       # Full extraction (generated, gitignored)
    └── lightsense.json      # Full extraction (generated, gitignored)
```
