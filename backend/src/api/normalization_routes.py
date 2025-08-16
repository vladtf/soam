"""
Normalization rules CRUD endpoints.
"""
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.models import (
    NormalizationRuleCreate,
    NormalizationRuleUpdate,
    NormalizationRuleResponse,
    ApiResponse,
)
from src.database import get_db
from src.database.models import NormalizationRule

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/normalization", tags=["normalization"])


@router.get("/", response_model=List[NormalizationRuleResponse])
def list_rules(db: Session = Depends(get_db)):
    try:
        rules = db.query(NormalizationRule).order_by(NormalizationRule.id.asc()).all()
        return [
            NormalizationRuleResponse(
                id=r.id,
                ingestion_id=r.ingestion_id,
                raw_key=r.raw_key,
                canonical_key=r.canonical_key,
                enabled=r.enabled,
                applied_count=getattr(r, "applied_count", 0),
                last_applied_at=r.last_applied_at.isoformat() if getattr(r, "last_applied_at", None) else None,
                created_by=getattr(r, "created_by", "unknown"),
                updated_by=getattr(r, "updated_by", None),
                created_at=r.created_at.isoformat() if r.created_at else None,
                updated_at=r.updated_at.isoformat() if r.updated_at else None,
            )
            for r in rules
        ]
    except Exception as e:
        logger.error("Error listing normalization rules: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=NormalizationRuleResponse)
def create_rule(payload: NormalizationRuleCreate, db: Session = Depends(get_db)):
    try:
        rule = NormalizationRule(
            ingestion_id=payload.ingestion_id,
            raw_key=payload.raw_key.strip().lower(),
            canonical_key=payload.canonical_key.strip(),
            enabled=payload.enabled,
            created_by=payload.created_by.strip(),
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        logger.info("Normalization rule created by '%s': %s -> %s", 
                   payload.created_by, rule.raw_key, rule.canonical_key)
        return NormalizationRuleResponse(
            id=rule.id,
            ingestion_id=rule.ingestion_id,
            raw_key=rule.raw_key,
            canonical_key=rule.canonical_key,
            enabled=rule.enabled,
            applied_count=getattr(rule, "applied_count", 0),
            last_applied_at=rule.last_applied_at.isoformat() if getattr(rule, "last_applied_at", None) else None,
            created_by=rule.created_by,
            updated_by=rule.updated_by,
            created_at=rule.created_at.isoformat() if rule.created_at else None,
            updated_at=rule.updated_at.isoformat() if rule.updated_at else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Error creating normalization rule: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{rule_id}", response_model=NormalizationRuleResponse)
def update_rule(rule_id: int, payload: NormalizationRuleUpdate, db: Session = Depends(get_db)):
    try:
        rule = db.query(NormalizationRule).filter(NormalizationRule.id == rule_id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")

        rule = db.query(NormalizationRule).filter(NormalizationRule.id == rule_id).first()
        if payload.canonical_key is not None and payload.canonical_key.strip() != rule.canonical_key:
            changes.append(f"canonical_key: '{rule.canonical_key}' -> '{payload.canonical_key.strip()}'")
            rule.canonical_key = payload.canonical_key.strip()
        if payload.enabled is not None and payload.enabled != rule.enabled:
            changes.append(f"enabled: {rule.enabled} -> {payload.enabled}")
            rule.enabled = payload.enabled

        rule.updated_by = payload.updated_by.strip()
        
        db.commit()
        db.refresh(rule)
        
        if changes:
            logger.info("Normalization rule %d updated by '%s': %s", 
                       rule.id, payload.updated_by, "; ".join(changes))
        else:
            logger.info("Normalization rule %d touched by '%s' (no changes)", 
                       rule.id, payload.updated_by)
        
        return NormalizationRuleResponse(
            id=rule.id,
            ingestion_id=rule.ingestion_id,
            raw_key=rule.raw_key,
            canonical_key=rule.canonical_key,
            enabled=rule.enabled,
            applied_count=getattr(rule, "applied_count", 0),
            last_applied_at=rule.last_applied_at.isoformat() if getattr(rule, "last_applied_at", None) else None,
            created_by=rule.created_by,
            updated_by=rule.updated_by,
            created_at=rule.created_at.isoformat() if rule.created_at else None,
            updated_at=rule.updated_at.isoformat() if rule.updated_at else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Error updating normalization rule %d: %s", rule_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{rule_id}", response_model=ApiResponse)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    try:
        rule = db.query(NormalizationRule).filter(NormalizationRule.id == rule_id).first()
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        db.delete(rule)
        db.commit()
        logger.info("Normalization rule deleted: id=%d", rule_id)
        return ApiResponse(status="success", message="Rule deleted")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("Error deleting normalization rule %d: %s", rule_id, e)
        raise HTTPException(status_code=500, detail=str(e))
