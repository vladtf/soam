#!/usr/bin/env python3
"""
test_spark.py ― sanity-check for the Spark cluster
Calculates π with a Monte-Carlo method.
"""

import random
from pyspark.sql import SparkSession
import os

spark_host = os.environ.get("SPARK_HOST", "localhost")

# point to the master inside Docker compose
spark = (
    SparkSession.builder
    .master(f"spark://{spark_host}:7077")
    .appName("SparkSanityCheck")
    .getOrCreate()
)
sc = spark.sparkContext

NUM_SAMPLES = 1_000_000  # tweak for a longer or shorter run


def inside(_):
    """Return 1 if the random point is inside the unit circle."""
    x, y = random.random(), random.random()
    return 1 if x * x + y * y <= 1 else 0


count = sc.parallelize(range(NUM_SAMPLES)).map(inside).reduce(lambda a, b: a + b)
pi = 4 * count / NUM_SAMPLES

print(f"Pi is roughly {pi}")
spark.stop()
