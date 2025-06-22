from collections import deque
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from src.spark_manager import SparkManager
from src.neo4j_manager import Neo4jManager
from fastapi.exceptions import HTTPException
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("backend.log")
    ]
)

logger = logging.getLogger(__name__)


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
        
        # Initialize Neo4jManager
        self.neo4j_manager = Neo4jManager(self.neo4j_uri, self.neo4j_user, self.neo4j_password)
        self.spark_host = os.getenv("SPARK_HOST", "localhost")
        self.spark_port = os.getenv("SPARK_PORT", "7077")
        self.minio_endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
        self.minio_access_key = os.getenv("MINIO_ACCESS_KEY", "minio")
        self.minio_secret_key = os.getenv("MINIO_SECRET_KEY", "minio123")
        self.minio_bucket = os.getenv("MINIO_BUCKET", "lake")
        self.spark_history = os.getenv("SPARK_HISTORY", "http://spark-history:18080")
        
        # Initialize SparkManager in the constructor
        self.spark_manager = SparkManager(
            self.spark_host,
            self.spark_port,
            self.minio_endpoint,
            self.minio_access_key,
            self.minio_secret_key,
            self.minio_bucket,
            self.spark_history,
        )

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
        self.app.post("/buildings")(self.add_building)  # new endpoint to add a building
        self.app.get("/averageTemperature")(self.get_average_temperature)  # Register new route
        self.app.get("/runningSparkJobs")(self.get_running_spark_jobs)  # Register the new route
        self.app.get("/temperatureAlerts")(self.get_temperature_alerts)

        # Provision Neo4j with initial data from utils.txt
        self.neo4j_manager.provision_data()

        # Register shutdown event to gracefully close
        self.app.on_event("shutdown")(self.shutdown_event)

    def get_buildings(self):
        try:
            return self.neo4j_manager.get_buildings()
        except Exception as e:
            logger.error(f"Error fetching buildings: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def add_building(self, request: Request):
        data = await request.json()
        try:
            return self.neo4j_manager.add_building(data)
        except KeyError as e:
            logger.error(f"Missing field in add_building: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Missing field: {str(e)}")
        except Exception as e:
            logger.error(f"Error adding building: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def shutdown_event(self):
        # Stop and join all threads stored in the map
        for key, thread in self.threads.items():
            if thread.is_alive():
                thread.join(timeout=5)  # join with timeout for safety
        self.neo4j_manager.close()
        logger.info("Shutdown event completed.")

    def get_average_temperature(self):
        try:
            return self.spark_manager.get_streaming_average_temperature()
        except Exception as e:
            logger.error(f"Error fetching average temperature: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    def get_running_spark_jobs(self):
        try:
            return self.spark_manager.get_running_spark_jobs()
        except Exception as e:
            logger.error(f"Error fetching running Spark jobs: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    def get_temperature_alerts(self, since_minutes=60):
        since_minutes = int(since_minutes)
        try:
            return self.spark_manager.get_temperature_alerts(since_minutes)
        except Exception as e:
            logger.error(f"Error fetching temperature alerts: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))


# Instantiate the backend and expose its app
backend = SmartCityBackend()
app = backend.app
