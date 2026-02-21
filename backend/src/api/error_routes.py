"""
Client error reporting API endpoints.
"""
import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.models import ClientErrorCreate, ClientErrorResponse, ApiResponse, ApiListResponse
from src.api.response_utils import success_response, list_response, paginate_query, DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from src.database import get_db
from src.database.models import ClientError as ClientErrorModel
from src.utils.logging import get_logger
from src.utils.api_utils import handle_api_errors

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["errors"]) 


@router.post("/errors", response_model=ApiResponse)
@handle_api_errors("store client error")
async def create_error(payload: ClientErrorCreate, db: Session = Depends(get_db)):
    """Accept a client error report and store it in the database."""
    db_err = ClientErrorModel(
        message=payload.message,
        stack=payload.stack,
        url=payload.url,
        component=payload.component,
        context=payload.context,
        severity=payload.severity,
        user_agent=payload.user_agent,
        session_id=payload.session_id,
        extra=None if payload.extra is None else json.dumps(payload.extra),
    )
    db.add(db_err)
    db.commit()
    db.refresh(db_err)
    logger.error("Client error stored id=%s message=%s", db_err.id, (db_err.message or "")[:200])
    return success_response({"id": db_err.id}, "Error report stored successfully")


@router.get("/errors", response_model=ApiListResponse[ClientErrorResponse])
@handle_api_errors("list client errors")
async def list_errors(
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db)
):
    query = db.query(ClientErrorModel).order_by(ClientErrorModel.id.desc())
    rows, total = paginate_query(query, page, page_size)
    
    def parse_extra(txt):
        try:
            return json.loads(txt) if txt else None
        except Exception:
            return None
    
    errors_data = [
        ClientErrorResponse(
            id=r.id,
            message=r.message,
            stack=r.stack,
            url=r.url,
            component=r.component,
            context=r.context,
            severity=r.severity,
            user_agent=r.user_agent,
            session_id=r.session_id,
            extra=parse_extra(r.extra),
            created_at=r.created_at.isoformat() if getattr(r, "created_at", None) else None,
        )
        for r in rows
    ]
    
    return list_response(errors_data, total=total, page=page, page_size=page_size, message="Client errors retrieved successfully")


