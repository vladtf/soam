"""
Feedback API endpoints.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from src.api.models import FeedbackCreate, FeedbackResponse, ApiResponse
from src.database import get_db, Feedback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/", response_model=ApiResponse)
async def create_feedback(
    feedback: FeedbackCreate,
    db: Session = Depends(get_db)
):
    """Submit new feedback."""
    try:
        # Create new feedback record
        db_feedback = Feedback(
            email=feedback.email,
            message=feedback.message
        )
        
        db.add(db_feedback)
        db.commit()
        db.refresh(db_feedback)
        
        logger.info(f"New feedback submitted by {feedback.email}")
        
        return ApiResponse(
            status="success",
            data={"id": db_feedback.id},
            message="Feedback submitted successfully"
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[FeedbackResponse])
async def get_feedbacks(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all feedback submissions."""
    try:
        feedbacks = db.query(Feedback).offset(skip).limit(limit).all()
        
        return [
            FeedbackResponse(
                id=f.id,
                email=f.email,
                message=f.message,
                created_at=f.created_at.isoformat() if f.created_at else ""
            )
            for f in feedbacks
        ]
        
    except Exception as e:
        logger.error(f"Error fetching feedbacks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{feedback_id}", response_model=FeedbackResponse)
async def get_feedback(
    feedback_id: int,
    db: Session = Depends(get_db)
):
    """Get specific feedback by ID."""
    try:
        feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
        
        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")
            
        return FeedbackResponse(
            id=feedback.id,
            email=feedback.email,
            message=feedback.message,
            created_at=feedback.created_at.isoformat() if feedback.created_at else ""
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching feedback {feedback_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{feedback_id}", response_model=ApiResponse)
async def delete_feedback(
    feedback_id: int,
    db: Session = Depends(get_db)
):
    """Delete specific feedback by ID."""
    try:
        feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
        
        if not feedback:
            raise HTTPException(status_code=404, detail="Feedback not found")
            
        db.delete(feedback)
        db.commit()
        
        logger.info(f"Feedback {feedback_id} deleted")
        
        return ApiResponse(
            status="success",
            message="Feedback deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting feedback {feedback_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
