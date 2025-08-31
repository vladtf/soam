"""
Pydantic models for the SOAM ingestor API.
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Generic, TypeVar
from datetime import datetime

T = TypeVar('T')


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


class ApiResponse(BaseModel, Generic[T]):
    """Generic API response wrapper."""
    status: str
    data: Optional[T] = None
    message: Optional[str] = None
    error: Optional[str] = None


class ApiListResponse(BaseModel, Generic[T]):
    """Generic API list response wrapper."""
    status: str
    data: List[T]
    total: Optional[int] = None
    page: Optional[int] = None
    page_size: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None


class HealthStatus(BaseModel):
    """Schema for health check response."""
    status: str = Field(..., description="Overall service status")
    components: Dict[str, Any] = Field(..., description="Component health details")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Service metrics")
