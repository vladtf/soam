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


# Neo4j-specific create payload and response (used by /buildings POST)
class BuildingCreateNeo4j(BaseModel):
    """Create payload for Neo4j-backed buildings endpoint."""
    name: str
    description: str
    street: str
    city: str
    country: str
    lat: float
    lng: float


class BuildingCreateResult(BaseModel):
    """Response shape returned by Neo4j manager when creating a building."""
    status: str
    building: Optional[Dict[str, Any]] = None
    address: Optional[Dict[str, Any]] = None


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
# Devices (Registration)
# ===============================

class DeviceCreate(BaseModel):
    ingestion_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: bool = True

class DeviceResponse(BaseModel):
    id: int
    ingestion_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
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


# ===============================
# Dashboard Tiles (User-defined)
# ===============================

class DashboardTileCreate(BaseModel):
    name: str
    computation_id: int
    viz_type: str  # table | stat | timeseries
    config: Dict[str, Any] = Field(default_factory=dict)
    layout: Optional[Dict[str, Any]] = None
    enabled: bool = True


class DashboardTileUpdate(BaseModel):
    name: Optional[str] = None
    computation_id: Optional[int] = None
    viz_type: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    layout: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class DashboardTileResponse(BaseModel):
    id: int
    name: str
    computation_id: int
    viz_type: str
    config: Dict[str, Any]
    layout: Optional[Dict[str, Any]] = None
    enabled: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ===============================
# Client Error Reporting
# ===============================

class ClientErrorCreate(BaseModel):
    message: str
    stack: Optional[str] = None
    url: Optional[str] = None
    component: Optional[str] = None
    context: Optional[str] = None
    severity: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class ClientErrorResponse(BaseModel):
    id: int
    message: str
    stack: Optional[str] = None
    url: Optional[str] = None
    component: Optional[str] = None
    context: Optional[str] = None
    severity: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None