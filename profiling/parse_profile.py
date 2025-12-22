"""Parse scalene profile and extract CPU + I/O hotspots in your code."""
import json
import sys

profile_file = sys.argv[1] if len(sys.argv) > 1 else 'scalene-profile.json'
min_pct = float(sys.argv[2]) if len(sys.argv) > 2 else 0.01  # Default threshold

with open(profile_file) as f:
    data = json.load(f)

hotspots = []
for filepath, filedata in data.get('files', {}).items():
    # Only our code
    if '/app/src/' not in filepath:
        continue
    for line in filedata.get('lines', []):
        cpu_python = line.get('n_cpu_percent_python', 0)
        cpu_c = line.get('n_cpu_percent_c', 0)
        sys_pct = line.get('n_sys_percent', 0)  # I/O wait time
        total = cpu_python + cpu_c + sys_pct
        
        if total > min_pct:
            hotspots.append({
                'file': filepath.replace('/app/src/', ''),
                'line': line.get('lineno'),
                'cpu_py': round(cpu_python, 2),
                'cpu_c': round(cpu_c, 2),
                'io_wait': round(sys_pct, 2),
                'total': round(total, 2),
                'code': line.get('line', '').strip()[:60]
            })

# Sort by I/O wait time (where app waits for data)
hotspots.sort(key=lambda x: x['io_wait'], reverse=True)

print(f"Hotspots in your code (>{min_pct}% total time):")
print(f"Total: {len(hotspots)} lines\n")
print(f"{'IO Wait':>8}  {'CPU(Py)':>8}  {'CPU(C)':>8}  {'Total':>8}  {'Location':<40}  Code")
print("-" * 140)
for h in hotspots:
    loc = f"{h['file']}:{h['line']}"
    print(f"{h['io_wait']:7.2f}%  {h['cpu_py']:7.2f}%  {h['cpu_c']:7.2f}%  {h['total']:7.2f}%  {loc:<40}  {h['code']}")

# Summary
print("\n" + "=" * 80)
total_io = sum(h['io_wait'] for h in hotspots)
total_cpu = sum(h['cpu_py'] + h['cpu_c'] for h in hotspots)
print(f"Summary: I/O Wait: {total_io:.2f}%  |  CPU: {total_cpu:.2f}%")
print("High I/O Wait = code waiting on network/disk (Spark, MinIO, DB)")
print("High CPU(C) = native code (Spark JVM bridge, serialization)")
