"""
Device registration API endpoints.
"""
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.models import DeviceCreate, DeviceUpdate, DeviceResponse, ApiResponse
from src.database.database import get_db
from src.database.models import Device

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("/", response_model=List[DeviceResponse])
def list_devices(db: Session = Depends(get_db)):
    try:
        rows = db.query(Device).order_by(Device.created_at.desc()).all()
        return [r.to_dict() for r in rows]
    except Exception as e:
        logger.error("Error listing devices: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=DeviceResponse)
def register_device(payload: DeviceCreate, db: Session = Depends(get_db)):
    try:
        # Validate user is provided
        if not payload.created_by or not payload.created_by.strip():
            raise HTTPException(status_code=400, detail="User information required (created_by)")
        
        # Initial registration should only require ingestion_id.
        # If a device with the same ingestion_id exists, update its metadata; otherwise create it.
        existing = db.query(Device).filter(Device.ingestion_id == payload.ingestion_id).one_or_none()
        if existing:
            existing.name = payload.name
            existing.description = payload.description
            existing.enabled = payload.enabled
            existing.updated_by = payload.created_by.strip()  # Use created_by as updated_by for existing devices
            db.add(existing)
            db.commit()
            db.refresh(existing)
            logger.info("Device updated by '%s': %s", 
                       payload.created_by, existing.ingestion_id)
            return existing.to_dict()
        
        row = Device(
            ingestion_id=payload.ingestion_id,
            name=payload.name,
            description=payload.description,
            enabled=payload.enabled,
            created_by=payload.created_by.strip(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        logger.info("Device registered by '%s': %s", 
                   payload.created_by, row.ingestion_id)
        return row.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error registering device: %s", e)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{device_id}", response_model=DeviceResponse)
def update_device(device_id: int, payload: DeviceUpdate, db: Session = Depends(get_db)):
    try:
        # Validate user is provided
        if not payload.updated_by or not payload.updated_by.strip():
            raise HTTPException(status_code=400, detail="User information required (updated_by)")
        
        row = db.query(Device).filter(Device.id == device_id).one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Device not found")
        
        changes = []
        if payload.name is not None and payload.name != row.name:
            changes.append(f"name: '{row.name or ''}' -> '{payload.name}'")
            row.name = payload.name
        if payload.description is not None and payload.description != row.description:
            changes.append(f"description: '{row.description or ''}' -> '{payload.description}'")
            row.description = payload.description
        if payload.enabled is not None and payload.enabled != row.enabled:
            changes.append(f"enabled: {row.enabled} -> {payload.enabled}")
            row.enabled = payload.enabled

        row.updated_by = payload.updated_by.strip()
        
        db.add(row)
        db.commit()
        db.refresh(row)
        
        if changes:
            logger.info("Device %d updated by '%s': %s", 
                       row.id, payload.updated_by, "; ".join(changes))
        else:
            logger.info("Device %d touched by '%s' (no changes)", 
                       row.id, payload.updated_by)
        
        return row.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating device: %s", e)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{device_id}", response_model=ApiResponse)
def delete_device(device_id: int, db: Session = Depends(get_db)):
    try:
        row = db.query(Device).filter(Device.id == device_id).one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Device not found")
        db.delete(row)
        db.commit()
        return {"status": "success", "message": "Device deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting device: %s", e)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{device_id}/toggle", response_model=DeviceResponse)
def toggle_device(device_id: int, db: Session = Depends(get_db)):
    try:
        row = db.query(Device).filter(Device.id == device_id).one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Device not found")
        row.enabled = not row.enabled
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error toggling device: %s", e)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
