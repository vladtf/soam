"""
SQLAlchemy models for application storage.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.sql import func
from src.database.database import Base


class Feedback(Base):
    """Feedback model for storing user feedback and bug reports."""
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def to_dict(self):
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
    raw_key = Column(String(255), nullable=False, index=True)  # incoming raw column/key (case-insensitive)
    canonical_key = Column(String(255), nullable=False)         # target canonical column name
    enabled = Column(Boolean, nullable=False, default=True)
    applied_count = Column(Integer, nullable=False, server_default="0")
    last_applied_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "raw_key": self.raw_key,
            "canonical_key": self.canonical_key,
            "enabled": self.enabled,
            "applied_count": getattr(self, "applied_count", 0),
            "last_applied_at": self.last_applied_at.isoformat() if getattr(self, "last_applied_at", None) else None,
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
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self):
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
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
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

    def to_dict(self):
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
