"""
Device registration API endpoints.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.models import DeviceCreate, DeviceUpdate, DeviceResponse, ApiResponse, ApiListResponse
from src.api.response_utils import success_response, list_response, not_found_error, bad_request_error, forbidden_error, internal_server_error, paginate_query, DEFAULT_PAGE, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from src.database.database import get_db
from src.database.models import Device, DataSensitivity, UserRole, User
from src.api.dependencies import get_neo4j_manager
from src.neo4j.neo4j_manager import Neo4jManager
from src.neo4j.ontology_manager import OntologyManager
from src.auth.dependencies import get_current_user
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["devices"])


def _get_sensitivity_enum(sensitivity_str: str) -> DataSensitivity:
    """Convert sensitivity string to enum, with validation."""
    try:
        return DataSensitivity(sensitivity_str.lower())
    except ValueError:
        return DataSensitivity.INTERNAL


def _can_register_sensitivity(user: User, sensitivity: DataSensitivity) -> bool:
    """Check if user can register devices with given sensitivity."""
    # Only users with ADMIN role can register CONFIDENTIAL or RESTRICTED devices
    if sensitivity in [DataSensitivity.CONFIDENTIAL, DataSensitivity.RESTRICTED]:
        return user.has_role(UserRole.ADMIN)
    return True


@router.get("/devices", response_model=ApiListResponse[DeviceResponse])
def list_devices(
    page: int = Query(DEFAULT_PAGE, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db)
) -> ApiListResponse[DeviceResponse]:
    try:
        query = db.query(Device).order_by(Device.created_at.desc())
        rows, total = paginate_query(query, page, page_size)
        devices: List[dict] = [r.to_dict() for r in rows]
        return list_response(devices, total=total, page=page, page_size=page_size, message="Devices retrieved successfully")
    except Exception as e:
        logger.error("Error listing devices: %s", e)
        raise internal_server_error("Failed to retrieve devices", str(e))


@router.post("/devices", response_model=ApiResponse[DeviceResponse])
async def register_device(
    payload: DeviceCreate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    neo4j: Neo4jManager = Depends(get_neo4j_manager),
) -> ApiResponse[DeviceResponse]:
    try:
        # Parse and validate sensitivity level
        sensitivity = _get_sensitivity_enum(payload.sensitivity)
        
        # Check role-based restrictions for high-sensitivity devices
        if not _can_register_sensitivity(current_user, sensitivity):
            raise forbidden_error(
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
            existing.updated_by = current_user.username
            db.add(existing)
            db.commit()
            db.refresh(existing)
            logger.info("✅ Device updated by '%s' with sensitivity '%s': %s", 
                       current_user.username, sensitivity.value, existing.ingestion_id)
            return success_response(existing.to_dict(), "Device updated successfully")
        
        row: Device = Device(
            ingestion_id=payload.ingestion_id,
            name=payload.name,
            description=payload.description,
            enabled=payload.enabled,
            sensitivity=sensitivity,
            data_retention_days=payload.data_retention_days,
            created_by=current_user.username,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        logger.info("✅ Device registered by '%s' with sensitivity '%s': %s", 
                   current_user.username, sensitivity.value, row.ingestion_id)

        # Register sensor in Neo4j ontology (hardcoded building for now)
        OntologyManager(neo4j).register_sensor(row.ingestion_id)

        return success_response(row.to_dict(), "Device registered successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Error registering device: %s", e)
        db.rollback()
        raise internal_server_error("Failed to register device", str(e))


@router.patch("/devices/{device_id}", response_model=ApiResponse[DeviceResponse])
async def update_device(
    device_id: int, 
    payload: DeviceUpdate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> ApiResponse[DeviceResponse]:
    try:
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
        
        # Handle sensitivity updates with role-based restrictions
        if payload.sensitivity is not None:
            new_sensitivity = _get_sensitivity_enum(payload.sensitivity)
            if new_sensitivity != row.sensitivity:
                if not _can_register_sensitivity(current_user, new_sensitivity):
                    raise forbidden_error(
                        f"Only administrators can set devices to '{new_sensitivity.value}' sensitivity level"
                    )
                changes.append(f"sensitivity: {row.sensitivity.value} -> {new_sensitivity.value}")
                row.sensitivity = new_sensitivity
        
        if payload.data_retention_days is not None and payload.data_retention_days != row.data_retention_days:
            changes.append(f"data_retention_days: {row.data_retention_days} -> {payload.data_retention_days}")
            row.data_retention_days = payload.data_retention_days
        
        row.updated_by = current_user.username
        
        db.add(row)
        db.commit()
        db.refresh(row)
        
        if changes:
            logger.info("✅ Device %d updated by '%s': %s", 
                       row.id, current_user.username, "; ".join(changes))
        else:
            logger.info("ℹ️ Device %d touched by '%s' (no changes)", 
                       row.id, current_user.username)
        
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
    except HTTPException:
        raise
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
    except HTTPException:
        raise
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
