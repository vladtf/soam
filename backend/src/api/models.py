"""
Pydantic models for API request/response schemas.
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime


class BuildingCreate(BaseModel):
    """Schema for creating a new building."""
    name: str = Field(..., description="Building name")
    location: str = Field(..., description="Building location")
    type: str = Field(..., description="Building type")
    floors: int = Field(..., ge=1, description="Number of floors")
    description: Optional[str] = Field(None, description="Building description")


class Building(BaseModel):
    """Schema for building response."""
    id: str
    name: str
    location: str
    type: str
    floors: int
    description: Optional[str] = None


class BuildingLocation(BaseModel):
    """Schema for building location data from Neo4j."""
    name: str
    lat: float
    lng: float


class HealthStatus(BaseModel):
    """Schema for health check response."""
    status: str = Field(..., description="Overall system status")
    components: Dict[str, Any] = Field(..., description="Component health details")


class TemperatureAlert(BaseModel):
    """Schema for temperature alert."""
    sensorId: str
    temperature: float
    event_time: datetime
    alert_type: str


class TemperatureReading(BaseModel):
    """Schema for temperature reading."""
    sensorId: str
    time_start: datetime
    avg_temp: float


class SparkTestResult(BaseModel):
    """Schema for Spark test results."""
    status: str
    message: str
    results: Optional[Dict[str, Any]] = None


class ApiResponse(BaseModel):
    """Generic API response wrapper."""
    status: str
    data: Optional[Any] = None
    message: Optional[str] = None
    error: Optional[str] = None


# ===============================
# Normalization Rules
# ===============================

class NormalizationRuleCreate(BaseModel):
    raw_key: str = Field(..., description="Incoming raw field/column name")
    canonical_key: str = Field(..., description="Canonical field/column name")
    enabled: bool = Field(default=True)


class NormalizationRuleUpdate(BaseModel):
    canonical_key: Optional[str] = Field(None)
    enabled: Optional[bool] = Field(None)


class NormalizationRuleResponse(BaseModel):
    id: int
    raw_key: str
    canonical_key: str
    enabled: bool
    applied_count: int | None = 0
    last_applied_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class FeedbackCreate(BaseModel):
    """Schema for creating feedback."""
    email: str = Field(..., description="User email address")
    message: str = Field(..., description="Feedback message")


class FeedbackResponse(BaseModel):
    """Schema for feedback response."""
    id: int
    email: str
    message: str
    created_at: str


# ===============================
# Computations (User-defined)
# ===============================

class ComputationCreate(BaseModel):
    name: str
    description: Optional[str] = None
    dataset: str = Field(..., description="Target dataset: silver | alerts | sensors")
    definition: Dict[str, Any] = Field(..., description="JSON computation definition")
    enabled: bool = True


class ComputationUpdate(BaseModel):
    description: Optional[str] = None
    dataset: Optional[str] = None
    definition: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class ComputationResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    dataset: str
    definition: Dict[str, Any]
    enabled: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
