"""
Device registration API endpoints.
"""
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.models import DeviceCreate, DeviceUpdate, DeviceResponse, ApiResponse, ApiListResponse
from src.api.response_utils import success_response, error_response, list_response, not_found_error, bad_request_error, internal_server_error
from src.database.database import get_db
from src.database.models import Device

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["devices"])


@router.get("/devices", response_model=ApiListResponse[DeviceResponse])
def list_devices(db: Session = Depends(get_db)) -> ApiListResponse[DeviceResponse]:
    try:
        rows: List[Device] = db.query(Device).order_by(Device.created_at.desc()).all()
        devices: List[dict] = [r.to_dict() for r in rows]
        return list_response(devices, message="Devices retrieved successfully")
    except Exception as e:
        logger.error("Error listing devices: %s", e)
        raise internal_server_error("Failed to retrieve devices", str(e))


@router.post("/devices", response_model=ApiResponse[DeviceResponse])
def register_device(payload: DeviceCreate, db: Session = Depends(get_db)) -> ApiResponse[DeviceResponse]:
    try:
        # Validate user is provided
        if not payload.created_by or not payload.created_by.strip():
            raise bad_request_error("User information required (created_by)")
        
        # Initial registration should only require ingestion_id.
        # If a device with the same ingestion_id exists, update its metadata; otherwise create it.
        existing: Device | None = db.query(Device).filter(Device.ingestion_id == payload.ingestion_id).one_or_none()
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
            return success_response(existing.to_dict(), "Device updated successfully")
        
        row: Device = Device(
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
        return success_response(row.to_dict(), "Device registered successfully")
    except Exception as e:
        logger.error("Error registering device: %s", e)
        db.rollback()
        raise internal_server_error("Failed to register device", str(e))


@router.patch("/devices/{device_id}", response_model=ApiResponse[DeviceResponse])
def update_device(device_id: int, payload: DeviceUpdate, db: Session = Depends(get_db)) -> ApiResponse[DeviceResponse]:
    try:
        # Validate user is provided
        if not payload.updated_by or not payload.updated_by.strip():
            raise bad_request_error("User information required (updated_by)")
        
        row: Device | None = db.query(Device).filter(Device.id == device_id).one_or_none()
        if not row:
            raise not_found_error("Device not found")
        
        changes: List[str] = []
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
        
        return success_response(row.to_dict(), "Device updated successfully")
    except Exception as e:
        logger.error("Error updating device: %s", e)
        db.rollback()
        raise internal_server_error("Failed to update device", str(e))


@router.delete("/devices/{device_id}", response_model=ApiResponse)
def delete_device(device_id: int, db: Session = Depends(get_db)) -> ApiResponse:
    try:
        row: Device | None = db.query(Device).filter(Device.id == device_id).one_or_none()
        if not row:
            raise not_found_error("Device not found")
        db.delete(row)
        db.commit()
        return success_response({"message": "Device deleted"}, "Device deleted successfully")
    except Exception as e:
        logger.error("Error deleting device: %s", e)
        db.rollback()
        raise internal_server_error("Failed to delete device", str(e))


@router.post("/devices/{device_id}/toggle", response_model=ApiResponse[DeviceResponse])
def toggle_device(device_id: int, db: Session = Depends(get_db)) -> ApiResponse[DeviceResponse]:
    try:
        row: Device | None = db.query(Device).filter(Device.id == device_id).one_or_none()
        if not row:
            raise not_found_error("Device not found")
        row.enabled = not row.enabled
        db.add(row)
        db.commit()
        db.refresh(row)
        return success_response(row.to_dict(), "Device toggled successfully")
    except Exception as e:
        logger.error("Error toggling device: %s", e)
        db.rollback()
        raise internal_server_error("Failed to toggle device", str(e))
