"""
Testing and diagnostic utilities for Spark operations.
"""
import logging
from typing import Dict, Any

from .session import SparkSessionManager

logger = logging.getLogger(__name__)


class SparkDiagnostics:
    """Provides testing and diagnostic capabilities for Spark operations."""
    
    def __init__(self, session_manager: SparkSessionManager, minio_bucket: str):
        """Initialize SparkDiagnostics."""
        self.session_manager = session_manager
        self.minio_bucket = minio_bucket
        self.sensors_path = f"s3a://{minio_bucket}/sensors/"
    
    def test_spark_basic_computation(self) -> Dict[str, Any]:
        """Test basic Spark functionality."""
        try:
            if not self.session_manager.is_connected():
                return {
                    "status": "error",
                    "message": "Spark connection not available"
                }
            
            # Execute simple SQL test
            result = self.session_manager.spark.sql("SELECT 1 as test_value, 'hello' as test_string").collect()
            
            if result and len(result) > 0:
                row = result[0]
                return {
                    "status": "success",
                    "message": "Spark is working correctly",
                    "results": {
                        "spark_version": self.session_manager.spark.version,
                        "test_sql_result": {
                            "test_value": row[0],
                            "test_string": row[1]
                        },
                        "can_execute_sql": True,
                        "spark_context_active": not self.session_manager.spark.sparkContext._jsc.sc().isStopped()
                    }
                }
            else:
                return {
                    "status": "error",
                    "message": "Spark SQL execution returned no results"
                }
                
        except Exception as e:
            logger.error(f"Spark basic computation test failed: {e}")
            return {
                "status": "error",
                "message": f"Spark test failed: {str(e)}"
            }

    def test_sensor_data_access(self) -> Dict[str, Any]:
        """Test access to sensor data in MinIO."""
        try:
            if not self.session_manager.is_connected():
                return {
                    "status": "error",
                    "message": "Spark connection not available"
                }
            
            try:
                # Attempt to read sensor data
                df = self.session_manager.spark.read.option("basePath", self.sensors_path).parquet(f"{self.sensors_path}date=*/hour=*")
                count = df.count()
                
                if count > 0:
                    # Get sample data
                    sample = df.limit(3).collect()
                    sample_data = [
                        {
                            "sensorId": getattr(row, 'sensorId', 'unknown'),
                            "temperature": getattr(row, 'temperature', 'unknown'),
                            "timestamp": str(getattr(row, 'timestamp', 'unknown'))
                        }
                        for row in sample
                    ]
                    
                    return {
                        "status": "success",
                        "message": "Successfully accessed sensor data",
                        "results": {
                            "total_sensor_records": count,
                            "sample_data": sample_data,
                            "data_path": self.sensors_path
                        }
                    }
                else:
                    return {
                        "status": "warning",
                        "message": "Sensor data directory exists but contains no data",
                        "results": {"total_sensor_records": 0}
                    }
                    
            except Exception as data_error:
                return {
                    "status": "warning", 
                    "message": f"Cannot access sensor data: {str(data_error)}",
                    "results": {"data_path": self.sensors_path}
                }
                
        except Exception as e:
            logger.error(f"Sensor data access test failed: {e}")
            return {
                "status": "error",
                "message": f"Test failed: {str(e)}"
            }
