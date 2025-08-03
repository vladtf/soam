"""
Pydantic models for the SOAM ingestor API.
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime


class ConnectionConfigCreate(BaseModel):
    """Schema for creating a new connection configuration."""
    broker: str = Field(..., description="MQTT broker hostname or IP")
    port: int = Field(1883, ge=1, le=65535, description="MQTT broker port")
    topic: str = Field(..., description="MQTT topic to subscribe to")
    connectionType: str = Field("mqtt", description="Connection type")


class ConnectionConfig(BaseModel):
    """Schema for connection configuration response."""
    id: int
    broker: str
    port: int
    topic: str
    connectionType: str = "mqtt"


class BrokerSwitchRequest(BaseModel):
    """Schema for switching active broker."""
    id: int = Field(..., description="Connection ID to switch to")


class SensorData(BaseModel):
    """Schema for sensor data."""
    sensorId: str
    temperature: float
    timestamp: datetime
    location: Optional[str] = None


class ConnectionsResponse(BaseModel):
    """Schema for connections list response."""
    status: str
    data: Dict[str, Any]


class ApiResponse(BaseModel):
    """Generic API response wrapper."""
    status: str
    data: Optional[Any] = None
    message: Optional[str] = None
    error: Optional[str] = None


class HealthStatus(BaseModel):
    """Schema for health check response."""
    status: str = Field(..., description="Overall service status")
    components: Dict[str, Any] = Field(..., description="Component health details")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Service metrics")
