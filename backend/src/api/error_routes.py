"""
Client error reporting API endpoints.
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.models import ClientErrorCreate, ClientErrorResponse, ApiResponse
from src.api.response_utils import success_response
from src.database import get_db
from src.database.models import ClientError as ClientErrorModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["errors"]) 


@router.post("/errors", response_model=ApiResponse)
async def create_error(payload: ClientErrorCreate, db: Session = Depends(get_db)):
    """Accept a client error report and store it in the database."""
    try:
        db_err = ClientErrorModel(
            message=payload.message,
            stack=payload.stack,
            url=payload.url,
            component=payload.component,
            context=payload.context,
            severity=payload.severity,
            user_agent=payload.user_agent,
            session_id=payload.session_id,
            extra=None if payload.extra is None else __import__("json").dumps(payload.extra),
        )
        db.add(db_err)
        db.commit()
        db.refresh(db_err)
        logger.error("Client error stored id=%s message=%s", db_err.id, (db_err.message or "")[:200])
        return success_response({"id": db_err.id}, "Error report stored successfully")
    except Exception as e:
        db.rollback()
        logger.exception("Failed to store client error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/errors", response_model=List[ClientErrorResponse])
async def list_errors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List recent client errors for troubleshooting UI."""
    try:
        q = db.query(ClientErrorModel).order_by(ClientErrorModel.id.desc()).offset(skip).limit(limit)
        rows = q.all()
        import json as _json
        def parse_extra(txt):
            try:
                return _json.loads(txt) if txt else None
            except Exception:
                return None
        return [
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
    except Exception as e:
        logger.exception("Failed to list client errors: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


