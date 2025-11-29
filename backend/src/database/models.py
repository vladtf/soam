"""
SQLAlchemy models for application storage.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, UniqueConstraint, Float, JSON, Enum as SAEnum
from sqlalchemy.sql import func
from src.database.database import Base
import enum


class UserRole(str, enum.Enum):
    """User role enumeration for RBAC."""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    # Roles stored as JSON list of role values, e.g. ["admin", "user"]
    roles = Column(JSON, default=["user"], nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def get_roles(self) -> list:
        """Get list of UserRole enums from stored roles."""
        if not self.roles:
            return []
        return [UserRole(r) for r in self.roles if r in [e.value for e in UserRole]]

    def has_role(self, role: UserRole) -> bool:
        """Check if user has a specific role."""
        return role.value in (self.roles or [])

    def has_any_role(self, roles: list) -> bool:
        """Check if user has any of the specified roles."""
        role_values = [r.value if isinstance(r, UserRole) else r for r in roles]
        return any(r in (self.roles or []) for r in role_values)

    def to_dict(self) -> dict:
        """Convert the model to a dictionary (excludes password_hash)."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "roles": self.roles or [],
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Feedback(Base):
    """Feedback model for storing user feedback and bug reports."""
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def to_dict(self) -> dict:
        """Convert the model to a dictionary."""
        return {
            "id": self.id,
            "email": self.email,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class NormalizationRule(Base):
    """User-defined normalization rule for mapping raw keys to canonical names."""
    __tablename__ = "normalization_rules"

    id = Column(Integer, primary_key=True, index=True)
    ingestion_id = Column(String(255), nullable=True, index=True)  # NULL = global rule
    raw_key = Column(String(255), nullable=False, index=True)  # incoming raw column/key (case-insensitive)
    canonical_key = Column(String(255), nullable=False)         # target canonical column name
    enabled = Column(Boolean, nullable=False, default=True)
    applied_count = Column(Integer, nullable=False, server_default="0")
    last_applied_at = Column(DateTime(timezone=True), nullable=True)
    
    # Ownership and audit fields
    created_by = Column(String(255), nullable=False)  # User who created the rule
    updated_by = Column(String(255), nullable=True)   # User who last updated the rule
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ingestion_id": self.ingestion_id,
            "raw_key": self.raw_key,
            "canonical_key": self.canonical_key,
            "enabled": self.enabled,
            "applied_count": getattr(self, "applied_count", 0),
            "last_applied_at": self.last_applied_at.isoformat() if getattr(self, "last_applied_at", None) else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ValueTransformationRule(Base):
    """User-defined value transformation rule for filtering, aggregating, and modifying data values before processing."""
    __tablename__ = "value_transformation_rules"

    id = Column(Integer, primary_key=True, index=True)
    ingestion_id = Column(String(255), nullable=True, index=True)  # NULL = global rule
    field_name = Column(String(255), nullable=False, index=True)   # Field to apply transformation to
    transformation_type = Column(String(64), nullable=False)       # 'filter', 'aggregate', 'convert', 'validate'
    transformation_config = Column(Text, nullable=False)           # JSON config for the transformation
    order_priority = Column(Integer, nullable=False, default=100)  # Execution order (lower = earlier)
    enabled = Column(Boolean, nullable=False, default=True)
    applied_count = Column(Integer, nullable=False, server_default="0")
    last_applied_at = Column(DateTime(timezone=True), nullable=True)
    
    # Ownership and audit fields
    created_by = Column(String(255), nullable=False)
    updated_by = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ingestion_id": self.ingestion_id,
            "field_name": self.field_name,
            "transformation_type": self.transformation_type,
            "transformation_config": self.transformation_config,
            "order_priority": self.order_priority,
            "enabled": self.enabled,
            "applied_count": getattr(self, "applied_count", 0),
            "last_applied_at": self.last_applied_at.isoformat() if getattr(self, "last_applied_at", None) else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Computation(Base):
    """User-defined computation stored as a JSON definition."""
    __tablename__ = "computations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    dataset = Column(String(64), nullable=False)  # e.g., 'silver', 'alerts', 'sensors'
    definition = Column(Text, nullable=False)     # JSON string of the computation definition
    recommended_tile_type = Column(String(32), nullable=True)  # 'table', 'stat', 'timeseries'
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Ownership tracking
    created_by = Column(String(255), nullable=False)
    updated_by = Column(String(255), nullable=True)

    def to_dict(self) -> dict:
        import json as _json
        try:
            parsed_def = _json.loads(self.definition) if isinstance(self.definition, str) else (self.definition or {})
        except Exception:
            parsed_def = {}
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "dataset": self.dataset,
            "definition": parsed_def,
            "recommended_tile_type": self.recommended_tile_type,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": getattr(self, "created_by", "unknown"),
            "updated_by": getattr(self, "updated_by", None),
        }


