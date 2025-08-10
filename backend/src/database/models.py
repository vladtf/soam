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
