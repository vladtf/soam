from fastapi import APIRouter, Request
from src.config import ConnectionConfig

def register_routes(app, backend):
    """Register API routes."""
    router = APIRouter()

    @router.get("/data")
    def get_data():
        """Returns the buffered sensor data."""
        return list(backend.data_buffer)

    @router.post("/addConnection")
    async def add_connection(request: Request):
        """Add a new connection configuration."""
        config = await request.json()
        config_id = len(backend.connection_configs) + 1
        new_config = ConnectionConfig(
            id=config_id,
            broker=config.get("broker", "localhost"),
            port=config.get("port", 1883),
            topic=config.get("topic", "smartcity/sensor"),
            connectionType=config.get("connectionType", "mqtt")
        )
        backend.connection_configs.append(new_config)
        if backend.active_connection is None:
            backend.active_connection = new_config
        print("Added connection:", new_config)
        return {"status": "Connection added", "id": config_id}

    @router.post("/switchBroker")
    async def switch_broker(request: Request):
        """Switch the active broker."""
        body = await request.json()
        target_id = body.get("id")
        for config in backend.connection_configs:
            if config.id == target_id:
                backend.active_connection = config
                backend.data_buffer.clear()
                print("Switched active broker to", config)
                return {"status": "Switched to connection", "active": config.__dict__}
        return {"status": "Connection id not found"}

    @router.get("/connections")
    def get_connections():
        """Get all connection configurations."""
        return {
            "connections": [c.__dict__ for c in backend.connection_configs],
            "active": backend.active_connection.__dict__ if backend.active_connection else None
        }

    app.include_router(router)
