"""
Enhanced diagnostics for debugging enrichment filtering issues.
"""
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import sessionmaker
from src.database.database import engine
from src.database.models import Device
from .session import SparkSessionManager
from pyspark.sql import functions as F

logger = logging.getLogger(__name__)


def diagnose_enrichment_filtering(spark_manager: SparkSessionManager, enriched_path: str) -> Dict[str, Any]:
    """Diagnose why enrichment filtering isn't working as expected.
    
    Returns detailed information about:
    - Registered devices
    - Actual ingestion_id values in enriched data
    - Sensor data breakdown
    """
    result = {
        "registered_devices": [],
        "enriched_data_ingestion_ids": [],
        "enriched_sensors_by_ingestion_id": {},
        "total_enriched_sensors": 0,
        "potential_issues": []
    }
    
    # 1. Check registered devices
    try:
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        try:
            devices = db.query(Device).filter(Device.enabled == True).all()
            result["registered_devices"] = [
                {
                    "id": d.id,
                    "ingestion_id": d.ingestion_id,
                    "name": d.name,
                    "enabled": d.enabled,
                    "is_wildcard": d.ingestion_id is None
                }
                for d in devices
            ]
        finally:
            db.close()
    except Exception as e:
        result["potential_issues"].append(f"Failed to load registered devices: {e}")
    
    # 2. Check enriched data
    try:
        if spark_manager.is_connected():
            df = (
                spark_manager.spark.read.format("delta")
                .load(enriched_path)
            )
            
            # Get all ingestion_id values in enriched data
            if "ingestion_id" in df.columns:
                ingestion_ids = [r[0] for r in df.select("ingestion_id").distinct().collect()]
                result["enriched_data_ingestion_ids"] = ingestion_ids
                
                # Get sensors grouped by ingestion_id
                for iid in ingestion_ids:
                    # Extract sensorId from sensor_data map (union schema)
                    sensor_df = (
                        df.filter(df.ingestion_id == iid)
                        .select(
                            F.coalesce(
                                df.sensor_data.getItem("sensorId"),
                                df.sensor_data.getItem("sensorid"),
                                df.sensor_data.getItem("sensor_id"),
                                F.lit("unknown")
                            ).alias("sensorId")
                        )
                        .filter(F.col("sensorId").isNotNull() & (F.col("sensorId") != "unknown"))
                        .distinct()
                    )
                    sensors = [r[0] for r in sensor_df.collect()]
                    result["enriched_sensors_by_ingestion_id"][str(iid)] = sensors
                
                # Total unique sensors - extract from sensor_data map
                total_sensors_df = (
                    df.select(
                        F.coalesce(
                            df.sensor_data.getItem("sensorId"),
                            df.sensor_data.getItem("sensorid"), 
                            df.sensor_data.getItem("sensor_id"),
                            F.lit("unknown")
                        ).alias("sensorId")
                    )
                    .filter(F.col("sensorId").isNotNull() & (F.col("sensorId") != "unknown"))
                    .distinct()
                )
                total_sensors = total_sensors_df.count()
                result["total_enriched_sensors"] = total_sensors
            else:
                result["potential_issues"].append("No 'ingestion_id' column found in enriched data")
                
    except Exception as e:
        result["potential_issues"].append(f"Failed to read enriched data: {e}")
    
    # 3. Analyze potential issues
    registered_ids = [d["ingestion_id"] for d in result["registered_devices"] if not d["is_wildcard"]]
    has_wildcard = any(d["is_wildcard"] for d in result["registered_devices"])
    
    if has_wildcard:
        result["potential_issues"].append("WARNING: Wildcard device registration found (ingestion_id=None) - this accepts ALL sensors")
    
    if registered_ids and result["enriched_data_ingestion_ids"]:
        # Check for mismatches
        enriched_ids = set(result["enriched_data_ingestion_ids"])
        registered_ids_set = set(str(rid) for rid in registered_ids if rid is not None)
        
        unregistered_in_data = enriched_ids - registered_ids_set
        if unregistered_in_data:
            result["potential_issues"].append(f"Found unregistered ingestion_ids in enriched data: {list(unregistered_in_data)}")
            
        registered_not_in_data = registered_ids_set - enriched_ids
        if registered_not_in_data:
            result["potential_issues"].append(f"Registered ingestion_ids not found in data: {list(registered_not_in_data)}")
    
    # 4. Check for multiple sensors per ingestion_id (potential issue)
    for ingestion_id, sensors in result["enriched_sensors_by_ingestion_id"].items():
        if len(sensors) > 1:
            result["potential_issues"].append(
                f"ISSUE: Multiple sensors ({len(sensors)}) found under single ingestion_id '{ingestion_id}': {sensors}. "
                f"This suggests that multiple distinct sensors are being published with the same ingestion_id, "
                f"which may not be the intended behavior if you want to filter sensors individually."
            )
    
    # 5. Check if registered devices count doesn't match unique sensors
    total_registered = len([d for d in result["registered_devices"] if d["enabled"]])
    total_sensors = result["total_enriched_sensors"]
    if total_registered < total_sensors and not has_wildcard:
        result["potential_issues"].append(
            f"MISMATCH: {total_registered} registered devices but {total_sensors} unique sensors being processed. "
            f"Either register more devices for individual sensors, or configure data ingestion to use different ingestion_ids per sensor type."
        )
    
    return result


def print_enrichment_diagnosis(spark_manager: SparkSessionManager, enriched_path: str):
    """Print a human-readable diagnosis of enrichment filtering."""
    diagnosis = diagnose_enrichment_filtering(spark_manager, enriched_path)
    
    print("=== ENRICHMENT FILTERING DIAGNOSIS ===")
    print()
    
    print("REGISTERED DEVICES:")
    for device in diagnosis["registered_devices"]:
        wildcard_note = " (WILDCARD - accepts all sensors)" if device["is_wildcard"] else ""
        print(f"  - ID: {device['id']}, Ingestion ID: {device['ingestion_id']}, Name: {device['name']}{wildcard_note}")
    print()
    
    print("INGESTION IDs IN ENRICHED DATA:")
    for iid in diagnosis["enriched_data_ingestion_ids"]:
        sensors = diagnosis["enriched_sensors_by_ingestion_id"].get(str(iid), [])
        print(f"  - {iid}: {len(sensors)} sensors {sensors[:3]}{'...' if len(sensors) > 3 else ''}")
    print()
    
    print(f"TOTAL UNIQUE SENSORS IN ENRICHED DATA: {diagnosis['total_enriched_sensors']}")
    print()
    
    if diagnosis["potential_issues"]:
        print("POTENTIAL ISSUES:")
        for issue in diagnosis["potential_issues"]:
            print(f"  ⚠️  {issue}")
    else:
        print("✅ No obvious issues detected")
    
    print()
    print("=== END DIAGNOSIS ===")
    
    return diagnosis
