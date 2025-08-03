from collections import deque
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from src.spark.spark_manager import SparkManager
from src.neo4j.neo4j_manager import Neo4jManager
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

        # Initialize variables
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.getenv("NEO4J_PASSWORD", "verystrongpassword")

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
        
        # Initialize Neo4jManager
        self.neo4j_manager = Neo4jManager(self.neo4j_uri, self.neo4j_user, self.neo4j_password)

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
        self.app.get("/sparkMasterStatus")(self.get_spark_master_status)  # Spark master status endpoint
        self.app.get("/temperatureAlerts")(self.get_temperature_alerts)
        self.app.get("/health")(self.get_health_status)  # Health check endpoint
        self.app.get("/test-spark")(self.test_spark_computation)  # Spark test endpoint
        self.app.get("/test-sensor-data")(self.test_sensor_data_access)  # Sensor data test

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
        
        # Stop Spark streams
        try:
            self.spark_manager.stop_streams()
        except Exception as e:
            logger.error(f"Error stopping Spark streams: {e}")
            
        self.neo4j_manager.close()
        logger.info("Shutdown event completed.")

    def get_average_temperature(self):
        try:
            return self.spark_manager.get_streaming_average_temperature()
        except Exception as e:
            logger.error(f"Error fetching average temperature: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    def get_spark_master_status(self):
        """Get Spark master status including workers and applications"""
        try:
            return self.spark_manager.get_spark_master_status()
        except Exception as e:
            logger.error(f"Error fetching Spark master status: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    def get_temperature_alerts(self, since_minutes=60):
        since_minutes = int(since_minutes)
        try:
            return self.spark_manager.get_temperature_alerts(since_minutes)
        except Exception as e:
            logger.error(f"Error fetching temperature alerts: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    def get_health_status(self):
        """Health check endpoint to monitor system status"""
        try:
            health_status = {
                "status": "healthy",
                "components": {
                    "neo4j": "unknown",
                    "spark": "unknown",
                    "streams": {
                        "temperature": "unknown",
                        "alerts": "unknown"
                    }
                }
            }
            
            # Check Neo4j
            try:
                neo4j_health = self.neo4j_manager.health_check()
                if neo4j_health["status"] == "healthy":
                    health_status["components"]["neo4j"] = "healthy"
                else:
                    health_status["components"]["neo4j"] = f"unhealthy: {neo4j_health['message']}"
                    health_status["status"] = "degraded"
            except Exception as e:
                health_status["components"]["neo4j"] = f"unhealthy: {str(e)}"
                health_status["status"] = "degraded"
            
            # Check Spark
            try:
                if self.spark_manager._check_spark_connection():
                    health_status["components"]["spark"] = "healthy"
                else:
                    health_status["components"]["spark"] = "unhealthy"
                    health_status["status"] = "degraded"
            except Exception as e:
                health_status["components"]["spark"] = f"unhealthy: {str(e)}"
                health_status["status"] = "degraded"
            
            # Check Streams
            try:
                if hasattr(self.spark_manager, 'avg_query') and self.spark_manager.avg_query:
                    health_status["components"]["streams"]["temperature"] = "active" if self.spark_manager.avg_query.isActive else "inactive"
                else:
                    health_status["components"]["streams"]["temperature"] = "not_started"
                    
                if hasattr(self.spark_manager, 'alert_query') and self.spark_manager.alert_query:
                    health_status["components"]["streams"]["alerts"] = "active" if self.spark_manager.alert_query.isActive else "inactive"
                else:
                    health_status["components"]["streams"]["alerts"] = "not_started"
            except Exception as e:
                health_status["components"]["streams"]["temperature"] = f"error: {str(e)}"
                health_status["components"]["streams"]["alerts"] = f"error: {str(e)}"
            
            return health_status
            
        except Exception as e:
            logger.error(f"Error in health check: {str(e)}")
            return {
                "status": "unhealthy", 
                "error": str(e)
            }

    def test_spark_computation(self):
        """Test Spark with a basic computation"""
        try:
            return self.spark_manager.test_spark_basic_computation()
        except Exception as e:
            logger.error(f"Error in Spark computation test: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    def test_sensor_data_access(self):
        """Test Spark access to sensor data"""
        try:
            return self.spark_manager.test_sensor_data_access()
        except Exception as e:
            logger.error(f"Error in sensor data access test: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))


# Instantiate the backend and expose its app
backend = SmartCityBackend()
app = backend.app
