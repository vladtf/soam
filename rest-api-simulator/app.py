"""
REST API Simulator for SOAM Smart City Platform.

This service provides mock sensor data endpoints that can be consumed by the ingestor
and automatically registers itself with the ingestor on startup.
"""
import asyncio
import logging
import random
import json
from datetime import datetime, timezone
from typing import Dict, Any, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import httpx
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
INGESTOR_URL = "http://ingestor:8001"  # Internal service URL
SIMULATOR_URL = "http://rest-api-simulator:8002"  # This service's URL
POLL_INTERVAL = 30  # seconds


class SensorDataGenerator:
    """Generates realistic sensor data for different sensor types."""
    
    @staticmethod
    def generate_temperature_data() -> Dict[str, Any]:
        """Generate temperature sensor data."""
        return {
            "sensor_id": f"temp_sensor_{random.randint(1, 10):02d}",
            "temperature": round(random.uniform(15.0, 35.0), 2),
            "humidity": round(random.uniform(30.0, 90.0), 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": random.choice([
                "Sector 1, Bucharest", "Sector 2, Bucharest", "Sector 3, Bucharest",
                "City Center", "Industrial District", "Residential Area"
            ]),
            "battery_level": random.randint(70, 100),
            "status": "active"
        }
    
    @staticmethod
    def generate_air_quality_data() -> Dict[str, Any]:
        """Generate air quality sensor data."""
        return {
            "sensor_id": f"air_quality_{random.randint(1, 8):02d}",
            "pm25": round(random.uniform(5.0, 50.0), 2),
            "pm10": round(random.uniform(10.0, 80.0), 2),
            "co": round(random.uniform(0.1, 5.0), 2),
            "no2": round(random.uniform(5.0, 40.0), 2),
            "o3": round(random.uniform(20.0, 150.0), 2),
            "aqi": random.randint(20, 150),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "location": random.choice([
                "Traffic Junction A", "Park Central", "Industrial Zone B",
                "Residential Complex C", "Highway Monitor D"
            ]),
            "status": "operational"
        }
    
    @staticmethod
    def generate_traffic_data() -> Dict[str, Any]:
        """Generate traffic monitoring data."""
        return {
            "sensor_id": f"traffic_sensor_{random.randint(1, 15):02d}",
            "vehicle_count": random.randint(0, 150),
            "average_speed": round(random.uniform(10.0, 80.0), 1),
            "congestion_level": random.choice(["low", "moderate", "high", "critical"]),
            "road_segment": random.choice([
                "Highway A1 - Km 45", "Main Street - Block 12", "Ring Road - Sector 3",
                "Boulevard Magheru", "Calea Victoriei", "Strada Lipscani"
            ]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "incident_detected": random.choice([True, False]) if random.random() < 0.1 else False,
            "weather_condition": random.choice(["clear", "rain", "fog", "snow"])
        }
    
    @staticmethod
    def generate_smart_parking_data() -> Dict[str, Any]:
        """Generate smart parking sensor data."""
        return {
            "sensor_id": f"parking_sensor_{random.randint(1, 20):02d}",
            "occupied_spots": random.randint(0, 100),
            "total_spots": 100,
            "occupancy_rate": round(random.uniform(0.0, 1.0), 2),
            "average_duration_minutes": random.randint(30, 240),
            "location": random.choice([
                "Mall Parking Lot A", "City Center Garage", "Airport Terminal 1",
                "Hospital Parking", "University Campus", "Shopping District"
            ]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payment_system_status": "operational",
            "peak_hours": datetime.now().hour in [8, 9, 17, 18, 19]
        }
    
    @staticmethod
    def generate_energy_meter_data() -> Dict[str, Any]:
        """Generate smart energy meter data."""
        base_consumption = random.uniform(100.0, 500.0)
        return {
            "meter_id": f"energy_meter_{random.randint(1, 50):03d}",
            "current_consumption_kw": round(base_consumption, 2),
            "daily_consumption_kwh": round(base_consumption * 24, 1),
            "voltage": round(random.uniform(220.0, 240.0), 1),
            "current": round(base_consumption / 230.0, 2),
            "power_factor": round(random.uniform(0.85, 0.95), 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "building_type": random.choice([
                "residential", "commercial", "industrial", "public_building"
            ]),
            "grid_frequency": round(random.uniform(49.8, 50.2), 1),
            "status": "online"
        }


# Global data store
class DataStore:
    """In-memory data store for sensor readings."""
    
    def __init__(self):
        self.data: Dict[str, List[Dict[str, Any]]] = {
            "temperature": [],
            "air_quality": [],
            "traffic": [],
            "parking": [],
            "energy": []
        }
        self.max_records_per_type = 100
        
    def add_data(self, data_type: str, record: Dict[str, Any]):
        """Add a new record to the data store."""
        if data_type not in self.data:
            self.data[data_type] = []
            
        self.data[data_type].append(record)
        
        # Keep only the most recent records
        if len(self.data[data_type]) > self.max_records_per_type:
            self.data[data_type] = self.data[data_type][-self.max_records_per_type:]
    
    def get_recent_data(self, data_type: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent records of a specific type."""
        return self.data.get(data_type, [])[-limit:]
    
    def get_all_recent_data(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent records from all sensor types."""
        all_records = []
        for records in self.data.values():
            all_records.extend(records[-limit//5:])  # Distribute evenly
        
        # Sort by timestamp and return most recent
        all_records.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return all_records[:limit]


# Initialize data store
data_store = DataStore()


async def generate_sensor_data():
    """Continuously generate and store sensor data."""
    generators = {
        "temperature": SensorDataGenerator.generate_temperature_data,
        "air_quality": SensorDataGenerator.generate_air_quality_data,
        "traffic": SensorDataGenerator.generate_traffic_data,
        "parking": SensorDataGenerator.generate_smart_parking_data,
        "energy": SensorDataGenerator.generate_energy_meter_data
    }
    
    while True:
        try:
            # Generate data for each sensor type
            for data_type, generator in generators.items():
                # Generate 1-3 records per type each cycle
                num_records = random.randint(1, 3)
                for _ in range(num_records):
                    record = generator()
                    data_store.add_data(data_type, record)
            
            logger.debug("Generated new sensor data batch")
            await asyncio.sleep(5)  # Generate new data every 5 seconds
            
        except Exception as e:
            logger.error(f"Error generating sensor data: {e}")
            await asyncio.sleep(10)


async def register_with_ingestor():
    """Register this REST API simulator with the ingestor."""
    max_retries = 10
    retry_delay = 15
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to register with ingestor (attempt {attempt + 1}/{max_retries})...")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Configuration for the REST API data source
                config = {
                    "url": f"{SIMULATOR_URL}/api/sensors/all",
                    "method": "GET",
                    "poll_interval": POLL_INTERVAL,
                    "data_path": "data",  # Extract records from "data" array
                    "headers": {
                        "Accept": "application/json",
                        "User-Agent": "SOAM-REST-Simulator/1.0"
                    }
                }
                
                # Registration payload
                registration_data = {
                    "name": "Smart City REST API Simulator",
                    "type_name": "rest_api",
                    "config": config,
                    "created_by": "rest_api_simulator_auto_register"
                }
                
                response = await client.post(
                    f"{INGESTOR_URL}/api/data-sources",
                    json=registration_data
                )
                
                if response.status_code in [200, 201]:
                    result = response.json()
                    logger.info(f"✅ Successfully registered with ingestor: ID {result.get('data', {}).get('id')}")
                    
                    # Enable the data source
                    source_id = result.get('data', {}).get('id')
                    if source_id:
                        enable_response = await client.post(
                            f"{INGESTOR_URL}/api/data-sources/{source_id}/start"
                        )
                        if enable_response.status_code == 200:
                            logger.info("✅ Successfully enabled data source in ingestor")
                        else:
                            logger.warning(f"⚠️ Failed to enable data source: {enable_response.status_code}")
                    
                    return True
                    
                elif response.status_code == 409:
                    logger.info("ℹ️ Data source already exists, attempting to enable it")
                    # Try to find and enable existing source
                    sources_response = await client.get(f"{INGESTOR_URL}/api/data-sources")
                    if sources_response.status_code == 200:
                        sources = sources_response.json().get('data', [])
                        existing_source = next(
                            (s for s in sources if s['name'] == 'Smart City REST API Simulator'),
                            None
                        )
                        if existing_source:
                            source_id = existing_source['id']
                            enable_response = await client.post(f"{INGESTOR_URL}/api/data-sources/{source_id}/start")
                            if enable_response.status_code == 200:
                                logger.info("✅ Successfully enabled existing data source")
                                return True
                    
                else:
                    logger.error(f"❌ Registration failed with status {response.status_code}: {response.text}")
                    
        except Exception as e:
            logger.error(f"❌ Registration attempt {attempt + 1} failed: {e}")
        
        if attempt < max_retries - 1:
            logger.info(f"⏳ Retrying in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 1.5, 30)  # Exponential backoff
    
    logger.error("❌ Failed to register with ingestor after all attempts")
    return False


async def delayed_registration():
    """Handle registration with a delay to ensure HTTP server is ready."""
    # Wait a bit for the HTTP server to be fully ready
    await asyncio.sleep(15)
    logger.info("🔗 Starting delayed registration process...")
    await register_with_ingestor()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("🚀 Starting REST API Simulator...")
    
    # Start background data generation
    data_task = asyncio.create_task(generate_sensor_data())
    
    # Start registration process in background (non-blocking)
    registration_task = asyncio.create_task(delayed_registration())
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down REST API Simulator...")
    data_task.cancel()
    registration_task.cancel()
    try:
        await data_task
    except asyncio.CancelledError:
        pass
    try:
        await registration_task
    except asyncio.CancelledError:
        pass


# Create FastAPI app
app = FastAPI(
    title="SOAM REST API Simulator",
    description="Mock sensor data REST API for the Smart City platform",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "SOAM REST API Simulator",
        "version": "1.0.0",
        "description": "Mock sensor data REST API for testing and development",
        "endpoints": {
            "all_sensors": "/api/sensors/all",
            "temperature": "/api/sensors/temperature",
            "air_quality": "/api/sensors/air-quality",
            "traffic": "/api/sensors/traffic",
            "parking": "/api/sensors/parking",
            "energy": "/api/sensors/energy",
            "health": "/health"
        },
        "total_records": sum(len(records) for records in data_store.data.values())
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data_types_available": list(data_store.data.keys()),
        "total_records": sum(len(records) for records in data_store.data.values())
    }


@app.get("/api/sensors/all")
async def get_all_sensors(limit: int = 20):
    """Get recent data from all sensor types - Main endpoint consumed by ingestor."""
    try:
        data = data_store.get_all_recent_data(limit)
        return {
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "count": len(data),
            "data": data  # This matches the "data_path": "data" in ingestor config
        }
    except Exception as e:
        logger.error(f"Error retrieving all sensor data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sensors/temperature")
async def get_temperature_data(limit: int = 10):
    """Get recent temperature sensor data."""
    data = data_store.get_recent_data("temperature", limit)
    return {
        "status": "success",
        "sensor_type": "temperature",
        "count": len(data),
        "data": data
    }


@app.get("/api/sensors/air-quality") 
async def get_air_quality_data(limit: int = 10):
    """Get recent air quality sensor data."""
    data = data_store.get_recent_data("air_quality", limit)
    return {
        "status": "success",
        "sensor_type": "air_quality",
        "count": len(data),
        "data": data
    }


@app.get("/api/sensors/traffic")
async def get_traffic_data(limit: int = 10):
    """Get recent traffic sensor data."""
    data = data_store.get_recent_data("traffic", limit)
    return {
        "status": "success",
        "sensor_type": "traffic", 
        "count": len(data),
        "data": data
    }


@app.get("/api/sensors/parking")
async def get_parking_data(limit: int = 10):
    """Get recent parking sensor data."""
    data = data_store.get_recent_data("parking", limit)
    return {
        "status": "success",
        "sensor_type": "parking",
        "count": len(data), 
        "data": data
    }


@app.get("/api/sensors/energy")
async def get_energy_data(limit: int = 10):
    """Get recent energy meter data."""
    data = data_store.get_recent_data("energy", limit)
    return {
        "status": "success",
        "sensor_type": "energy",
        "count": len(data),
        "data": data
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
