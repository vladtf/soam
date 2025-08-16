"""
Data troubleshooting utilities for diagnosing data transformation issues.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pyspark.sql import DataFrame, functions as F
from pyspark.sql.types import StructType

from .session import SparkSessionManager
from .cleaner import DataCleaner
from .union_schema import UnionSchemaTransformer

logger = logging.getLogger(__name__)


class DataTroubleshooter:
    """Diagnose data transformation issues across the pipeline."""

    def __init__(self, session_manager: SparkSessionManager, minio_bucket: str):
        self.session_manager = session_manager
        self.minio_bucket = minio_bucket
        
        # Build paths
        self.sensors_path = f"s3a://{minio_bucket}/sensors"
        self.enriched_path = f"s3a://{minio_bucket}/enriched"
        self.silver_path = f"s3a://{minio_bucket}/silver"

    def diagnose_field_transformation(
        self, 
        sensor_id: str, 
        field_name: str, 
        minutes_back: int = 30,
        ingestion_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Diagnose why a specific field (like temperature) becomes null during transformation.
        
        Args:
            sensor_id: The sensor ID to investigate
            field_name: The field name to track (e.g., "temperature")
            minutes_back: How many minutes back to look
            ingestion_id: Optional ingestion ID filter
            
        Returns:
            Dict with detailed analysis of the field transformation
        """
        logger.info(f"Diagnosing field '{field_name}' for sensor '{sensor_id}'")
        
        result = {
            "sensor_id": sensor_id,
            "field_name": field_name,
            "minutes_back": minutes_back,
            "ingestion_id": ingestion_id,
            "timestamp": datetime.now().isoformat(),
            "raw_data_analysis": {},
            "normalization_analysis": {},
            "enrichment_analysis": {},
            "silver_analysis": {},
            "recommendations": []
        }

        try:
            # Step 1: Analyze raw data
            result["raw_data_analysis"] = self._analyze_raw_data(
                sensor_id, field_name, minutes_back, ingestion_id
            )
            
            # Step 2: Analyze normalization step
            result["normalization_analysis"] = self._analyze_normalization(
                sensor_id, field_name, minutes_back, ingestion_id
            )
            
            # Step 3: Analyze enrichment step  
            result["enrichment_analysis"] = self._analyze_enrichment(
                sensor_id, field_name, minutes_back, ingestion_id
            )
            
            # Step 4: Analyze silver layer
            result["silver_analysis"] = self._analyze_silver_layer(
                sensor_id, field_name, minutes_back
            )
            
            # Step 5: Generate recommendations
            result["recommendations"] = self._generate_recommendations(result)
            
            result["status"] = "success"
            
        except Exception as e:
            logger.error(f"Error in field transformation diagnosis: {e}")
            result["status"] = "error"
            result["error"] = str(e)
            
        return result

    def _analyze_raw_data(
        self, 
        sensor_id: str, 
        field_name: str, 
        minutes_back: int,
        ingestion_id: Optional[str]
    ) -> Dict[str, Any]:
        """Analyze raw sensor data in MinIO."""
        analysis = {
            "found_data": False,
            "record_count": 0,
            "field_variants_found": [],
            "field_values_sample": [],
            "schema_info": {},
            "time_range": {}
        }
        
        try:
            spark = self.session_manager.spark
            time_filter = F.current_timestamp() - F.expr(f"INTERVAL {minutes_back} MINUTES")
            
            # Read raw data
            base_query = spark.read.option("basePath", self.sensors_path)
            
            if ingestion_id:
                raw_df = base_query.parquet(f"{self.sensors_path}/ingestion_id={ingestion_id}/date=*/hour=*")
            else:
                raw_df = base_query.parquet(f"{self.sensors_path}/ingestion_id=*/date=*/hour=*")
            
            # Remove duplicate ingestion_id column if it exists in both partition and data
            columns_to_select = [col for col in raw_df.columns if col != "ingestion_id" or raw_df.columns.count("ingestion_id") == 1]
            if len(columns_to_select) < len(raw_df.columns):
                raw_df = raw_df.select(*columns_to_select)
            
            # Filter by time and sensor
            # Handle both possible sensor ID column names
            sensor_filter = F.col("timestamp") >= time_filter
            
            # Check which sensor ID column exists and create appropriate filter
            columns = raw_df.columns
            if "sensor_id" in columns:
                sensor_filter = sensor_filter & (F.col("sensor_id") == sensor_id)
            elif "sensorId" in columns:
                sensor_filter = sensor_filter & (F.col("sensorId") == sensor_id)
            else:
                # Try both in case of mixed schemas
                try:
                    sensor_filter = sensor_filter & (
                        (F.col("sensor_id") == sensor_id) | (F.col("sensorId") == sensor_id)
                    )
                except Exception:
                    # If neither column exists, just use timestamp filter
                    pass
            
            filtered_df = raw_df.filter(sensor_filter)
            
            if not filtered_df.rdd.isEmpty():
                analysis["found_data"] = True
                analysis["record_count"] = filtered_df.count()
                
                # Find field variants (case variations, underscores, etc.)
                all_columns = filtered_df.columns
                field_variants = []
                
                # Look for exact matches and partial matches
                for col in all_columns:
                    if field_name.lower() in col.lower():
                        field_variants.append(col)  # Use original column name, not lowercase
                
                analysis["field_variants_found"] = field_variants
                
                # Debug logging
                logger.info(f"Field search: looking for '{field_name}' in columns: {all_columns}")
                logger.info(f"Field variants found: {field_variants}")
                
                # Get schema information
                analysis["schema_info"] = {
                    "total_columns": len(filtered_df.columns),
                    "column_names": filtered_df.columns,
                    "column_types": {f.name: str(f.dataType) for f in filtered_df.schema.fields}
                }
                
                # Sample field values for each variant
                for variant in field_variants:
                    if variant in filtered_df.columns:
                        sample_values = (
                            filtered_df.select(variant, "timestamp")
                            .filter(F.col(variant).isNotNull())
                            .orderBy(F.desc("timestamp"))
                            .limit(5)
                            .collect()
                        )
                        analysis["field_values_sample"].extend([
                            {
                                "field_variant": variant,
                                "value": row[variant],
                                "timestamp": str(row["timestamp"]),
                                "type": type(row[variant]).__name__
                            }
                            for row in sample_values
                        ])
                
                # Time range analysis
                time_stats = filtered_df.agg(
                    F.min("timestamp").alias("earliest"),
                    F.max("timestamp").alias("latest")
                ).collect()[0]
                
                analysis["time_range"] = {
                    "earliest": str(time_stats["earliest"]),
                    "latest": str(time_stats["latest"])
                }
                
        except Exception as e:
            logger.error(f"Error analyzing raw data: {e}")
            analysis["error"] = str(e)
            
        return analysis

    def _analyze_normalization(
        self, 
        sensor_id: str, 
        field_name: str, 
        minutes_back: int,
        ingestion_id: Optional[str]
    ) -> Dict[str, Any]:
        """Analyze the normalization step."""
        analysis = {
            "normalization_rules": {},
            "field_mapping": {},
            "normalized_values": [],
            "transformation_applied": False
        }
        
        try:
            # Get normalization rules from DataCleaner
            cleaner = DataCleaner()
            rules = cleaner._load_dynamic_rules(ingestion_id)
            
            analysis["normalization_rules"] = dict(rules) if rules else {}
            
            # Check if our field is mapped
            field_lower = field_name.lower()
            mapped_fields = {}
            for raw_field, canonical in rules.items():
                if field_lower in raw_field.lower() or field_lower in canonical.lower():
                    mapped_fields[raw_field] = canonical
                    
            analysis["field_mapping"] = mapped_fields
            analysis["transformation_applied"] = len(mapped_fields) > 0
            
            # Test normalization on a sample
            if mapped_fields:
                spark = self.session_manager.spark
                time_filter = F.current_timestamp() - F.expr(f"INTERVAL {minutes_back} MINUTES")
                
                base_query = spark.read.option("basePath", self.sensors_path)
                if ingestion_id:
                    raw_df = base_query.parquet(f"{self.sensors_path}/ingestion_id={ingestion_id}/date=*/hour=*")
                else:
                    raw_df = base_query.parquet(f"{self.sensors_path}/ingestion_id=*/date=*/hour=*")
                
                # Handle sensor ID column variations and time filter
                columns = raw_df.columns
                time_filter_condition = F.col("timestamp") >= time_filter
                
                if "sensor_id" in columns:
                    sensor_filter_condition = F.col("sensor_id") == sensor_id
                elif "sensorId" in columns:
                    sensor_filter_condition = F.col("sensorId") == sensor_id
                else:
                    # If neither exists, skip sensor filtering for normalization test
                    sensor_filter_condition = F.lit(True)
                
                sample_df = raw_df.filter(time_filter_condition & sensor_filter_condition).limit(5)
                
                if not sample_df.rdd.isEmpty():
                    # Apply normalization
                    normalized_df = cleaner.normalize_sensor_columns(sample_df, ingestion_id)
                    
                    # Check field values before and after normalization
                    for raw_field, canonical in mapped_fields.items():
                        if raw_field in sample_df.columns and canonical in normalized_df.columns:
                            before_values = sample_df.select(raw_field).collect()
                            after_values = normalized_df.select(canonical).collect()
                            
                            analysis["normalized_values"].append({
                                "raw_field": raw_field,
                                "canonical_field": canonical,
                                "before_values": [str(row[raw_field]) for row in before_values],
                                "after_values": [str(row[canonical]) for row in after_values],
                                "values_match": [str(b[raw_field]) == str(a[canonical]) 
                                               for b, a in zip(before_values, after_values)]
                            })
                
        except Exception as e:
            logger.error(f"Error analyzing normalization: {e}")
            analysis["error"] = str(e)
            
        return analysis

    def _analyze_enrichment(
        self, 
        sensor_id: str, 
        field_name: str, 
        minutes_back: int,
        ingestion_id: Optional[str]
    ) -> Dict[str, Any]:
        """Analyze the enrichment step."""
        analysis = {
            "found_in_enriched": False,
            "record_count": 0,
            "field_in_sensor_data": False,
            "field_in_normalized_data": False,
            "union_schema_analysis": {},
            "device_registration_check": {}
        }
        
        try:
            spark = self.session_manager.spark
            time_filter = F.current_timestamp() - F.expr(f"INTERVAL {minutes_back} MINUTES")
            
            # Check if enriched path exists
            try:
                # Try to read enriched data
                enriched_df = (
                    spark.read.format("delta")
                    .load(self.enriched_path)
                    .filter(F.col("ingest_ts") >= time_filter)
                )
                
                # Filter by sensor ID (check both sensor_data and normalized_data)
                sensor_filter = (
                    F.col("sensor_data").getItem("sensorId").isin([sensor_id]) |
                    F.col("sensor_data").getItem("sensor_id").isin([sensor_id]) |
                    F.col("normalized_data").getItem("sensorId").isin([sensor_id])
                )
                
                if ingestion_id:
                    sensor_filter = sensor_filter & (F.col("ingestion_id") == ingestion_id)
                    
                filtered_enriched = enriched_df.filter(sensor_filter)
                
            except Exception as path_error:
                logger.warning(f"Enriched path not accessible: {path_error}")
                analysis["path_error"] = str(path_error)
                return analysis
            
            if not filtered_enriched.rdd.isEmpty():
                analysis["found_in_enriched"] = True
                analysis["record_count"] = filtered_enriched.count()
                
                # Check if field exists in sensor_data JSON
                sample_rows = filtered_enriched.limit(5).collect()
                
                sensor_data_fields = set()
                normalized_data_fields = set()
                field_values = []
                
                for row in sample_rows:
                    # Analyze sensor_data JSON
                    if row.sensor_data:
                        import json
                        try:
                            sensor_json = json.loads(row.sensor_data) if isinstance(row.sensor_data, str) else row.sensor_data
                            sensor_data_fields.update(sensor_json.keys())
                            
                            # Check if our field exists
                            field_variants = [k for k in sensor_json.keys() if field_name.lower() in k.lower()]
                            for variant in field_variants:
                                field_values.append({
                                    "source": "sensor_data",
                                    "field": variant,
                                    "value": sensor_json[variant],
                                    "timestamp": str(row.timestamp)
                                })
                        except Exception as e:
                            logger.warning(f"Failed to parse sensor_data JSON: {e}")
                    
                    # Analyze normalized_data
                    if row.normalized_data:
                        try:
                            norm_json = json.loads(row.normalized_data) if isinstance(row.normalized_data, str) else row.normalized_data
                            normalized_data_fields.update(norm_json.keys())
                            
                            field_variants = [k for k in norm_json.keys() if field_name.lower() in k.lower()]
                            for variant in field_variants:
                                field_values.append({
                                    "source": "normalized_data", 
                                    "field": variant,
                                    "value": norm_json[variant],
                                    "timestamp": str(row.timestamp)
                                })
                        except Exception as e:
                            logger.warning(f"Failed to parse normalized_data JSON: {e}")
                
                analysis["field_in_sensor_data"] = any(field_name.lower() in f.lower() for f in sensor_data_fields)
                analysis["field_in_normalized_data"] = any(field_name.lower() in f.lower() for f in normalized_data_fields)
                
                analysis["union_schema_analysis"] = {
                    "sensor_data_fields": list(sensor_data_fields),
                    "normalized_data_fields": list(normalized_data_fields),
                    "field_values_found": field_values
                }
            
            # Check device registration
            try:
                from sqlalchemy.orm import sessionmaker
                from src.database.database import engine
                from src.database.models import Device
                SessionLocal = sessionmaker(bind=engine)
                db_session = SessionLocal()
                
                try:
                    devices = db_session.query(Device).filter(Device.enabled == True).all()
                    
                    matching_devices = []
                    for device in devices:
                        if ingestion_id and device.ingestion_id == ingestion_id:
                            matching_devices.append({
                                "id": device.id,
                                "name": device.name,
                                "ingestion_id": device.ingestion_id,
                                "enabled": device.enabled
                            })
                        elif device.ingestion_id is None:  # Wildcard device
                            matching_devices.append({
                                "id": device.id,
                                "name": device.name,
                                "ingestion_id": "wildcard",
                                "enabled": device.enabled
                            })
                    
                    analysis["device_registration_check"] = {
                        "total_devices": len(devices),
                        "matching_devices": matching_devices,
                        "is_registered": len(matching_devices) > 0
                    }
                    
                finally:
                    db_session.close()
                    
            except Exception as e:
                logger.error(f"Error checking device registration: {e}")
                analysis["device_registration_check"]["error"] = str(e)
                
        except Exception as e:
            logger.error(f"Error analyzing enrichment: {e}")
            analysis["error"] = str(e)
            
        return analysis

    def _analyze_silver_layer(
        self, 
        sensor_id: str, 
        field_name: str, 
        minutes_back: int
    ) -> Dict[str, Any]:
        """Analyze the silver layer (aggregated data)."""
        analysis = {
            "found_in_silver": False,
            "record_count": 0,
            "aggregated_values": [],
            "field_aggregations": {}
        }
        
        try:
            spark = self.session_manager.spark
            time_filter = F.current_timestamp() - F.expr(f"INTERVAL {minutes_back} MINUTES")
            
            # Check if silver path exists
            try:
                # Read silver data
                silver_df = (
                    spark.read.format("delta")
                    .load(self.silver_path)
                    .filter(
                        (F.col("window_start") >= time_filter) &
                        (F.col("sensorId") == sensor_id)
                    )
                )
            except Exception as path_error:
                logger.warning(f"Silver path not accessible: {path_error}")
                analysis["path_error"] = str(path_error)
                return analysis
            
            if not silver_df.rdd.isEmpty():
                analysis["found_in_silver"] = True
                analysis["record_count"] = silver_df.count()
                
                # Look for aggregated field values
                silver_columns = silver_df.columns
                field_columns = [col for col in silver_columns if field_name.lower() in col.lower()]
                
                if field_columns:
                    sample_data = silver_df.select(["sensorId", "window_start"] + field_columns).limit(10).collect()
                    
                    analysis["aggregated_values"] = [
                        {
                            "sensorId": row.sensorId,
                            "window_start": str(row.window_start),
                            **{col: getattr(row, col) for col in field_columns}
                        }
                        for row in sample_data
                    ]
                
                # Get field statistics
                for col in field_columns:
                    try:
                        stats = silver_df.agg(
                            F.count(col).alias("count"),
                            F.countDistinct(col).alias("distinct_count"),
                            F.min(col).alias("min_val"),
                            F.max(col).alias("max_val"),
                            F.avg(col).alias("avg_val")
                        ).collect()[0]
                        
                        analysis["field_aggregations"][col] = {
                            "count": stats["count"],
                            "distinct_count": stats["distinct_count"],
                            "min_value": stats["min_val"],
                            "max_value": stats["max_val"],
                            "avg_value": stats["avg_val"]
                        }
                    except Exception as e:
                        logger.warning(f"Could not compute stats for {col}: {e}")
                        
        except Exception as e:
            logger.error(f"Error analyzing silver layer: {e}")
            analysis["error"] = str(e)
            
        return analysis

    def _generate_recommendations(self, analysis_result: Dict[str, Any]) -> List[str]:
        """Generate troubleshooting recommendations based on analysis."""
        recommendations = []
        
        raw_analysis = analysis_result.get("raw_data_analysis", {})
        norm_analysis = analysis_result.get("normalization_analysis", {})
        enrich_analysis = analysis_result.get("enrichment_analysis", {})
        silver_analysis = analysis_result.get("silver_analysis", {})
        
        # Raw data recommendations
        if not raw_analysis.get("found_data"):
            recommendations.append("❌ No raw data found for this sensor. Check if the sensor is actively sending data and MQTT ingestion is working.")
        elif not raw_analysis.get("field_variants_found"):
            # Data was found but field wasn't found - be more specific
            available_columns = raw_analysis.get("schema_info", {}).get("column_names", [])
            if available_columns:
                recommendations.append(f"⚠️ Field '{analysis_result['field_name']}' not found in raw data. Available columns: {', '.join(available_columns[:10])}{'...' if len(available_columns) > 10 else ''}")
            else:
                recommendations.append(f"⚠️ Field '{analysis_result['field_name']}' not found in raw data. Check the sensor's data format and field names.")
        else:
            field_variants = raw_analysis.get("field_variants_found", [])
            if len(field_variants) == 1 and field_variants[0].lower() == analysis_result['field_name'].lower():
                recommendations.append("✅ Raw data contains the field - data is reaching the system.")
            else:
                recommendations.append(f"✅ Raw data contains field variants: {', '.join(field_variants)} - data is reaching the system.")
        
        # Normalization recommendations
        if norm_analysis.get("transformation_applied"):
            if norm_analysis.get("field_mapping"):
                recommendations.append("✅ Normalization rules are mapping this field.")
            else:
                recommendations.append("⚠️ Normalization is active but may not be handling this field correctly.")
        else:
            recommendations.append("ℹ️ No normalization rules applied to this field. Consider adding mapping rules if field names vary.")
        
        # Enrichment recommendations
        if not enrich_analysis.get("found_in_enriched"):
            if enrich_analysis.get("path_error"):
                recommendations.append("❌ Enriched data layer not found. This may be normal if enrichment streaming hasn't started yet.")
            else:
                device_check = enrich_analysis.get("device_registration_check", {})
                if not device_check.get("is_registered"):
                    recommendations.append("❌ Sensor data not found in enriched layer. The device may not be registered or enabled.")
                else:
                    recommendations.append("❌ Device is registered but data not reaching enriched layer. Check streaming job status.")
        else:
            if enrich_analysis.get("field_in_sensor_data") and not enrich_analysis.get("field_in_normalized_data"):
                recommendations.append("⚠️ Field exists in raw sensor_data but missing from normalized_data. Check normalization rules.")
            elif enrich_analysis.get("field_in_normalized_data"):
                recommendations.append("✅ Field successfully processed through enrichment.")
        
        # Silver layer recommendations
        if silver_analysis.get("path_error"):
            recommendations.append("ℹ️ Silver layer not yet available. This is normal if aggregation jobs haven't been configured.")
        elif silver_analysis.get("found_in_silver"):
            if silver_analysis.get("field_aggregations"):
                recommendations.append("✅ Field is being aggregated in silver layer.")
            else:
                recommendations.append("⚠️ Data exists in silver layer but field may not be included in aggregations.")
        else:
            recommendations.append("ℹ️ No recent aggregated data in silver layer. This may be normal if aggregation jobs are pending.")
        
        # General recommendations
        if len(recommendations) == 0:
            recommendations.append("ℹ️ Analysis complete. Review the detailed findings above for specific issues.")
            
        return recommendations

    def get_field_transformation_pipeline(
        self, 
        sensor_id: str, 
        minutes_back: int = 10
    ) -> Dict[str, Any]:
        """
        Get a complete view of how data flows through the transformation pipeline for a sensor.
        
        Args:
            sensor_id: The sensor ID to trace
            minutes_back: How many minutes back to look
            
        Returns:
            Dict with pipeline stages and data samples
        """
        result = {
            "sensor_id": sensor_id,
            "minutes_back": minutes_back,
            "timestamp": datetime.now().isoformat(),
            "pipeline_stages": {}
        }
        
        try:
            spark = self.session_manager.spark
            time_filter = F.current_timestamp() - F.expr(f"INTERVAL {minutes_back} MINUTES")
            
            # Stage 1: Raw Data
            try:
                raw_df = (
                    spark.read.option("basePath", self.sensors_path)
                    .parquet(f"{self.sensors_path}/ingestion_id=*/date=*/hour=*")
                )
                
                # Handle both sensor ID column variations
                columns = raw_df.columns
                if "sensor_id" in columns:
                    sensor_filter = F.col("sensor_id") == sensor_id
                elif "sensorId" in columns:
                    sensor_filter = F.col("sensorId") == sensor_id
                else:
                    # Try both
                    try:
                        sensor_filter = (F.col("sensor_id") == sensor_id) | (F.col("sensorId") == sensor_id)
                    except Exception:
                        sensor_filter = F.lit(True)  # No filter if no sensor ID column
                
                filtered_raw = raw_df.filter(
                    (F.col("timestamp") >= time_filter) & sensor_filter
                )
                
                if not filtered_raw.rdd.isEmpty():
                    sample_raw = filtered_raw.limit(3).collect()
                    result["pipeline_stages"]["1_raw_data"] = {
                        "status": "found",
                        "record_count": filtered_raw.count(),
                        "columns": filtered_raw.columns,
                        "sample_records": [dict(row.asDict()) for row in sample_raw]
                    }
                else:
                    result["pipeline_stages"]["1_raw_data"] = {"status": "no_data"}
                    
            except Exception as e:
                result["pipeline_stages"]["1_raw_data"] = {"status": "error", "error": str(e)}
            
            # Stage 2: Enriched Data
            try:
                enriched_df = (
                    spark.read.format("delta")
                    .load(self.enriched_path)
                    .filter(
                        (F.col("ingest_ts") >= time_filter) &
                        (
                            F.col("sensor_data").getItem("sensorId").isin([sensor_id]) |
                            F.col("sensor_data").getItem("sensor_id").isin([sensor_id]) |
                            F.col("normalized_data").getItem("sensorId").isin([sensor_id])
                        )
                    )
                )
                
                if not enriched_df.rdd.isEmpty():
                    sample_enriched = enriched_df.limit(3).collect()
                    result["pipeline_stages"]["2_enriched_data"] = {
                        "status": "found",
                        "record_count": enriched_df.count(),
                        "columns": enriched_df.columns,
                        "sample_records": [dict(row.asDict()) for row in sample_enriched]
                    }
                else:
                    result["pipeline_stages"]["2_enriched_data"] = {"status": "no_data"}
                    
            except Exception as e:
                result["pipeline_stages"]["2_enriched_data"] = {"status": "error", "error": str(e)}
            
            # Stage 3: Silver Data
            try:
                silver_df = (
                    spark.read.format("delta")
                    .load(self.silver_path)
                    .filter(
                        (F.col("window_start") >= time_filter) &
                        (F.col("sensorId") == sensor_id)
                    )
                )
                
                if not silver_df.rdd.isEmpty():
                    sample_silver = silver_df.limit(3).collect()
                    result["pipeline_stages"]["3_silver_data"] = {
                        "status": "found",
                        "record_count": silver_df.count(),
                        "columns": silver_df.columns,
                        "sample_records": [dict(row.asDict()) for row in sample_silver]
                    }
                else:
                    result["pipeline_stages"]["3_silver_data"] = {"status": "no_data"}
                    
            except Exception as e:
                result["pipeline_stages"]["3_silver_data"] = {"status": "error", "error": str(e)}
            
            result["status"] = "success"
            
        except Exception as e:
            logger.error(f"Error getting transformation pipeline: {e}")
            result["status"] = "error"
            result["error"] = str(e)
            
        return result
