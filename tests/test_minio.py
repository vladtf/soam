#!/usr/bin/env python3
"""
Writes three sensor rows to MinIO as Parquet, reads them back,
and prints the mean temperature.

# 1. Copy the test script into the Spark master container
docker cp test_minio.py spark-master:/tmp/

# 2. Submit the job
docker exec -it spark-master \
  /opt/bitnami/spark/bin/spark-submit \
  --master spark://spark-master:7077 /tmp/test_minio.py
"""

from pyspark.sql import SparkSession, functions as F
import os

spark_host = os.environ.get("SPARK_HOST", "localhost")


ENDPOINT = "http://minio:9000"
ACCESS_KEY = "minio"
SECRET_KEY = "minio123"
BUCKET     = "lake"
PATH       = f"s3a://{BUCKET}/sensors/"

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

data = [("s1", 23.5), ("s2", 22.8), ("s1", 24.1)]
df = spark.createDataFrame(data, ["sensor_id", "temp"])

# 1) APPEND data to MinIO  --------------------------
df.write.mode("append").parquet(PATH)

# 2) READ it back & compute mean  ------------------
mean = (
    spark.read.parquet(PATH)
         .agg(F.avg("temp").alias("mean_temp"))
         .first()[0]
)

print(f"Mean temperature in dataset: {mean:.2f} °C")
spark.stop()
