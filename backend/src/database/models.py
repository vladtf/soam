"""
SQLAlchemy models for feedback storage.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from src.database.database import Base


class Feedback(Base):
    """
    Feedback model for storing user feedback and bug reports.
    """
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
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
