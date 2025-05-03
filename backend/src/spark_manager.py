import requests
from pyspark.sql import SparkSession, functions as F


class SparkManager:
    def __init__(self, spark_host, spark_port, minio_endpoint, minio_access_key, minio_secret_key, minio_bucket, spark_history):
        self.spark_host = spark_host
        self.spark_port = spark_port
        self.minio_endpoint = minio_endpoint
        self.minio_access_key = minio_access_key
        self.minio_secret_key = minio_secret_key
        self.minio_bucket = minio_bucket
        self.spark_history = spark_history
        self.spark = (
                SparkSession.builder
                .appName("SmartCityBackend")
                .master(f"spark://{self.spark_host}:{self.spark_port}")
                .config("spark.eventLog.enabled", "true")
                .config("spark.hadoop.fs.s3a.endpoint", f"http://{self.minio_endpoint}")
                .config("spark.hadoop.fs.s3a.path.style.access", "true")
                .config("spark.hadoop.fs.s3a.access.key", self.minio_access_key)
                .config("spark.hadoop.fs.s3a.secret.key", self.minio_secret_key)
                .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
                .config(
                    "spark.jars.packages",
                    ",".join([
                        "io.delta:delta-spark_2.12:3.1.0",
                        "org.apache.hadoop:hadoop-aws:3.3.4",
                        "com.amazonaws:aws-java-sdk-bundle:1.12.620",
                    ])
                )
                .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
                .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
                .getOrCreate()
            )
            
        self.spark.sparkContext.setLogLevel("INFO")
    

    def get_average_temperature(self):
        try:
            # Read sensor data from MinIO
            df = (
                self.spark.read.option("basePath", f"s3a://{self.minio_bucket}/sensors/")
                .parquet(f"s3a://{self.minio_bucket}/sensors/date=*/hour=*")
            )
            hourly_avg = (
                df.withColumn("date", F.to_date("timestamp"))
                .withColumn("hour", F.hour("timestamp"))
                .groupBy("date", "hour")
                .agg(F.avg("temperature").alias("avg_temp"))
                .orderBy("date", "hour")
            )
            response_data = hourly_avg.collect()
            response_list = [
                {"date": row["date"], "hour": row["hour"], "avg_temp": row["avg_temp"]}
                for row in response_data
            ]
            return {"status": "success", "data": response_list}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    def get_running_spark_jobs(self):
        try:
            base = f"{self.spark_history}/api/v1/applications"
            apps = requests.get(base, timeout=5).json()
            running = []
            for app in apps:
                app_id = app["id"]
                app_name = app["name"]
                jobs = requests.get(f"{base}/{app_id}/jobs", timeout=5).json()
                for j in jobs:
                    if j["status"] == "RUNNING":
                        running.append({
                            "app_id": app_id,
                            "app_name": app_name,
                            "job_id": j["jobId"],
                            "job_name": j["name"],
                            "status": j["status"],
                            "submission_time": j["submissionTime"],
                        })
            return {"status": "success", "data": running}
        except requests.exceptions.RequestException as e:
            return {"status": "error", "detail": f"HTTP error: {e}"}
        except ValueError as e:
            return {"status": "error", "detail": f"Bad JSON: {e}"}

    def close(self):
        """Close the Spark session."""
        self.spark.stop()