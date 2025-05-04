#!/usr/bin/env python3
'''
Smoke test for the rate stream source.

docker cp rate_stream.py soam-backend:/tmp/rate_stream.py && \
docker exec -it soam-backend python /tmp/rate_stream.py
'''

from pyspark.sql import SparkSession

spark = (SparkSession
         .builder
         .appName("Rate-stream smoke-test")
         .master("spark://spark-master:7077")   # the service name in compose
         .getOrCreate())

spark.sparkContext.setLogLevel("WARN")          # keep the log quiet

rate_df = (spark
           .readStream
           .format("rate")          # built-in generator source
           .option("rowsPerSecond", 5)
           .load())

result = rate_df.groupBy().count()              # single global count

query = (result
         .writeStream
         .outputMode("complete")    # so the single row is overwritten each batch
         .format("console")         # prints to driver stdout
         .option("truncate", False)
         .trigger(processingTime="10 seconds")
         .start())

query.awaitTermination()
