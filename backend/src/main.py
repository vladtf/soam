import datetime
import io
import json
import threading
from collections import deque
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from minio import S3Error
import os
from dataclasses import dataclass
import asyncio
from neo4j import GraphDatabase
import logging
from pyspark.sql import SparkSession, functions as F  # Import Spark libraries
import requests  # Add this import for making HTTP requests




class SmartCityBackend:
    def __init__(self):
        self.app = FastAPI()
        self.data_buffer = deque(maxlen=100)  # Buffer to store the last 100 messages
        self.connection_configs = []          # List of connection configs
        self.active_connection = None         # Active connection config
        self.threads = {}                     # Map to store threads for later shutdown
        self.thread_counter = 1               # Counter for unique thread keys
        self.last_connection_error = None
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "verystrongpassword")
        self.neo4j_driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password))  # new driver initialization
        self.spark_host = os.getenv("SPARK_HOST", "localhost")
        self.spark_port = os.getenv("SPARK_PORT", "7077")
        self.minio_endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
        self.minio_access_key = os.getenv("MINIO_ACCESS_KEY", "minio")
        self.minio_secret_key = os.getenv("MINIO_SECRET_KEY", "minio123")
        self.minio_bucket = os.getenv("MINIO_BUCKET", "lake")
        

        # Enable CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )


        # Register routes
        self.app.get("/buildings")(self.get_buildings)  # new route to fetch buildings
        self.app.post("/addBuilding")(self.add_building)  # new endpoint to add a building
        self.app.get("/averageTemperature")(self.get_average_temperature)  # Register new route
        self.app.get("/runningSparkJobs")(self.get_running_spark_jobs)  # Register the new route

        # Provision Neo4j with initial data from utils.txt
        self.provision_data()

        # Register shutdown event to gracefully close
        self.app.on_event("shutdown")(self.shutdown_event)

    def get_buildings(self):
        """Query Neo4j for all buildings with their address coordinates."""
        query = """
        MATCH (b:Building)-[:hasAddress]->(a:Address)
        RETURN b.name AS name, a.location.latitude AS lat, a.location.longitude AS lng
        """
        with self.neo4j_driver.session() as session:
            result = session.run(query)
            buildings = [{"name": record["name"], "lat": record["lat"], "lng": record["lng"]} for record in result]

        logging.info("Fetched buildings from Neo4j. Count: %s", len(buildings))
        return buildings

    async def add_building(self, request: Request):
        # Extract building and address details from the request
        data = await request.json()
        try:
            name = data["name"]
            description = data.get("description", "")
            street = data["street"]
            city = data["city"]
            country = data["country"]
            lat = data["lat"]
            lng = data["lng"]
        except KeyError as e:
            return {"status": "error", "detail": f"Missing field: {str(e)}"}

        query = """
        MERGE (b:Building { name: $name })
        SET b.description = $description
        MERGE (a:Address { street: $street, city: $city, country: $country })
        SET a.location = point({ latitude: $lat, longitude: $lng })
        MERGE (b)-[:hasAddress]->(a)
        RETURN b, a
        """
        try:
            with self.neo4j_driver.session() as session:
                result = session.run(query, name=name, description=description,
                                     street=street, city=city, country=country,
                                     lat=lat, lng=lng)
                record = result.single()
                if record is None:
                    return {"status": "No building added"}
                # Return simplified representations of the nodes
                b = record["b"]
                a = record["a"]
                return {"status": "Building added", "building": dict(b), "address": dict(a)}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    def provision_data(self):
        # Pre-provision data from utils.txt (excluding clear and show queries)
        queries = [
            """
            MERGE (sc:SmartCity { name: "Metropolis", description: "A smart city leveraging technology to improve quality of life." })
            """,
            """
            MERGE (corp_ec:Building { name: "Corp EC", description: "The central administrative building." })
            """,
            """
            MERGE (corp_ed:Building { name: "Corp ED", description: "The central administrative building." })
            """,
            """
            MERGE (c_precis:Building { name: "Centrul PRECIS", description: "The central administrative building." })
            """,
            """
            MERGE (a_corp_ec:Address { street: "Splaiul Independenței, 313", city: "Bucharest", country: "Romania",
                                         location: point({latitude: 44.435907, longitude: 26.047295}) })
            """,
            """
            MERGE (a_corp_ed:Address { street: "Splaiul Independenței, 313", city: "Bucharest", country: "Romania",
                                         location: point({latitude: 44.435751, longitude: 26.048120}) })
            """,
            """
            MERGE (a_c_precis:Address { street: "Splaiul Independenței, 313", city: "Bucharest", country: "Romania",
                                         location: point({latitude: 44.435013, longitude: 26.047758}) })
            """,
            """
            MERGE (s:Sensor { sensorId: "Sensor123", measurementTime: datetime("2023-10-14T12:00:00"),
                               temperature: 22.5, humidity: 45.0 })
            """,
            """
            MATCH (b:Building), (a:Address)
            WHERE b.name = "Corp EC" AND a.street = "Splaiul Independenței, 313"
            MERGE (b)-[:hasAddress]->(a)
            """,
            """
            MATCH (b:Building), (a:Address)
            WHERE b.name = "Corp ED" AND a.street = "Splaiul Independenței, 313"
            MERGE (b)-[:hasAddress]->(a)
            """,
            """
            MATCH (b:Building), (a:Address)
            WHERE b.name = "Centrul PRECIS" AND a.street = "Splaiul Independenței, 313"
            MERGE (b)-[:hasAddress]->(a)
            """,
            """
            MATCH (sc:SmartCity), (s:Sensor)
            WHERE sc.name = "Metropolis" AND s.sensorId = "Sensor123"
            MERGE (sc)-[:hasSensor]->(s)
            """,
            """
            MATCH (s:Sensor), (b:Building)
            WHERE s.sensorId = "Sensor123" AND b.name = "Corp EC"
            MERGE (s)-[:locatedIn]->(b)
            """
        ]
        try:
            with self.neo4j_driver.session() as session:
                for query in queries:
                    session.run(query)
            print("Provisioned initial data to Neo4j.")
        except Exception as e:
            print("Error provisioning Neo4j data:", e)

    async def shutdown_event(self):
        # Stop and join all threads stored in the map
        for key, thread in self.threads.items():
            if thread.is_alive():
                thread.join(timeout=5)  # join with timeout for safety
        print("Shutdown event triggered")

    def get_average_temperature(self):
        """Calculate the average temperature from sensor data in MinIO."""
        try:
            # Initialize Spark session
            spark = (
                SparkSession.builder
                .appName("SmartCityBackend")
                .master(f"spark://{self.spark_host}:{self.spark_port}")

                # ---- MinIO (S3A) -------------------------------------------------
                .config("spark.eventLog.enabled", "true")
                .config("spark.hadoop.fs.s3a.endpoint", f"http://{self.minio_endpoint}")
                .config("spark.hadoop.fs.s3a.path.style.access", "true")
                .config("spark.hadoop.fs.s3a.access.key", self.minio_access_key)
                .config("spark.hadoop.fs.s3a.secret.key", self.minio_secret_key)
                .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")

                # ---- Extra jars: Delta + S3A ------------------------------------
                .config(
                    "spark.jars.packages",
                    ",".join([
                        "io.delta:delta-spark_2.12:3.1.0",
                        "org.apache.hadoop:hadoop-aws:3.3.4",
                        "com.amazonaws:aws-java-sdk-bundle:1.12.620",
                    ])  # TODO: to move this to dockerfile
                )
                .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
                .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
                .getOrCreate()
            )

            spark.sparkContext.setLogLevel("DEBUG")  # Set log level to ERROR

            # Read data from MinIO
            df = (
                spark.read.option("basePath", f"s3a://{self.minio_bucket}/sensors/")
                .parquet(f"s3a://{self.minio_bucket}/sensors/date=*/hour=*")
            )
            hourly_avg = (
                df.withColumn("date", F.to_date("timestamp"))
                .withColumn("hour", F.hour("timestamp"))
                .groupBy("date", "hour")
                .agg(F.avg("temperature").alias("avg_temp"))
                .orderBy("date", "hour")
            )

            response = hourly_avg.collect()  # Collect the results to a list

            # Convert to a list of dictionaries for easier JSON serialization
            response = [
                {"date": row["date"], "hour": row["hour"], "avg_temp": row["avg_temp"]}
                for row in response
            ]

            spark.stop()  # Stop Spark session after use

            return {"status": "success", "data": response}
        except Exception as e:
            print("Error calculating average temperature:", e)
            return {"status": "error", "detail": str(e)}

    def get_running_spark_jobs(self):
        """
        Return jobs whose latest stage is RUNNING as reported by the History-Server.
        History UI is mapped to http://localhost:18080 in docker-compose.yml
        """
        try:
            base = "http://spark-history:18080/api/v1/applications"
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
        except ValueError as e:          # .json() failed → not JSON
            return {"status": "error", "detail": f"Bad JSON: {e}"}


# Instantiate the backend and expose its app
backend = SmartCityBackend()
app = backend.app
