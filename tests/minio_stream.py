#!/usr/bin/env python3
'''
Smoke test for the MinIO stream source.

docker cp minio_stream.py soam-backend:/tmp/minio_stream.py && \
docker exec -it soam-backend python /tmp/minio_stream.py
'''
from pyspark.sql import SparkSession, functions as F, types as T
import os

# ------------------------------------------------------------------ #
#         connection details – identical to your original script     #
# ------------------------------------------------------------------ #
spark_host = os.environ.get("SPARK_HOST", "localhost")
ENDPOINT = "http://minio:9000"
ACCESS_KEY = "minio"
SECRET_KEY = "minio123"
BUCKET = "lake"

BRONZE_PATH = "s3a://lake/sensors/date=*/hour=*"
BASE_PATH = "s3a://lake/sensors/"            # so partition columns resolve
CKPT_PATH = "s3a://lake/_checkpoints/iot_hourly_mean"

# ------------------------------------------------------------------ #
#                       Spark session                                #
# ------------------------------------------------------------------ #
spark = (
    SparkSession.builder
    .appName("MinIO_Streaming_Demo")
    .master(f"spark://{spark_host}:7077")
    # ---- S3A connector settings ----
    .config("spark.hadoop.fs.s3a.endpoint", ENDPOINT)
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.access.key", ACCESS_KEY)
    .config("spark.hadoop.fs.s3a.secret.key", SECRET_KEY)
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
spark.sparkContext.setLogLevel("WARN")  # keep the log quiet

# Disable vectorized reader to avoid conversion issues
spark.conf.set("spark.sql.parquet.enableVectorizedReader", "false")

# Enable legacy read mode for timestamps
spark.conf.set("spark.sql.legacy.parquet.datetimeRebaseModeInRead", "CORRECTED")
spark.conf.set("spark.sql.legacy.parquet.int96RebaseModeInRead", "CORRECTED")

# ------------------------------------------------------------------ #
#                  1. define the schema ONCE                         #
# ------------------------------------------------------------------ #
# Define the schema treating 'timestamp' as a string.
schema = T.StructType([
    T.StructField("sensorId",  T.StringType()),
    T.StructField("temperature", T.DoubleType()),
    T.StructField("timestamp",  T.StringType())    # changed field name from timestamp_str to timestamp
])

# ------------------------------------------------------------------ #
#                  2. read the directory as a STREAM                 #
# ------------------------------------------------------------------ #
# Read the directory as a stream with the updated schema.
raw = (
    spark.readStream
         .schema(schema)                     
         .option("basePath", BASE_PATH)      
         .option("maxFilesPerTrigger", 20)   
         .parquet(BRONZE_PATH)
)

# Convert the string field to a proper timestamp.
raw = raw.withColumn("timestamp", F.to_timestamp("timestamp"))

# Debug: add source file info.
debug = raw.withColumn("source_file", F.input_file_name())

# New debug aggregation: number of distinct files and latest reporting time.
debug_agg = debug.agg(
    F.approx_count_distinct("source_file").alias("num_files"),
    F.max("timestamp").alias("latest_report_time")
)
debug_query = (
    debug_agg.writeStream
         .outputMode("complete")
         .format("console")
         .option("truncate", False)
         .trigger(processingTime="1 minute")
         .start()
)

# ------------------------------------------------------------------ #
#                  3. hourly aggregation                             #
# ------------------------------------------------------------------ #
hourly_avg = (
    raw
      .withWatermark("timestamp", "1 minute")  # changed from "1 hour"
      .groupBy(
          F.window("timestamp", "1 hour").alias("hour_window"),
          "sensorId"
      )
      .agg(F.round(F.avg("temperature"), 2).alias("avg_temp"))
      .selectExpr("sensorId",
                  "hour_window.start as hour_start",
                  "avg_temp")
)

# ------------------------------------------------------------------ #
#                  4. write the stream ● to console                  #
# ------------------------------------------------------------------ #
query = (
    hourly_avg
    .writeStream
    .outputMode("update")              # only rows that changed
    .format("console")                 # quick & easy smoke-test
    .option("truncate", False)
    .option("checkpointLocation", CKPT_PATH)
    .trigger(processingTime="1 minute")  # every minute = bounded latency
    .start()
)

query.awaitTermination()
debug_query.awaitTermination()
