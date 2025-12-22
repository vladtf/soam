# Profiling SOAM Backend with Scalene

This guide explains how to profile the SOAM backend application using Scalene to identify performance bottlenecks.

## Overview

Scalene is a high-precision CPU, memory, and I/O profiler for Python. It separates:
- **CPU (Python)**: Time spent in Python code
- **CPU (C)**: Time spent in native/C extensions (e.g., Spark JVM bridge)
- **I/O Wait (System)**: Time waiting on network, disk, or other syscalls

## Prerequisites

Scalene is already included in the backend `Pipfile`:
```toml
[packages]
scalene = "*"
```

A wrapper script `run_server.py` exists in the backend folder for Scalene compatibility.

## Enabling Profiling

### 1. Update Kubernetes Config

Edit `k8s/backend.yaml` to use Scalene instead of direct uvicorn:

```yaml
# Scalene profiling - full profile including I/O wait time
command: ["/bin/sh", "-c"]
args: ["scalene run --profile-interval 60 -o /app/scalene-profile.json run_server.py"]
```

**Options explained:**
- `--profile-interval 60`: Write profile every 60 seconds (required for long-running servers)
- `-o /app/scalene-profile.json`: Output file path
- `--cpu-only`: Add this flag if you only want CPU profiling (faster, smaller output)

### 2. Restart the Backend

If using Skaffold, it will auto-detect the change:
```powershell
# Skaffold will redeploy automatically
# Or force restart:
kubectl delete pod backend-0
```

### 3. Generate Load

Make requests to the endpoints you want to profile:
```powershell
# Single request
Invoke-RestMethod http://localhost:8000/api/spark/average-temperature

# Multiple requests
1..10 | ForEach-Object { Invoke-RestMethod http://localhost:8000/api/spark/average-temperature }
```

### 4. Wait for Profile Update

Scalene writes the profile every 60 seconds (configurable via `--profile-interval`).

## Viewing Results

### Option 1: Parse with Custom Script (Recommended for Your Code Only)

```powershell
# Copy profile from pod
kubectl cp backend-0:/app/scalene-profile.json ./profiling/scalene-profile.json

# Parse and show hotspots (threshold: 0.01%)
python profiling/parse_profile.py profiling/scalene-profile.json 0.01
```

Output columns:
- **IO Wait**: Time waiting for data (network, disk, Spark)
- **CPU(Py)**: Python computation time
- **CPU(C)**: Native code time (JVM bridge, serialization)
- **Total**: Combined time
- **Location**: File and line number
- **Code**: The actual code line

### Option 2: Scalene CLI View

```powershell
# Copy profile locally
kubectl cp backend-0:/app/scalene-profile.json ./scalene-profile.json

# View in terminal
scalene view --cli scalene-profile.json

# View in browser (interactive)
scalene view scalene-profile.json
```

### Option 3: Speedscope (Interactive Flame Graph)

```powershell
# Copy profile
kubectl cp backend-0:/app/scalene-profile.json ./scalene-profile.json

# Open speedscope in browser
Start-Process "https://speedscope.app"
# Then drag scalene-profile.json into the browser
```

### Option 4: View Inside Pod

```powershell
kubectl exec -it backend-0 -- scalene view --cli /app/scalene-profile.json
```

## Interpreting Results

### High I/O Wait Time
- **Cause**: Code waiting on external resources (Spark, MinIO, database, network)
- **Solution**: Add caching, reduce data fetched, optimize queries

### High CPU (C) Time
- **Cause**: Native code execution (Spark JVM bridge, data serialization)
- **Solution**: Reduce data transfer between Python and Spark, batch operations

### High CPU (Python) Time
- **Cause**: Python computation
- **Solution**: Optimize algorithms, use vectorized operations, consider Cython

### Example Output

```
Hotspots in your code (>0.01% total time):
Total: 4 lines

 IO Wait   CPU(Py)    CPU(C)     Total  Location                                  Code
----------------------------------------------------------------------------------------------------------------------------------------
  40.16%     0.00%     3.68%    43.84%  spark/enrichment/usage_tracker.py:40      while not cls._stop_event.wait(timeout=cls._flush_interval_s
   2.71%     0.00%     0.33%     3.05%  spark/data_access.py:78                   rows = df.collect()
   2.38%     0.00%     0.28%     2.65%  spark/enrichment/batch_processor.py:126   .save()
   1.66%     0.00%     0.21%     1.88%  spark/data_access.py:182                  return [row.asDict() for row in df.collect()]

================================================================================
Summary: I/O Wait: 44.56%  |  CPU: 4.30%
High I/O Wait = code waiting on network/disk (Spark, MinIO, DB)
High CPU(C) = native code (Spark JVM bridge, serialization)
```

## Disabling Profiling

To return to normal operation, comment out or remove the scalene command in `k8s/backend.yaml`:

```yaml
# Normal operation (no profiling)
# command: ["/bin/sh", "-c"]
# args: ["scalene run --profile-interval 60 -o /app/scalene-profile.json run_server.py"]
```

The default CMD from the Dockerfile will be used:
```dockerfile
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Important Notes

1. **Performance Overhead**: Scalene adds ~10-20% overhead. Don't use in production.

2. **Profile File Size**: The JSON can be large (64MB+). Use `--cpu-only` for smaller files.

3. **Background Threads**: Scalene profiles all threads. Background workers like `usage_tracker.py` will appear but don't affect API latency.

4. **Spark/JVM Time**: Most Spark operations happen in the JVM, not Python. High latency with low Python CPU indicates Spark/network bottlenecks.

5. **Caching**: The `data_access.py` has built-in caching (10s TTL). First request is slow, subsequent requests are fast.

## Alternative Profilers

| Profiler | Attach to Running | Filter by Path | I/O Tracking |
|----------|-------------------|----------------|--------------|
| Scalene  | No                | Yes (parse)    | Yes          |
| py-spy   | Yes               | No (manual)    | No           |
| cProfile | No                | Yes            | No           |
| Austin   | Yes               | No             | No           |

For attaching to running processes without restart, use py-spy:
```powershell
kubectl exec -it backend-0 -- pip install py-spy
kubectl exec -it backend-0 -- py-spy top --pid 1
```

## Quick Reference

```powershell
# One-liner: Copy and analyze profile
kubectl cp backend-0:/app/scalene-profile.json ./profiling/scalene-profile.json; python profiling/parse_profile.py profiling/scalene-profile.json 0.01
```
