#!/usr/bin/env python3
"""
Writes three sensor rows to MinIO as Parquet, reads them back,
and prints the mean temperature.

# 1. Copy the test script into the Spark master container and Submit the job
docker cp test_minio_read_files.py soam-backend:/tmp/test_minio_read_files.py && \
docker exec -it soam-backend python /tmp/test_minio_read_files.py
"""

from pyspark.sql import SparkSession, functions as F
import os

spark_host = os.environ.get("SPARK_HOST", "localhost")


ENDPOINT = "http://minio:9000"
ACCESS_KEY = "minio"
SECRET_KEY = "minio123"
BUCKET     = "mybucket"
PATH       = f"s3a://{BUCKET}/sensors/sensor_1"

spark = (
    SparkSession.builder
      .appName("MinIO_E2E_Demo")
      .master(f"spark://{spark_host}:7077")
      # ---- S3A connector settings ----
      .config("spark.hadoop.fs.s3a.endpoint", ENDPOINT)
      .config("spark.hadoop.fs.s3a.path.style.access", "true")
      .config("spark.hadoop.fs.s3a.access.key", ACCESS_KEY)
      .config("spark.hadoop.fs.s3a.secret.key", SECRET_KEY)
      .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
      .getOrCreate()
)

# ----------- COUNT total entities in the bucket -----------
df = (
    spark.read.option("basePath", "s3a://mybucket/sensors/")
         .parquet("s3a://mybucket/sensors/date=*/hour=*")
)
entity_count = df.count()

print(f"Total number of entities in the dataset: {entity_count}")

hourly_avg = (
    df.withColumn("date", F.to_date("timestamp"))
      .withColumn("hour", F.hour("timestamp"))
      .groupBy("date", "hour")
      .agg(F.avg("temperature").alias("avg_temp"))
      .orderBy("date", "hour")
)

hourly_avg.show(truncate=False)

spark.stop()
