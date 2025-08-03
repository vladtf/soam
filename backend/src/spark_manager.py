import os
import requests
import logging
from typing import List, Dict, Any, Optional
from pyspark.sql import SparkSession, functions as F, types as T
from pyspark import SparkContext
from py4j.protocol import Py4JNetworkError

from .models import SparkWorker, SparkApplication, SparkMasterStatus

logging.getLogger('py4j').setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


class SparkManager:
    # ------------------------------------------------------------------ #
    # tune this once – or load per-sensor thresholds from S3/DB instead
    TEMP_THRESHOLD = 30.0        # °C
    ALERT_PATH = "silver/temperature_alerts"   # relative to the bucket
    # -------------------------------2----------------------------------- #

    def __init__(self, spark_host, spark_port,
                 minio_endpoint, minio_access_key, minio_secret_key,
                 minio_bucket, spark_history):
        # Store Spark master web UI URL for API calls
        self.spark_master_url = f"http://{spark_host}:8080"
        self.minio_bucket = minio_bucket
        self.spark_history = spark_history
        self.alerts_fs_path = f"s3a://{minio_bucket}/{self.ALERT_PATH}"
        self.silver = f"s3a://{self.minio_bucket}/silver/five_min_avg"

        # ---------- SparkSession boot ------------------ #
        # Get the hostname that executors can use to reach this driver
        driver_host = os.getenv("SPARK_DRIVER_HOST", "backend")
        driver_bind_address = os.getenv("SPARK_DRIVER_BIND_ADDRESS", "0.0.0.0")
        driver_port = os.getenv("SPARK_DRIVER_PORT", "41397")
        block_manager_port = os.getenv("SPARK_BLOCK_MANAGER_PORT", "41398")

        self.spark = (
            SparkSession.builder
            .appName("SmartCityBackend")
            .master(f"spark://{spark_host}:{spark_port}")
            .config("spark.eventLog.enabled", "true")
            .config("spark.driver.host", driver_host)
            .config("spark.driver.bindAddress", driver_bind_address)
            .config("spark.driver.port", driver_port)
            .config("spark.blockManager.port", block_manager_port)
            .config("spark.hadoop.fs.s3a.endpoint", f"http://{minio_endpoint}")
            .config("spark.hadoop.fs.s3a.path.style.access", "true")
            .config("spark.hadoop.fs.s3a.access.key",  minio_access_key)
            .config("spark.hadoop.fs.s3a.secret.key",  minio_secret_key)
            .config("spark.hadoop.fs.s3a.impl",        "org.apache.hadoop.fs.s3a.S3AFileSystem")
            .config("spark.jars", os.getenv("SPARK_JARS", ""))
            # Use pre-downloaded jars instead of runtime package resolution
            # .config("spark.jars.packages",
            #         ",".join([
            #             "io.delta:delta-spark_2.12:3.1.0",
            #             "org.apache.hadoop:hadoop-aws:3.3.4",
            #             "com.amazonaws:aws-java-sdk-bundle:1.12.620",
            #         ]))
            .config("spark.sql.extensions",
                    "io.delta.sql.DeltaSparkSessionExtension")
            .config("spark.sql.catalog.spark_catalog",
                    "org.apache.spark.sql.delta.catalog.DeltaCatalog")
            .getOrCreate()
        )
        self.spark.sparkContext.setLogLevel("WARN")

        # Initialize streaming queries as None
        self.avg_query = None
        self.alert_query = None

        # Check if the sensors data directory exists
        if not self._check_data_directory():
            logger.warning("Sensors data directory not ready. Streaming will be started when data becomes available.")
        else:
            # Try to launch both streams, but don't fail if they can't start
            # pass
            self._start_streams_safely()

    def get_spark_master_status(self) -> Dict[str, Any]:
        """Fetch Spark master status from the web UI API."""
        try:
            response = requests.get(f"{self.spark_master_url}/json/", timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Use the model's deserialization method
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

    def _start_streams_safely(self):
        """Start streaming jobs with error handling"""
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

    def _check_data_directory(self):
        """Check if the sensors data directory exists"""
        try:
            # Try to list the base sensors directory
            df = self.spark.read.option("basePath", f"s3a://{self.minio_bucket}/sensors/").parquet(f"s3a://{self.minio_bucket}/sensors/")
            # If we can create the DataFrame, directory exists
            return True
        except Exception as e:
            logger.error(f"Data directory not ready: {e}")
            return False

    def _ensure_streams_running(self):
        """Ensure streaming jobs are running, start them if not"""
        pass
        try:
            # Check if streams are running
            if self.avg_query is None or not self.avg_query.isActive:
                logger.info("Temperature stream not active, attempting to start...")
                self._start_temperature_stream()

            if self.alert_query is None or not self.alert_query.isActive:
                logger.info("Alert stream not active, attempting to start...")
                self._start_alert_stream()

        except Exception as e:
            logger.error(f"Error ensuring streams are running: {e}")

    # ------------------------------------------------------------------ #
    # 1) hourly average (unchanged – still kept in memory)
    # ------------------------------------------------------------------ #
    def _start_temperature_stream(self):
        schema = T.StructType([
            T.StructField("sensorId",    T.StringType()),
            T.StructField("temperature", T.DoubleType()),
            T.StructField("timestamp",   T.StringType())
        ])

        raw = (self.spark.readStream
                   .schema(schema)
                   .option("basePath", f"s3a://{self.minio_bucket}/sensors/")
                   .option("maxFilesPerTrigger", 20)
                   .parquet(f"s3a://{self.minio_bucket}/sensors/date=*/hour=*")
                   .withColumn("timestamp", F.to_timestamp("timestamp")))

        # Calculate average temperature in 5-minute buckets
        five_min_avg = (raw
                        .withWatermark("timestamp", "1 minute")
                        .groupBy(F.window("timestamp", "5 minutes").alias("time_window"),
                                 "sensorId")
                        .agg(F.round(F.avg("temperature"), 2).alias("avg_temp"))
                        .selectExpr("sensorId",
                                    "time_window.start as time_start",
                                    "avg_temp"))

        self.avg_query = (five_min_avg.writeStream
                          .format("delta")                       # or parquet
                          .option("path", self.silver)
                          .option("checkpointLocation",
                                  f"s3a://{self.minio_bucket}/_ckpt/five_min_avg")
                          .outputMode("complete")                # rewrites the file
                          .trigger(processingTime="1 minute")
                          .start())

    # ------------------------------------------------------------------ #
    # 2) alert stream – NEW
    # ------------------------------------------------------------------ #
    def _start_alert_stream(self):
        schema = T.StructType([
            T.StructField("sensorId",    T.StringType()),
            T.StructField("temperature", T.DoubleType()),
            T.StructField("timestamp",   T.StringType())
        ])

        raw = (self.spark.readStream
                   .schema(schema)
                   .option("basePath", f"s3a://{self.minio_bucket}/sensors/")
                   .option("maxFilesPerTrigger", 20)
                   .parquet(f"s3a://{self.minio_bucket}/sensors/date=*/hour=*")
                   .withColumn("event_time", F.to_timestamp("timestamp")))

        alerts = (raw
                  .filter(F.col("temperature") > self.TEMP_THRESHOLD)
                  .withColumn("alert_type", F.lit("TEMP_OVER_LIMIT")))

        # Deduplicate alerts using a Delta table
        deduplicated_alerts = (alerts
                               .withColumn("alert_id", F.concat(F.col("sensorId"), F.lit("_"), F.col("event_time")))
                               .withColumn("alert_time", F.current_timestamp())
                               .dropDuplicates(["sensorId"])
                               .select("sensorId", "temperature", "event_time", "alert_type"))  # Select only required columns

        self.alert_query = (deduplicated_alerts.writeStream
                            .format("delta")                          # durable, replayable
                            .option("path",     self.alerts_fs_path)
                            .option("checkpointLocation",
                                    f"s3a://{self.minio_bucket}/_ckpt/alert_stream")
                            .option("mergeSchema", "true")            # Enable schema merging
                            .outputMode("append")
                            .trigger(processingTime="30 seconds")
                            .start())

    def stop_streams(self):
        """Stop all streaming queries"""
        try:
            if self.avg_query and self.avg_query.isActive:
                self.avg_query.stop()
                logger.info("Temperature stream stopped")
        except Exception as e:
            logger.error(f"Error stopping temperature stream: {e}")

        try:
            if self.alert_query and self.alert_query.isActive:
                self.alert_query.stop()
                logger.info("Alert stream stopped")
        except Exception as e:
            logger.error(f"Error stopping alert stream: {e}")

    def _check_spark_connection(self):
        """Check if Spark session is available and working."""
        try:
            # Simple test to verify Spark session is working
            self.spark.sql("SELECT 1").collect()
            return True
        except Exception as e:
            logger.error(f"Spark connection check failed: {e}")
            return False

    def _reconnect_spark_session(self):
        """Attempt to reconnect the Spark session."""
        try:
            if hasattr(self, 'spark') and self.spark:
                self.spark.stop()
        except Exception as e:
            logger.warning(f"Error stopping existing Spark session: {e}")

        try:
            # Recreate the Spark session with the same configuration
            driver_host = os.getenv("SPARK_DRIVER_HOST", "backend")
            driver_bind_address = os.getenv("SPARK_DRIVER_BIND_ADDRESS", "0.0.0.0")
            driver_port = os.getenv("SPARK_DRIVER_PORT", "41397")
            block_manager_port = os.getenv("SPARK_BLOCK_MANAGER_PORT", "41398")

            self.spark = (
                SparkSession.builder
                .appName("SmartCityBackend")
                .master(f"spark://{os.getenv('SPARK_HOST', 'spark-master')}:{os.getenv('SPARK_PORT', '7077')}")
                .config("spark.eventLog.enabled", "true")
                .config("spark.driver.host", driver_host)
                .config("spark.driver.bindAddress", driver_bind_address)
                .config("spark.driver.port", driver_port)
                .config("spark.blockManager.port", block_manager_port)
                .config("spark.hadoop.fs.s3a.endpoint", f"http://{os.getenv('MINIO_ENDPOINT', 'minio:9000')}")
                .config("spark.hadoop.fs.s3a.path.style.access", "true")
                .config("spark.hadoop.fs.s3a.access.key", os.getenv('MINIO_ACCESS_KEY', 'minio'))
                .config("spark.hadoop.fs.s3a.secret.key", os.getenv('MINIO_SECRET_KEY', 'minio123'))
                .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
                .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
                .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
                .getOrCreate()
            )
            logger.info("Spark session reconnected successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reconnect Spark session: {e}")
            return False

    # ------------------------------------------------------------------ #
    # REST helpers
    # ------------------------------------------------------------------ #
    def get_streaming_average_temperature(self, minutes=30):
        # Ensure streams are running
        self._ensure_streams_running()

        if not self._check_spark_connection():
            logger.info("Spark connection lost, attempting to reconnect...")
            if not self._reconnect_spark_session():
                raise ConnectionError("Spark session is not available and reconnection failed")

        try:
            df = (self.spark.read.format("delta").load(self.silver)
                  .filter(F.col("time_start") >=
                          F.current_timestamp() - F.expr(f"INTERVAL {minutes} MINUTES")))
            rows = df.collect()
            return {"status": "success",
                    "data": [row.asDict() for row in rows]}
        except Exception as e:
            logger.error(f"Failed to get streaming average temperature: {e}")
            # Try reconnecting once more on failure
            if self._reconnect_spark_session():
                try:
                    df = (self.spark.read.format("delta").load(self.silver)
                          .filter(F.col("time_start") >=
                                  F.current_timestamp() - F.expr(f"INTERVAL {minutes} MINUTES")))
                    rows = df.collect()
                    return {"status": "success",
                            "data": [row.asDict() for row in rows]}
                except Exception as retry_e:
                    logger.error(f"Retry also failed: {retry_e}")
                    raise
            else:
                raise

    def get_temperature_alerts(self, since_minutes=60):
        """Return recent alerts from the Delta table (default last 60 min)."""
        # Ensure streams are running
        self._ensure_streams_running()

        if not self._check_spark_connection():
            logger.info("Spark connection lost, attempting to reconnect...")
            if not self._reconnect_spark_session():
                raise ConnectionError("Spark session is not available and reconnection failed")

        try:
            df = (self.spark.read.format("delta").load(self.alerts_fs_path)
                  .filter(F.col("event_time") >= F.current_timestamp() - F.expr(f"INTERVAL {since_minutes} minutes")))
            return {"status": "success",
                    "data": [row.asDict() for row in df.collect()]}
        except Exception as e:
            logger.error(f"Failed to get temperature alerts: {e}")
            # Try reconnecting once more on failure
            if self._reconnect_spark_session():
                try:
                    df = (self.spark.read.format("delta").load(self.alerts_fs_path)
                          .filter(F.col("event_time") >= F.current_timestamp() - F.expr(f"INTERVAL {since_minutes} minutes")))
                    return {"status": "success",
                            "data": [row.asDict() for row in df.collect()]}
                except Exception as retry_e:
                    logger.error(f"Retry also failed: {retry_e}")
                    raise
            else:
                raise

    def test_spark_basic_computation(self):
        """Simple Spark computation test to verify Spark is working"""
        try:
            if not self._check_spark_connection():
                return {
                    "status": "error",
                    "message": "Spark connection not available"
                }
            
            # Simplest possible test - just verify Spark can execute SQL
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

    def test_sensor_data_access(self):
        """Test if Spark can access real sensor data from MinIO"""
        try:
            if not self._check_spark_connection():
                return {
                    "status": "error",
                    "message": "Spark connection not available"
                }
            
            # Try to read actual sensor data
            sensor_path = f"s3a://{self.minio_bucket}/sensors/"
            
            try:
                # Attempt to read sensor data
                df = self.spark.read.option("basePath", sensor_path).parquet(f"{sensor_path}date=*/hour=*")
                count = df.count()
                
                if count > 0:
                    # Get a sample of recent data
                    sample = df.limit(3).collect()
                    sample_data = []
                    for row in sample:
                        sample_data.append({
                            "sensorId": row.sensorId if hasattr(row, 'sensorId') else 'unknown',
                            "temperature": row.temperature if hasattr(row, 'temperature') else 'unknown',
                            "timestamp": str(row.timestamp) if hasattr(row, 'timestamp') else 'unknown'
                        })
                    
                    return {
                        "status": "success",
                        "message": "Successfully accessed sensor data",
                        "results": {
                            "total_sensor_records": count,
                            "sample_data": sample_data,
                            "data_path": sensor_path
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
                    "results": {"data_path": sensor_path}
                }
                
        except Exception as e:
            logger.error(f"Sensor data access test failed: {e}")
            return {
                "status": "error",
                "message": f"Test failed: {str(e)}"
            }

    # ------------------------------------------------------------------ #
    # misc utilities (unchanged)
    # ------------------------------------------------------------------ #
    def stop_streams(self):
        for q in (getattr(self, "avg_query", None),
                  getattr(self, "alert_query", None)):
            if q and q.isActive:
                q.stop()

    def close(self):
        self.stop_streams()
        self.spark.stop()
