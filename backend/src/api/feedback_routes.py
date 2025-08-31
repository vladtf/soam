"""
Feedback API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from src.api.models import FeedbackCreate, FeedbackResponse, ApiResponse, ApiListResponse
from src.api.response_utils import success_response, list_response, not_found_error, bad_request_error, internal_server_error
from src.database import get_db, Feedback
from src.utils.logging import get_logger
from src.utils.api_utils import handle_api_errors

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["feedback"])


@router.post("/feedback", response_model=ApiResponse)
@handle_api_errors("create feedback")
async def create_feedback(
    feedback: FeedbackCreate,
    db: Session = Depends(get_db)
):
    """Submit new feedback."""
    # Create new feedback record
    db_feedback = Feedback(
        email=feedback.email,
        message=feedback.message
    )
    
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    
    logger.info(f"New feedback submitted by {feedback.email}")
    
    return success_response(
        {"id": db_feedback.id},
        "Feedback submitted successfully"
    )


@router.get("/feedback", response_model=ApiListResponse[FeedbackResponse])
@handle_api_errors("get feedbacks")
async def get_feedbacks(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all feedback submissions."""
    feedbacks = db.query(Feedback).offset(skip).limit(limit).all()
    
    feedback_responses = [
        FeedbackResponse(
            id=f.id,
            email=f.email,
            message=f.message,
            created_at=f.created_at.isoformat() if f.created_at else ""
        )
        for f in feedbacks
    ]
    
    return list_response(feedback_responses, message="Feedback retrieved successfully")


@router.get("/feedback/{feedback_id}", response_model=ApiResponse[FeedbackResponse])
@handle_api_errors("get feedback by id")
async def get_feedback(
    feedback_id: int,
    db: Session = Depends(get_db)
):
    """Get specific feedback by ID."""
    feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    
    if not feedback:
        not_found_error("Feedback not found")
        
    return FeedbackResponse(
        id=feedback.id,
        email=feedback.email,
        message=feedback.message,
        created_at=feedback.created_at.isoformat() if feedback.created_at else ""
    )


@router.delete("/feedback/{feedback_id}", response_model=ApiResponse)
@handle_api_errors("delete feedback")
async def delete_feedback(
    feedback_id: int,
    db: Session = Depends(get_db)
):
    """Delete specific feedback by ID."""
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