class DashboardTile(Base):
    """User-defined dashboard tile configuration persisted in DB."""
    __tablename__ = "dashboard_tiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    computation_id = Column(Integer, nullable=False)
    viz_type = Column(String(64), nullable=False)  # table | stat | timeseries
    config = Column(Text, nullable=False)          # JSON
    layout = Column(Text, nullable=True)           # JSON (x,y,w,h) optional
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        import json as _json
        try:
            cfg = _json.loads(self.config) if isinstance(self.config, str) else (self.config or {})
        except Exception:
            cfg = {}
        try:
            lay = _json.loads(self.layout) if isinstance(self.layout, str) else (self.layout or None)
        except Exception:
            lay = None
        return {
            "id": self.id,
            "name": self.name,
            "computation_id": self.computation_id,
            "viz_type": self.viz_type,
            "config": cfg,
            "layout": lay,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Device(Base):
    """Registered device allowed for enrichment and downstream processing."""
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint('ingestion_id', name='uq_device_ingestion'),
    )

    id = Column(Integer, primary_key=True, index=True)
    ingestion_id = Column(String(255), nullable=True)
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Ownership tracking
    created_by = Column(String(255), nullable=False)
    updated_by = Column(String(255), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ingestion_id": self.ingestion_id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": getattr(self, "created_by", "unknown"),
            "updated_by": getattr(self, "updated_by", None),
        }


class ValueTypeEnum(enum.Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    JSON = "json"

class Setting(Base):
    """Application settings and configuration values."""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), nullable=False, unique=True, index=True)  # Setting key (e.g., 'temperature_threshold')
    value = Column(String(1024), nullable=False)  # Setting value as string; type conversion handled by manager
    value_type = Column(SAEnum(ValueTypeEnum), nullable=False, default=ValueTypeEnum.STRING)  # Type: string, number, boolean, json
    description = Column(Text, nullable=True)  # Human-readable description
    category = Column(String(100), nullable=True)  # Category for grouping (e.g., 'alerts', 'thresholds')
    
    # Ownership and audit fields
    created_by = Column(String(255), nullable=False)
    updated_by = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "value_type": self.value_type.value if self.value_type else None,
            "description": self.description,
            "category": self.category,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def get_typed_value(self):
        """Return the value in its native type (JSON column handles conversion)."""
        return self.value


class ClientError(Base):
    """Client-side error/event reported from the frontend."""
    __tablename__ = "client_errors"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    stack = Column(Text, nullable=True)
    url = Column(Text, nullable=True)
    component = Column(String(255), nullable=True)
    context = Column(String(255), nullable=True)
    severity = Column(String(32), nullable=True)
    user_agent = Column(Text, nullable=True)
    session_id = Column(String(128), nullable=True)
    extra = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "message": self.message,
            "stack": self.stack,
            "url": self.url,
            "component": self.component,
            "context": self.context,
            "severity": self.severity,
            "user_agent": self.user_agent,
            "session_id": self.session_id,
            "extra": self.extra,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
