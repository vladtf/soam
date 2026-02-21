"""
Normalization rules CRUD endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.models import (
    NormalizationRuleCreate,
    NormalizationRuleUpdate,
    NormalizationRuleResponse,
    ApiResponse,
    ApiListResponse,
)
from src.api.response_utils import success_response, list_response, not_found_error, bad_request_error, internal_server_error
from src.database import get_db
from src.database.models import NormalizationRule
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["normalization"])


def _rule_to_response(r: NormalizationRule) -> NormalizationRuleResponse:
    """Convert a NormalizationRule ORM model to a NormalizationRuleResponse."""
    return NormalizationRuleResponse(
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


@router.get("/normalization", response_model=ApiListResponse)
def list_rules(db: Session = Depends(get_db)):
    """List all normalization rules."""
    try:
        rules = db.query(NormalizationRule).order_by(NormalizationRule.id.asc()).all()
        rule_responses = [_rule_to_response(r) for r in rules]
        return list_response(
            data=rule_responses,
            message=f"Retrieved {len(rule_responses)} normalization rules"
        )
    except Exception as e:
        logger.error("❌ Error listing normalization rules: %s", e)
        raise internal_server_error("Failed to retrieve normalization rules", str(e))


@router.post("/normalization", response_model=ApiResponse)
def create_rule(payload: NormalizationRuleCreate, db: Session = Depends(get_db)):
    """Create a new normalization rule."""
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
        logger.info("✅ Normalization rule created by '%s': %s -> %s", 
                   payload.created_by, rule.raw_key, rule.canonical_key)
        
        return success_response(
            data=_rule_to_response(rule),
            message="Normalization rule created successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("❌ Error creating normalization rule: %s", e)
        raise internal_server_error("Failed to create normalization rule", str(e))


@router.patch("/normalization/{rule_id}", response_model=ApiResponse)
def update_rule(rule_id: int, payload: NormalizationRuleUpdate, db: Session = Depends(get_db)):
    """Update an existing normalization rule."""
    try:
        rule = db.query(NormalizationRule).filter(NormalizationRule.id == rule_id).first()
        if not rule:
            raise not_found_error("Rule not found")

        changes = []
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
            logger.info("✅ Normalization rule %d updated by '%s': %s", 
                       rule.id, payload.updated_by, "; ".join(changes))
        else:
            logger.info("✅ Normalization rule %d touched by '%s' (no changes)",
                       rule.id, payload.updated_by)
        
        return success_response(
            data=_rule_to_response(rule),
            message="Normalization rule updated successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("❌ Error updating normalization rule %d: %s", rule_id, e)
        raise internal_server_error("Failed to update normalization rule", str(e))


@router.delete("/normalization/{rule_id}", response_model=ApiResponse)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    """Delete a normalization rule."""
    try:
        rule = db.query(NormalizationRule).filter(NormalizationRule.id == rule_id).first()
        if not rule:
            raise not_found_error("Rule not found")
        db.delete(rule)
        db.commit()
        logger.info("✅ Normalization rule deleted: id=%d", rule_id)
        return success_response(message="Rule deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("❌ Error deleting normalization rule %d: %s", rule_id, e)
        raise internal_server_error("Failed to delete normalization rule", str(e))


@router.patch("/normalization/{rule_id}/toggle", response_model=ApiResponse)
def toggle_rule(rule_id: int, db: Session = Depends(get_db)):
    """Toggle the enabled/disabled state of a normalization rule."""
    try:
        rule = db.query(NormalizationRule).filter(NormalizationRule.id == rule_id).first()
        if not rule:
            raise not_found_error("Rule not found")

        # Toggle the enabled state
        old_state = rule.enabled
        rule.enabled = not rule.enabled
        
        db.commit()
        db.refresh(rule)
        
        logger.info("✅ Normalization rule %d toggled: %s -> %s (%s -> %s)", 
                   rule_id, old_state, rule.enabled, rule.raw_key, rule.canonical_key)
        
        return success_response(
            data=_rule_to_response(rule),
            message=f"Rule {'enabled' if rule.enabled else 'disabled'} successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("❌ Error toggling normalization rule %d: %s", rule_id, e)
        raise internal_server_error("Failed to toggle normalization rule", str(e))
