#!/usr/bin/env python3
"""
Extract a diverse slice from the AoT Chicago complete dataset and convert to JSON files.

Reads the compressed CSV and produces per-subsystem JSON files suitable for
replay through the MQTT simulator. Only keeps environmental sensing subsystems
(metsense, chemsense, lightsense, alphasense, plantower, audio) and skips
system telemetry (wagman, ep, nc, image).

Usage:
    python tests/aot/extract_aot_data.py --input data/AoT_Chicago.complete.2022-08-31/data.csv.gz --output tests/aot/data --max-rows 500000
    python tests/aot/extract_aot_data.py --input data/AoT_Chicago.complete.2022-08-31/data.csv.gz --output tests/aot/data --max-rows 2000000

The output directory will contain one JSON file per subsystem, e.g.:
    tests/aot/data/metsense.json
    tests/aot/data/chemsense.json
    tests/aot/data/lightsense.json
"""
import argparse
import csv
import gzip
import json
import os
import sys
from collections import defaultdict


# Only keep environmental sensing subsystems — skip system telemetry
SENSING_SUBSYSTEMS = {"metsense", "chemsense", "lightsense", "alphasense", "plantower", "audio"}

# Map parameter to MQTT topic (one topic per measurement type)
# This ensures each topic carries a single type of reading so normalization
# rules can correctly map "value" → the canonical field name.
PARAMETER_TOPICS = {
    "temperature": "smartcity/sensors/aot_temperature",
    "humidity": "smartcity/sensors/aot_humidity",
    "pressure": "smartcity/sensors/aot_pressure",
    "concentration": "smartcity/sensors/aot_air_quality",
    "intensity": "smartcity/sensors/aot_light",
    "ir_intensity": "smartcity/sensors/aot_light",
    "uv_intensity": "smartcity/sensors/aot_light",
    "visible_light_intensity": "smartcity/sensors/aot_light",
    "magnetic_field_x": "smartcity/sensors/aot_magnetic",
    "magnetic_field_y": "smartcity/sensors/aot_magnetic",
    "magnetic_field_z": "smartcity/sensors/aot_magnetic",
    "pm1": "smartcity/sensors/aot_particulates",
    "pm2_5": "smartcity/sensors/aot_particulates",
    "pm10": "smartcity/sensors/aot_particulates",
    "pm1_atm": "smartcity/sensors/aot_particulates",
    "pm25_atm": "smartcity/sensors/aot_particulates",
    "pm10_atm": "smartcity/sensors/aot_particulates",
    "bins": "smartcity/sensors/aot_particulates",
    "acceleration_x": "smartcity/sensors/aot_vibration",
    "acceleration_y": "smartcity/sensors/aot_vibration",
    "acceleration_z": "smartcity/sensors/aot_vibration",
}

