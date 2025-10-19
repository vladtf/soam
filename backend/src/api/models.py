"""
Pydantic models for API request/response schemas.
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Generic, TypeVar
from datetime import datetime

# Type variable for generic response types
T = TypeVar('T')


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


class ApiResponse(BaseModel, Generic[T]):
    """
    Standard API response wrapper that matches frontend expectations.
    Used to ensure consistent response structure across all endpoints.
    """
    status: str = Field(..., description="Response status: 'success', 'error', 'warning'")
    data: Optional[T] = Field(None, description="Response data payload")
    message: Optional[str] = Field(None, description="Human-readable message")
    detail: Optional[str] = Field(None, description="Detailed error information")


class ApiListResponse(BaseModel, Generic[T]):
    """
    Standard API response wrapper for list endpoints.
    """
    status: str = Field(..., description="Response status: 'success', 'error', 'warning'")
    data: List[T] = Field(default_factory=list, description="List of response data items")
    total: Optional[int] = Field(None, description="Total number of items available")
    page: Optional[int] = Field(None, description="Current page number (for pagination)")
    page_size: Optional[int] = Field(None, description="Number of items per page")
    message: Optional[str] = Field(None, description="Human-readable message")
    detail: Optional[str] = Field(None, description="Detailed error information")


# ===============================
# Devices (Registration)
# ===============================

class DeviceCreate(BaseModel):
    ingestion_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: bool = True
    created_by: str = Field(..., description="User who created this device")

class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    updated_by: str = Field(..., description="User who updated this device")

class DeviceResponse(BaseModel):
    id: int
    ingestion_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
# ===============================
# Normalization Rules
# ===============================

class NormalizationRuleCreate(BaseModel):
    ingestion_id: Optional[str] = Field(None, description="Specific ingestion source (null = global rule)")
    raw_key: str = Field(..., description="Incoming raw field/column name")
    canonical_key: str = Field(..., description="Canonical field/column name")
    enabled: bool = Field(default=True)
    created_by: str = Field(..., description="Username of the user creating this rule")


class NormalizationRuleUpdate(BaseModel):
    ingestion_id: Optional[str] = Field(None)
    canonical_key: Optional[str] = Field(None)
    enabled: Optional[bool] = Field(None)
    updated_by: str = Field(..., description="Username of the user updating this rule")


class NormalizationRuleResponse(BaseModel):
    id: int
    ingestion_id: Optional[str] = None
    raw_key: str
    canonical_key: str
    enabled: bool
    applied_count: int | None = 0
    last_applied_at: Optional[str] = None
    created_by: str
    updated_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ===============================
# Value Transformation Rules
# ===============================

class ValueTransformationRuleCreate(BaseModel):
    ingestion_id: Optional[str] = Field(None, description="Specific ingestion source (null = global rule)")
    field_name: str = Field(..., description="Field name to apply transformation to")
    transformation_type: str = Field(..., description="Type of transformation: filter, aggregate, convert, validate")
    transformation_config: Dict[str, Any] = Field(..., description="Transformation configuration as JSON")
    order_priority: int = Field(default=100, description="Execution order (lower = earlier)")
    enabled: bool = Field(default=True)
    created_by: str = Field(..., description="Username of the user creating this rule")


class ValueTransformationRuleUpdate(BaseModel):
    ingestion_id: Optional[str] = Field(None)
    field_name: Optional[str] = Field(None)
    transformation_type: Optional[str] = Field(None)
    transformation_config: Optional[Dict[str, Any]] = Field(None)
    order_priority: Optional[int] = Field(None)
    enabled: Optional[bool] = Field(None)
    updated_by: str = Field(..., description="Username of the user updating this rule")


class ValueTransformationRuleResponse(BaseModel):
    id: int
    ingestion_id: Optional[str] = None
    field_name: str
    transformation_type: str
    transformation_config: str  # JSON string for consistency with frontend interface
    order_priority: int
    enabled: bool
    applied_count: int | None = 0
    last_applied_at: Optional[str] = None
    created_by: str
    updated_by: Optional[str] = None
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
    recommended_tile_type: Optional[str] = Field(None, description="Recommended tile type: table | stat | timeseries")
    enabled: bool = True
    created_by: str = Field(..., description="User who created this computation")


class ComputationUpdate(BaseModel):
    description: Optional[str] = None
    dataset: Optional[str] = None
    definition: Optional[Dict[str, Any]] = None
    recommended_tile_type: Optional[str] = None
    enabled: Optional[bool] = None
    updated_by: str = Field(..., description="User who updated this computation")


class ComputationResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    dataset: str
    definition: Dict[str, Any]
    recommended_tile_type: Optional[str] = None
    enabled: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


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
    """Schema for creating a client error."""
    message: str
    stack: Optional[str] = None
    url: Optional[str] = None
    component: Optional[str] = None
    context: Optional[str] = None
    severity: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    extra: Optional[str] = None


class SettingCreate(BaseModel):
    """Schema for creating a setting."""
    key: str
    value: str
    value_type: str = "string"  # string, number, boolean, json
    description: Optional[str] = None
    category: Optional[str] = None
    created_by: str


class SettingUpdate(BaseModel):
    """Schema for updating a setting."""
    value: str
    value_type: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    updated_by: str


class SettingResponse(BaseModel):
    """Schema for setting response."""
    id: int
    key: str
    value: str
    value_type: str
    description: Optional[str]
    category: Optional[str]
    created_by: str
    updated_by: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


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