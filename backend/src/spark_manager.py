import os
import json
import requests
from pathlib import Path
from pyspark.sql import SparkSession, functions as F, types as T


class SparkManager:
    # ------------------------------------------------------------------ #
    # tune this once – or load per-sensor thresholds from S3/DB instead
    TEMP_THRESHOLD = 30.0        # °C
    ALERT_PATH = "silver/temperature_alerts"   # relative to the bucket
    # ------------------------------------------------------------------ #

    def __init__(self, spark_host, spark_port,
                 minio_endpoint, minio_access_key, minio_secret_key,
                 minio_bucket, spark_history):

        # ↓ stash params you need later
        self.minio_bucket = minio_bucket
        self.spark_history = spark_history
        self.alerts_fs_path = f"s3a://{minio_bucket}/{self.ALERT_PATH}"
        self.silver = f"s3a://{self.minio_bucket}/silver/five_min_avg"

        # ---------- SparkSession boot ----------------------------------
        self.spark = (
            SparkSession.builder
            .appName("SmartCityBackend")
            .master(f"spark://{spark_host}:{spark_port}")
            .config("spark.eventLog.enabled", "true")
            .config("spark.hadoop.fs.s3a.endpoint", f"http://{minio_endpoint}")
            .config("spark.hadoop.fs.s3a.path.style.access", "true")
            .config("spark.hadoop.fs.s3a.access.key",  minio_access_key)
            .config("spark.hadoop.fs.s3a.secret.key",  minio_secret_key)
            .config("spark.hadoop.fs.s3a.impl",        "org.apache.hadoop.fs.s3a.S3AFileSystem")
            .config("spark.jars.packages",
                    ",".join([
                        "io.delta:delta-spark_2.12:3.1.0",
                        "org.apache.hadoop:hadoop-aws:3.3.4",
                        "com.amazonaws:aws-java-sdk-bundle:1.12.620",
                    ]))
            .config("spark.sql.extensions",
                    "io.delta.sql.DeltaSparkSessionExtension")
            .config("spark.sql.catalog.spark_catalog",
                    "org.apache.spark.sql.delta.catalog.DeltaCatalog")
            .getOrCreate()
        )
        self.spark.sparkContext.setLogLevel("WARN")

        # launch both streams
        self._start_temperature_stream()
        self._start_alert_stream()

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

    # ------------------------------------------------------------------ #
    # REST helpers
    # ------------------------------------------------------------------ #
    def get_streaming_average_temperature(self, minutes=30):
        df = (self.spark.read.format("delta").load(self.silver)
                .filter(F.col("time_start") >=
                        F.current_timestamp() - F.expr(f"INTERVAL {minutes} MINUTES")))
        rows = df.collect()
        return {"status":"success",
                "data":[row.asDict() for row in rows]}

    def get_temperature_alerts(self, since_minutes=60):
        """Return recent alerts from the Delta table (default last 60 min)."""
        df = (self.spark.read.format("delta").load(self.alerts_fs_path)
                .filter(F.col("event_time") >= F.current_timestamp() - F.expr(f"INTERVAL {since_minutes} minutes")))
        return {"status": "success",
                "data": [row.asDict() for row in df.collect()]}


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
