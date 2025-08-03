import os
import requests
import logging
from typing import Dict, Any, Optional
from pyspark.sql import SparkSession, functions as F, types as T
from pyspark.sql.streaming import StreamingQuery

from src.spark.spark_models import SparkMasterStatus

logging.getLogger('py4j').setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


class SparkManager:
    """
    Manages Spark session, streaming jobs, and data access for the SOAM smart city platform.
    
    Handles:
    - Spark session lifecycle and reconnection
    - Real-time streaming for temperature averages and alerts
    - Data access with graceful error handling
    - Integration with MinIO for data storage
    """
    
    # Configuration constants
    TEMP_THRESHOLD = 30.0  # °C - Temperature threshold for alerts
    ALERT_PATH = "silver/temperature_alerts"  # Path relative to bucket
    SILVER_PATH = "silver/five_min_avg"  # Path for aggregated temperature data
    
    def __init__(self, spark_host: str, spark_port: str, minio_endpoint: str, 
                 minio_access_key: str, minio_secret_key: str, minio_bucket: str, 
                 spark_history: str):
        """Initialize SparkManager with connection parameters."""
        # Store connection parameters
        self.spark_host = spark_host
        self.spark_port = spark_port
        self.minio_endpoint = minio_endpoint
        self.minio_access_key = minio_access_key
        self.minio_secret_key = minio_secret_key
        self.minio_bucket = minio_bucket
        self.spark_history = spark_history
        
        # Build paths
        self.spark_master_url = f"http://{spark_host}:8080"
        self.alerts_fs_path = f"s3a://{minio_bucket}/{self.ALERT_PATH}"
        self.silver_path = f"s3a://{minio_bucket}/{self.SILVER_PATH}"
        self.sensors_path = f"s3a://{minio_bucket}/sensors/"
        
        # Initialize streaming queries
        self.avg_query: Optional[StreamingQuery] = None
        self.alert_query: Optional[StreamingQuery] = None
        
        # Initialize Spark session
        self.spark = self._create_spark_session()
        
        # Start streaming if data is available
        self._initialize_streaming()

    def _create_spark_session(self) -> SparkSession:
        """Create and configure Spark session."""
        # Get driver configuration from environment
        driver_host = os.getenv("SPARK_DRIVER_HOST", "backend")
        driver_bind_address = os.getenv("SPARK_DRIVER_BIND_ADDRESS", "0.0.0.0")
        driver_port = os.getenv("SPARK_DRIVER_PORT", "41397")
        block_manager_port = os.getenv("SPARK_BLOCK_MANAGER_PORT", "41398")
        
        spark = (
            SparkSession.builder
            .appName("SmartCityBackend")
            .master(f"spark://{self.spark_host}:{self.spark_port}")
            .config("spark.eventLog.enabled", "true")
            .config("spark.driver.host", driver_host)
            .config("spark.driver.bindAddress", driver_bind_address)
            .config("spark.driver.port", driver_port)
            .config("spark.blockManager.port", block_manager_port)
            .config("spark.hadoop.fs.s3a.endpoint", f"http://{self.minio_endpoint}")
            .config("spark.hadoop.fs.s3a.path.style.access", "true")
            .config("spark.hadoop.fs.s3a.access.key", self.minio_access_key)
            .config("spark.hadoop.fs.s3a.secret.key", self.minio_secret_key)
            .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
            .config("spark.jars", os.getenv("SPARK_JARS", ""))
            .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
            .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
            .getOrCreate()
        )
        
        spark.sparkContext.setLogLevel("WARN")
        return spark

    def _initialize_streaming(self) -> None:
        """Initialize streaming jobs if data directory is available."""
        if self._is_data_directory_ready():
            self._start_streams_safely()
        else:
            logger.warning("Sensors data directory not ready. Streaming will be started when data becomes available.")

    def _is_data_directory_ready(self) -> bool:
        """Check if the sensors data directory exists and is accessible."""
        try:
            # Try to access the sensors directory
            self.spark.read.option("basePath", self.sensors_path).parquet(self.sensors_path)
            return True
        except Exception as e:
            logger.debug(f"Data directory not ready: {e}")
            return False

    # ================================================================
    # Spark Master Status API
    # ================================================================
    
    def get_spark_master_status(self) -> Dict[str, Any]:
        """Fetch Spark master status from the web UI API."""
        try:
            response = requests.get(f"{self.spark_master_url}/json/", timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Parse using the SparkMasterStatus model
            master_status = SparkMasterStatus.from_dict(data)
            
            return {
                "status": "success",
                "data": master_status
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch Spark master status: {e}")
            return {
                "status": "error",
                "message": f"Failed to connect to Spark master: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Error parsing Spark master status: {e}")
            return {
                "status": "error",
                "message": f"Error processing Spark master response: {str(e)}"
            }

    # ================================================================
    # Streaming Management
    # ================================================================

    def _start_streams_safely(self) -> None:
        """Start streaming jobs with error handling."""
        try:
            self._start_temperature_stream()
            logger.info("Temperature streaming started successfully")
        except Exception as e:
            logger.error(f"Failed to start temperature stream: {e}")

        try:
            self._start_alert_stream()
            logger.info("Alert streaming started successfully")
        except Exception as e:
            logger.error(f"Failed to start alert stream: {e}")

    def _ensure_streams_running(self) -> None:
        """Ensure streaming jobs are running, start them if not."""
        try:
            # Check temperature stream
            if self.avg_query is None or not self.avg_query.isActive:
                logger.info("Temperature stream not active, attempting to start...")
                self._start_temperature_stream()

            # Check alert stream
            if self.alert_query is None or not self.alert_query.isActive:
                logger.info("Alert stream not active, attempting to start...")
                self._start_alert_stream()

        except Exception as e:
            logger.error(f"Error ensuring streams are running: {e}")

    def _get_sensor_schema(self) -> T.StructType:
        """Get the schema for sensor data."""
        return T.StructType([
            T.StructField("sensorId", T.StringType()),
            T.StructField("temperature", T.DoubleType()),
            T.StructField("timestamp", T.StringType())
        ])

    def _start_temperature_stream(self) -> None:
        """Start the temperature averaging stream (5-minute windows)."""
        schema = self._get_sensor_schema()

        # Read streaming data
        raw_stream = (
            self.spark.readStream
            .schema(schema)
            .option("basePath", self.sensors_path)
            .option("maxFilesPerTrigger", 20)
            .parquet(f"{self.sensors_path}date=*/hour=*")
            .withColumn("timestamp", F.to_timestamp("timestamp"))
        )

        # Calculate 5-minute averages
        five_min_avg = (
            raw_stream
            .withWatermark("timestamp", "1 minute")
            .groupBy(
                F.window("timestamp", "5 minutes").alias("time_window"),
                "sensorId"
            )
            .agg(F.round(F.avg("temperature"), 2).alias("avg_temp"))
            .selectExpr(
                "sensorId",
                "time_window.start as time_start",
                "avg_temp"
            )
        )

        # Write to Delta table
        self.avg_query = (
            five_min_avg.writeStream
            .format("delta")
            .option("path", self.silver_path)
            .option("checkpointLocation", f"s3a://{self.minio_bucket}/_ckpt/five_min_avg")
            .outputMode("complete")
            .trigger(processingTime="1 minute")
            .start()
        )

    def _start_alert_stream(self) -> None:
        """Start the temperature alert stream."""
        schema = self._get_sensor_schema()

        # Read streaming data
        raw_stream = (
            self.spark.readStream
            .schema(schema)
            .option("basePath", self.sensors_path)
            .option("maxFilesPerTrigger", 20)
            .parquet(f"{self.sensors_path}date=*/hour=*")
            .withColumn("event_time", F.to_timestamp("timestamp"))
        )

        # Filter for temperature alerts and deduplicate
        alerts = (
            raw_stream
            .filter(F.col("temperature") > self.TEMP_THRESHOLD)
            .withColumn("alert_type", F.lit("TEMP_OVER_LIMIT"))
            .withColumn("alert_id", F.concat(F.col("sensorId"), F.lit("_"), F.col("event_time")))
            .withColumn("alert_time", F.current_timestamp())
            .dropDuplicates(["sensorId"])
            .select("sensorId", "temperature", "event_time", "alert_type")
        )

        # Write to Delta table
        self.alert_query = (
            alerts.writeStream
            .format("delta")
            .option("path", self.alerts_fs_path)
            .option("checkpointLocation", f"s3a://{self.minio_bucket}/_ckpt/alert_stream")
            .option("mergeSchema", "true")
            .outputMode("append")
            .trigger(processingTime="30 seconds")
            .start()
        )

    def stop_streams(self) -> None:
        """Stop all streaming queries gracefully."""
        streams = [
            ("Temperature stream", self.avg_query),
            ("Alert stream", self.alert_query)
        ]
        
        for stream_name, query in streams:
            try:
                if query and query.isActive:
                    query.stop()
                    logger.info(f"{stream_name} stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping {stream_name.lower()}: {e}")

    # ================================================================
    # Spark Session Management
    # ================================================================

    def _is_spark_connected(self) -> bool:
        """Check if Spark session is available and working."""
        try:
            self.spark.sql("SELECT 1").collect()
            return True
        except Exception as e:
            logger.error(f"Spark connection check failed: {e}")
            return False

    def _reconnect_spark_session(self) -> bool:
        """Attempt to reconnect the Spark session."""
        try:
            # Stop existing session
            if hasattr(self, 'spark') and self.spark:
                self.spark.stop()
        except Exception as e:
            logger.warning(f"Error stopping existing Spark session: {e}")

        try:
            # Create new session
            self.spark = self._create_spark_session()
            logger.info("Spark session reconnected successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reconnect Spark session: {e}")
            return False

    def _handle_table_not_found_error(self, error: Exception) -> bool:
        """Check if the error indicates a table/path not found."""
        error_str = str(error).lower()
        error_type = str(type(error))
        
        return (
            "path does not exist" in error_str or 
            "not found" in error_str or 
            "analysisexception" in error_type.lower()
        )

    def _create_table_not_ready_response(self, data_type: str) -> Dict[str, Any]:
        """Create a standard response for when tables are not ready."""
        return {
            "status": "success",
            "data": [],
            "message": f"{data_type} data not available yet. Please wait for data processing to begin."
        }

    # ================================================================
    # Data Access Methods
    # ================================================================
    def get_streaming_average_temperature(self, minutes: int = 30) -> Dict[str, Any]:
        """
        Get streaming average temperature data for the specified time window.
        
        Args:
            minutes: Time window in minutes (default: 30)
            
        Returns:
            Dict containing status and temperature data
        """
        self._ensure_streams_running()

        if not self._is_spark_connected():
            logger.info("Spark connection lost, attempting to reconnect...")
            if not self._reconnect_spark_session():
                raise ConnectionError("Spark session is not available and reconnection failed")

        try:
            df = (
                self.spark.read.format("delta")
                .load(self.silver_path)
                .filter(F.col("time_start") >= F.current_timestamp() - F.expr(f"INTERVAL {minutes} MINUTES"))
            )
            rows = df.collect()
            return {
                "status": "success",
                "data": [row.asDict() for row in rows]
            }
            
        except Exception as e:
            logger.error(f"Failed to get streaming average temperature: {e}")
            
            if self._handle_table_not_found_error(e):
                logger.info("Silver table not found, streaming likely hasn't started yet")
                return self._create_table_not_ready_response("Streaming")
            
            # Try reconnecting and retry once
            if self._reconnect_spark_session():
                try:
                    df = (
                        self.spark.read.format("delta")
                        .load(self.silver_path)
                        .filter(F.col("time_start") >= F.current_timestamp() - F.expr(f"INTERVAL {minutes} MINUTES"))
                    )
                    rows = df.collect()
                    return {
                        "status": "success", 
                        "data": [row.asDict() for row in rows]
                    }
                except Exception as retry_e:
                    logger.error(f"Retry also failed: {retry_e}")
                    if self._handle_table_not_found_error(retry_e):
                        return self._create_table_not_ready_response("Streaming")
                    raise
            else:
                raise

    def get_temperature_alerts(self, since_minutes: int = 60) -> Dict[str, Any]:
        """
        Get recent temperature alerts.
        
        Args:
            since_minutes: Time window in minutes (default: 60)
            
        Returns:
            Dict containing status and alert data
        """
        self._ensure_streams_running()

        if not self._is_spark_connected():
            logger.info("Spark connection lost, attempting to reconnect...")
            if not self._reconnect_spark_session():
                raise ConnectionError("Spark session is not available and reconnection failed")

        try:
            df = (
                self.spark.read.format("delta")
                .load(self.alerts_fs_path)
                .filter(F.col("event_time") >= F.current_timestamp() - F.expr(f"INTERVAL {since_minutes} minutes"))
            )
            return {
                "status": "success",
                "data": [row.asDict() for row in df.collect()]
            }
            
        except Exception as e:
            logger.error(f"Failed to get temperature alerts: {e}")
            
            if self._handle_table_not_found_error(e):
                logger.info("Alerts table not found, streaming likely hasn't started yet")
                return self._create_table_not_ready_response("Alert")
            
            # Try reconnecting and retry once
            if self._reconnect_spark_session():
                try:
                    df = (
                        self.spark.read.format("delta")
                        .load(self.alerts_fs_path)
                        .filter(F.col("event_time") >= F.current_timestamp() - F.expr(f"INTERVAL {since_minutes} minutes"))
                    )
                    return {
                        "status": "success",
                        "data": [row.asDict() for row in df.collect()]
                    }
                except Exception as retry_e:
                    logger.error(f"Retry also failed: {retry_e}")
                    if self._handle_table_not_found_error(retry_e):
                        return self._create_table_not_ready_response("Alert")
                    raise
            else:
                raise

    # ================================================================
    # Testing and Diagnostics
    # ================================================================

    def test_spark_basic_computation(self) -> Dict[str, Any]:
        """Test basic Spark functionality."""
        try:
            if not self._is_spark_connected():
                return {
                    "status": "error",
                    "message": "Spark connection not available"
                }
            
            # Execute simple SQL test
            result = self.spark.sql("SELECT 1 as test_value, 'hello' as test_string").collect()
            
            if result and len(result) > 0:
                row = result[0]
                return {
                    "status": "success",
                    "message": "Spark is working correctly",
                    "results": {
                        "spark_version": self.spark.version,
                        "test_sql_result": {
                            "test_value": row[0],
                            "test_string": row[1]
                        },
                        "can_execute_sql": True,
                        "spark_context_active": not self.spark.sparkContext._jsc.sc().isStopped()
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
            if not self._is_spark_connected():
                return {
                    "status": "error",
                    "message": "Spark connection not available"
                }
            
            try:
                # Attempt to read sensor data
                df = self.spark.read.option("basePath", self.sensors_path).parquet(f"{self.sensors_path}date=*/hour=*")
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

    # ================================================================
    # Lifecycle Management
    # ================================================================

    def close(self) -> None:
        """Clean shutdown of SparkManager."""
        logger.info("Shutting down SparkManager...")
        
        # Stop streaming queries
        self.stop_streams()
        
        # Stop Spark session
        try:
            if hasattr(self, 'spark') and self.spark:
                self.spark.stop()
                logger.info("Spark session stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping Spark session: {e}")
        
        logger.info("SparkManager shutdown complete")