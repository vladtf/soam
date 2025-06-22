from fastapi import APIRouter, Request, HTTPException
from src.config import ConnectionConfig

def register_routes(app, backend):
    """Register API routes."""
    router = APIRouter()

    @router.get("/data")
    def get_data():
        """Returns the buffered sensor data."""
        try:
            return list(backend.data_buffer)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/addConnection")
    async def add_connection(request: Request):
        """Add a new connection configuration."""
        try:
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
            return {"status": "success", "data": {"id": config_id}}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/switchBroker")
    async def switch_broker(request: Request):
        """Switch the active broker."""
        try:
            body = await request.json()
            target_id = body.get("id")
            for config in backend.connection_configs:
                if config.id == target_id:
                    backend.active_connection = config
                    backend.data_buffer.clear()
                    return {"status": "success", "data": config.__dict__}
            raise KeyError(f"Connection id {target_id} not found")
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/connections")
    def get_connections():
        """Get all connection configurations."""
        try:
            return {
                "status": "success",
                "data": {
                    "connections": [c.__dict__ for c in backend.connection_configs],
                    "active": backend.active_connection.__dict__ if backend.active_connection else None
                }
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    app.include_router(router)