# Unit lookup from sensors.csv (subsystem/sensor/parameter -> unit)
UNIT_MAP = {
    ("metsense", "bmp180", "temperature"): "C",
    ("metsense", "htu21d", "temperature"): "C",
    ("metsense", "pr103j2", "temperature"): "C",
    ("metsense", "tmp112", "temperature"): "C",
    ("metsense", "tsys01", "temperature"): "C",
    ("metsense", "bmp180", "pressure"): "hPa",
    ("metsense", "hih4030", "humidity"): "RH",
    ("metsense", "htu21d", "humidity"): "RH",
    ("metsense", "spv1840lr5h_b", "intensity"): "dB",
    ("metsense", "tsl250rd", "intensity"): "uW/cm^2",
    ("metsense", "mma8452q", "acceleration_x"): "mg",
    ("metsense", "mma8452q", "acceleration_y"): "mg",
    ("metsense", "mma8452q", "acceleration_z"): "mg",
    ("chemsense", "co", "concentration"): "ppm",
    ("chemsense", "h2s", "concentration"): "ppm",
    ("chemsense", "no2", "concentration"): "ppm",
    ("chemsense", "o3", "concentration"): "ppm",
    ("chemsense", "so2", "concentration"): "ppm",
    ("chemsense", "oxidizing_gases", "concentration"): "ppm",
    ("chemsense", "reducing_gases", "concentration"): "ppm",
    ("chemsense", "lps25h", "pressure"): "hPa",
    ("chemsense", "lps25h", "temperature"): "C",
    ("chemsense", "sht25", "humidity"): "RH",
    ("chemsense", "sht25", "temperature"): "C",
    ("chemsense", "at0", "temperature"): "C",
    ("chemsense", "at1", "temperature"): "C",
    ("chemsense", "at2", "temperature"): "C",
    ("chemsense", "at3", "temperature"): "C",
    ("chemsense", "si1145", "ir_intensity"): "uW/cm^2",
    ("chemsense", "si1145", "uv_intensity"): "uW/cm^2",
    ("chemsense", "si1145", "visible_light_intensity"): "uW/cm^2",
    ("lightsense", "apds_9006_020", "intensity"): "lux",
    ("lightsense", "mlx75305", "intensity"): "uW/cm^2",
    ("lightsense", "tsl250rd", "intensity"): "uW/cm^2",
    ("lightsense", "tsl260rd", "intensity"): "uW/cm^2",
    ("lightsense", "ml8511", "intensity"): "uW/cm^2",
    ("lightsense", "hih6130", "humidity"): "RH",
    ("lightsense", "hih6130", "temperature"): "C",
    ("lightsense", "tmp421", "temperature"): "C",
    ("lightsense", "hmc5883l", "magnetic_field_x"): "mG",
    ("lightsense", "hmc5883l", "magnetic_field_y"): "mG",
    ("lightsense", "hmc5883l", "magnetic_field_z"): "mG",
    ("alphasense", "opc_n2", "pm1"): "ug/m^3",
    ("alphasense", "opc_n2", "pm2_5"): "ug/m^3",
    ("alphasense", "opc_n2", "pm10"): "ug/m^3",
    ("alphasense", "opc_n2", "bins"): "counts",
    ("plantower", "pms7003", "pm1_atm"): "ug/m^3",
    ("plantower", "pms7003", "pm25_atm"): "ug/m^3",
    ("plantower", "pms7003", "pm10_atm"): "ug/m^3",
}


def parse_value(val: str):
    """Parse a CSV value: NA -> None, integers, floats, or strings."""
    if val == "NA":
        return None
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def convert_timestamp(ts: str) -> str:
    """Convert AoT timestamp format '2018/01/01 00:00:06' to ISO 8601."""
    return ts.replace("/", "-") + "Z"


def row_to_json(row: dict) -> dict:
    """Convert a CSV row to the JSON payload format expected by SOAM ingestor."""
    subsystem = row["subsystem"]
    sensor = row["sensor"]
    parameter = row["parameter"]
    node_id = row["node_id"]

    value_raw = parse_value(row["value_raw"])
    value_hrf = parse_value(row["value_hrf"])

    # Use the human-readable value if available, otherwise raw
    value = value_hrf if value_hrf is not None else value_raw

    unit = UNIT_MAP.get((subsystem, sensor, parameter), "")

    payload = {
        "sensor_id": f"aot_{node_id}_{sensor}",
        "timestamp": convert_timestamp(row["timestamp"]),
        "node_id": node_id,
        "subsystem": subsystem,
        "sensor": sensor,
        "parameter": parameter,
        # Name the value field after the parameter (e.g., "temperature", "humidity")
        # so that existing global normalization rules pick it up automatically.
        # This avoids the ambiguity of a generic "value" field that means different
        # things for different sensor types.
        parameter: value,
        "unit": unit,
    }

    # Include both raw and hrf when both are available (for schema inference testing)
    if value_raw is not None:
        payload["value_raw"] = value_raw
    if value_hrf is not None:
        payload["value_hrf"] = value_hrf

    return payload


