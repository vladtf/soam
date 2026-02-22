# CoAP Sensor Simulator

A CoAP server that simulates IoT sensors for the SOAM Smart City Platform.

## Sensors

| Resource | Description | Key Fields |
|---|---|---|
| `/sensors/parking` | Parking occupancy | zone, total/occupied/available spots, occupancy rate |
| `/sensors/noise` | Environmental noise | location, noise_level_db, peak_db, classification |

## Usage

### Run locally

```bash
pip install -r requirements.txt
python server.py
```

### Test with CoAP client

```bash
# GET a single reading
aiocoap-client coap://localhost:5683/sensors/parking

# Observe (receive push notifications)
aiocoap-client coap://localhost:5683/sensors/parking --observe

# Resource discovery
aiocoap-client coap://localhost:5683/.well-known/core
```

### Connect the ingestor

Register a CoAP data source via the frontend or API:

```json
{
  "name": "CoAP Parking Sensor",
  "type_name": "coap",
  "config": {
    "host": "coap-simulator",
    "port": 5683,
    "resources": ["/sensors/parking", "/sensors/noise"],
    "mode": "observe"
  }
}
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `COAP_PORT` | `5683` | UDP port to listen on |
| `COAP_UPDATE_INTERVAL` | `10` | Seconds between sensor readings |
