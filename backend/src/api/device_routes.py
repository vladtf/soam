"""
Device registration API endpoints.
"""
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.models import DeviceCreate, DeviceUpdate, DeviceResponse, ApiResponse, ApiListResponse
from src.api.response_utils import success_response, list_response, not_found_error, bad_request_error, internal_server_error
from src.database.database import get_db
from src.database.models import Device, DataSensitivity, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["devices"])


def _get_sensitivity_enum(sensitivity_str: str) -> DataSensitivity:
    """Convert sensitivity string to enum, with validation."""
    try:
        return DataSensitivity(sensitivity_str.lower())
    except ValueError:
        return DataSensitivity.INTERNAL


def _can_register_sensitivity(user_role: str, sensitivity: DataSensitivity) -> bool:
    """Check if user role can register devices with given sensitivity."""
    # Only ADMIN can register CONFIDENTIAL or RESTRICTED devices
    if sensitivity in [DataSensitivity.CONFIDENTIAL, DataSensitivity.RESTRICTED]:
        return user_role == UserRole.ADMIN.value or user_role == "admin"
    return True


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
        
        # Parse and validate sensitivity level
        sensitivity = _get_sensitivity_enum(payload.sensitivity)
        
        # Check role-based restrictions for high-sensitivity devices
        # For now, we'll check based on user role in created_by (format: "username:role" or just "username")
        user_parts = payload.created_by.strip().split(":")
        user_role = user_parts[1] if len(user_parts) > 1 else "user"
        
        if not _can_register_sensitivity(user_role, sensitivity):
            raise bad_request_error(
                f"Only administrators can register devices with '{sensitivity.value}' sensitivity level"
            )
        
        # Initial registration should only require ingestion_id.
        # If a device with the same ingestion_id exists, update its metadata; otherwise create it.
        existing: Device | None = db.query(Device).filter(Device.ingestion_id == payload.ingestion_id).one_or_none()
        if existing:
            existing.name = payload.name
            existing.description = payload.description
            existing.enabled = payload.enabled
            existing.sensitivity = sensitivity
            existing.data_retention_days = payload.data_retention_days
            existing.updated_by = user_parts[0]  # Use username part
            db.add(existing)
            db.commit()
            db.refresh(existing)
            logger.info("✅ Device updated by '%s' with sensitivity '%s': %s", 
                       payload.created_by, sensitivity.value, existing.ingestion_id)
            return success_response(existing.to_dict(), "Device updated successfully")
        
        row: Device = Device(
            ingestion_id=payload.ingestion_id,
            name=payload.name,
            description=payload.description,
            enabled=payload.enabled,
            sensitivity=sensitivity,
            data_retention_days=payload.data_retention_days,
            created_by=user_parts[0],  # Use username part
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        logger.info("✅ Device registered by '%s' with sensitivity '%s': %s", 
                   payload.created_by, sensitivity.value, row.ingestion_id)
        return success_response(row.to_dict(), "Device registered successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Error registering device: %s", e)
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
        
        # Parse user role from updated_by
        user_parts = payload.updated_by.strip().split(":")
        user_role = user_parts[1] if len(user_parts) > 1 else "user"
        username = user_parts[0]
        
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
        
        # Handle sensitivity updates with role-based restrictions
        if payload.sensitivity is not None:
            new_sensitivity = _get_sensitivity_enum(payload.sensitivity)
            if new_sensitivity != row.sensitivity:
                if not _can_register_sensitivity(user_role, new_sensitivity):
                    raise bad_request_error(
                        f"Only administrators can set devices to '{new_sensitivity.value}' sensitivity level"
                    )
                changes.append(f"sensitivity: {row.sensitivity.value} -> {new_sensitivity.value}")
                row.sensitivity = new_sensitivity
        
        if payload.data_retention_days is not None and payload.data_retention_days != row.data_retention_days:
            changes.append(f"data_retention_days: {row.data_retention_days} -> {payload.data_retention_days}")
            row.data_retention_days = payload.data_retention_days
        
        row.updated_by = username
        
        db.add(row)
        db.commit()
        db.refresh(row)
        
        if changes:
            logger.info("✅ Device %d updated by '%s': %s", 
                       row.id, payload.updated_by, "; ".join(changes))
        else:
            logger.info("ℹ️ Device %d touched by '%s' (no changes)", 
                       row.id, payload.updated_by)
        
        return success_response(row.to_dict(), "Device updated successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Error updating device: %s", e)
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


@router.get("/devices/sensitivity-levels", response_model=ApiResponse)
def get_sensitivity_levels() -> ApiResponse:
    """Get available sensitivity levels with descriptions."""
    levels = [
        {
            "value": "public",
            "label": "Public",
            "description": "Non-sensitive data, open access (weather, air quality)",
            "access": "All users",
            "badge_color": "success"
        },
        {
            "value": "internal",
            "label": "Internal",
            "description": "Business data, internal use only (energy usage, occupancy)",
            "access": "USER and ADMIN roles",
            "badge_color": "info"
        },
        {
            "value": "confidential",
            "label": "Confidential",
            "description": "Sensitive data, restricted access (location tracking, cameras)",
            "access": "ADMIN only",
            "badge_color": "warning"
        },
        {
            "value": "restricted",
            "label": "Restricted",
            "description": "Highly sensitive data, strict controls (personal identifiers, health)",
            "access": "ADMIN",
            "badge_color": "danger"
        }
    ]
    return success_response(levels, "Sensitivity levels retrieved")
