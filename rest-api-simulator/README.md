# REST API Simulator

A REST API simulator service for the SOAM Smart City platform that generates mock sensor data and automatically registers itself with the ingestor.

## Features

- **Automatic Registration**: Automatically registers with the ingestor on startup
- **Multiple Sensor Types**: Generates realistic data for:
  - Temperature & Humidity sensors
  - Air Quality sensors (PM2.5, PM10, CO, NO2, O3, AQI)
  - Traffic sensors (vehicle count, speed, congestion)
  - Smart Parking sensors (occupancy, duration)
  - Energy Meters (consumption, voltage, current)
- **RESTful API**: Provides HTTP endpoints for data consumption
- **Continuous Data Generation**: Generates new sensor data every 5 seconds
- **Health Monitoring**: Built-in health check endpoints

## API Endpoints

### Main Data Endpoint (Consumed by Ingestor)
- `GET /api/sensors/all` - Returns recent data from all sensor types (polled by ingestor)

### Individual Sensor Type Endpoints
- `GET /api/sensors/temperature` - Temperature and humidity data
- `GET /api/sensors/air-quality` - Air quality measurements
- `GET /api/sensors/traffic` - Traffic monitoring data
- `GET /api/sensors/parking` - Smart parking data
- `GET /api/sensors/energy` - Energy meter readings

### System Endpoints
- `GET /` - API information and statistics
- `GET /health` - Health check endpoint

## Configuration

The simulator automatically configures itself with the following settings when registering with the ingestor:

```json
{
  "url": "http://rest-api-simulator:8002/api/sensors/all",
  "method": "GET",
  "poll_interval": 30,
  "data_path": "data",
  "headers": {
    "Accept": "application/json",
    "User-Agent": "SOAM-REST-Simulator/1.0"
  }
}
```

## Data Format

All sensor data includes:
- Unique sensor IDs
- Timestamp in ISO format
- Location information
- Status indicators
- Sensor-specific measurements

Example temperature data:
```json
{
  "sensor_id": "temp_sensor_03",
  "temperature": 23.4,
  "humidity": 65.2,
  "timestamp": "2025-09-05T16:30:00Z",
  "location": "Sector 1, Bucharest",
  "battery_level": 87,
  "status": "active"
}
```

## Deployment

The service is automatically deployed as part of the SOAM platform via Skaffold:

```bash
skaffold dev --trigger=polling --watch-poll-interval=5000 --default-repo=localhost:5000/soam
```

## Access

When running with the full SOAM platform:
- **Local Access**: http://localhost:8002
- **Cluster Access**: http://rest-api-simulator:8002 (internal service URL)

## Monitoring

- Check `/health` endpoint for service health
- Monitor ingestor logs to see data ingestion
- View generated data at individual sensor endpoints

## Auto-Registration Process

1. **Startup Delay**: Waits 15 seconds for ingestor to be ready
2. **Registration**: POSTs configuration to ingestor's `/api/data-sources` endpoint
3. **Activation**: Automatically enables the data source for ingestion
4. **Retry Logic**: Retries registration with exponential backoff if ingestor is not ready
5. **Monitoring**: Ingestor begins polling the `/api/sensors/all` endpoint every 30 seconds