def extract(input_path: str, output_dir: str, max_rows: int) -> dict:
    """Extract rows from compressed CSV and write per-parameter JSON files."""
    os.makedirs(output_dir, exist_ok=True)

    data_by_param = defaultdict(list)
    stats = defaultdict(lambda: {"rows": 0, "sensors": set(), "subsystems": set(), "nodes": set()})
    skipped = 0
    total = 0

    print(f"📂 Reading: {input_path}")
    print(f"📊 Max rows: {max_rows:,}")

    with gzip.open(input_path, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            subsystem = row["subsystem"]
            parameter = row["parameter"]

            if subsystem not in SENSING_SUBSYSTEMS:
                skipped += 1
                continue

            # Skip ID rows (not sensor data)
            if parameter == "id":
                skipped += 1
                continue

            # Get topic for this parameter
            topic = PARAMETER_TOPICS.get(parameter)
            if not topic:
                topic = f"smartcity/sensors/aot_{parameter}"

            payload = row_to_json(row)
            # Derive a canonical topic key for grouping output files
            topic_key = topic.rsplit("/", 1)[-1]  # e.g. "aot_temperature"
            data_by_param[topic_key].append({"topic": topic, "payload": payload})

            s = stats[topic_key]
            s["rows"] += 1
            s["sensors"].add(row["sensor"])
            s["subsystems"].add(subsystem)
            s["nodes"].add(row["node_id"])

            if sum(s["rows"] for s in stats.values()) >= max_rows:
                break

            if total % 500_000 == 0:
                kept = sum(s["rows"] for s in stats.values())
                print(f"  Scanned {total:,} rows, kept {kept:,}...")

    # Write per-parameter JSON files
    print(f"\n💾 Writing JSON files to {output_dir}/")
    for topic_key, messages in sorted(data_by_param.items()):
        out_path = os.path.join(output_dir, f"{topic_key}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(messages, f, separators=(",", ":"))
        size_mb = os.path.getsize(out_path) / (1024 * 1024)
        print(f"  ✅ {topic_key}.json: {len(messages):,} messages ({size_mb:.1f} MB)")

    # Also write a combined smaller sample for quick tests
    sample_messages = []
    for topic_key, messages in sorted(data_by_param.items()):
        sample_messages.extend(messages[:500])
    sample_path = os.path.join(output_dir, "sample.json")
    with open(sample_path, "w", encoding="utf-8") as f:
        json.dump(sample_messages, f, separators=(",", ":"))
    print(f"  ✅ sample.json: {len(sample_messages):,} messages (quick test)")

    # Print summary
    print(f"\n{'='*60}")
    print(f"📊 Extraction Summary")
    print(f"{'='*60}")
    print(f"  Total CSV rows scanned: {total:,}")
    print(f"  Rows skipped (system/id): {skipped:,}")
    print(f"  Rows extracted: {sum(s['rows'] for s in stats.values()):,}")
    print(f"  Topics (output files): {len(stats)}")
    print(f"{'='*60}")

    for key in sorted(stats.keys()):
        s = stats[key]
        print(f"\n  [{key}]")
        print(f"    Rows: {s['rows']:,}")
        print(f"    Sensors: {', '.join(sorted(s['sensors']))}")
        print(f"    Subsystems: {', '.join(sorted(s['subsystems']))}")
        print(f"    Nodes: {len(s['nodes'])}")

    return dict(stats)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract AoT data to JSON for MQTT replay")
    parser.add_argument("--input", required=True, help="Path to data.csv.gz")
    parser.add_argument("--output", default="tests/aot/data", help="Output directory for JSON files")
    parser.add_argument("--max-rows", type=int, default=500_000, help="Max sensing rows to extract")
    args = parser.parse_args()

    extract(args.input, args.output, args.max_rows)
