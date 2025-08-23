"""
API routes for managing application settings.
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.database.database import get_db
from src.database.models import Setting, ValueTypeEnum
from src.api.models import SettingCreate, SettingUpdate, SettingResponse, ApiResponse
from src.api.response_utils import success_response
from src.utils.settings_manager import settings_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["settings"])


def _get_value_type_enum(value_type_str: str) -> ValueTypeEnum:
    """Convert string value type to enum."""
    try:
        return ValueTypeEnum(value_type_str.lower())
    except ValueError:
        # Default to string if invalid
        return ValueTypeEnum.STRING


@router.get("/settings", response_model=List[SettingResponse])
async def list_settings(
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all settings, optionally filtered by category."""
    try:
        query = db.query(Setting)
        if category:
            query = query.filter(Setting.category == category)
        
        settings = query.order_by(Setting.category, Setting.key).all()
        return [SettingResponse.model_validate(setting.to_dict()) for setting in settings]
    except Exception as e:
        logger.error(f"Error listing settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list settings: {str(e)}"
        )


@router.get("/settings/{key}", response_model=SettingResponse)
async def get_setting(
    key: str,
    db: Session = Depends(get_db)
):
    """Get a specific setting by key."""
    try:
        setting = db.query(Setting).filter(Setting.key == key).first()
        if not setting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Setting with key '{key}' not found"
            )
        
        return SettingResponse.model_validate(setting.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting setting '{key}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get setting: {str(e)}"
        )


@router.post("/settings", response_model=SettingResponse)
async def create_setting(
    setting_data: SettingCreate,
    db: Session = Depends(get_db)
):
    """Create a new setting."""
    try:
        # Check if setting with this key already exists
        existing = db.query(Setting).filter(Setting.key == setting_data.key).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Setting with key '{setting_data.key}' already exists"
            )
        
        # Validate value type
        _validate_setting_value(setting_data.value, setting_data.value_type)
        
        setting = Setting(
            key=setting_data.key,
            value=setting_data.value,
            value_type=_get_value_type_enum(setting_data.value_type),
            description=setting_data.description,
            category=setting_data.category,
            created_by=setting_data.created_by
        )
        
        db.add(setting)
        db.commit()
        db.refresh(setting)
        
        # Clear settings cache to ensure fresh data
        settings_manager.clear_cache()
        
        logger.info(f"Created setting '{setting.key}' with value '{setting.value}'")
        return SettingResponse.model_validate(setting.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating setting: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create setting: {str(e)}"
        )


@router.put("/settings/{key}", response_model=SettingResponse)
async def update_setting(
    key: str,
    setting_data: SettingUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing setting."""
    try:
        setting = db.query(Setting).filter(Setting.key == key).first()
        if not setting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Setting with key '{key}' not found"
            )
        
        # Validate value type
        value_type = setting_data.value_type or setting.value_type
        if isinstance(value_type, ValueTypeEnum):
            value_type = value_type.value
        _validate_setting_value(setting_data.value, value_type)
        
        # Update fields
        setting.value = setting_data.value
        if setting_data.value_type:
            setting.value_type = _get_value_type_enum(setting_data.value_type)
        if setting_data.description is not None:
            setting.description = setting_data.description
        if setting_data.category is not None:
            setting.category = setting_data.category
        setting.updated_by = setting_data.updated_by
        
        db.commit()
        db.refresh(setting)
        
        # Clear settings cache to ensure fresh data
        settings_manager.clear_cache()
        
        logger.info(f"Updated setting '{setting.key}' to value '{setting.value}'")
        return SettingResponse.model_validate(setting.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating setting '{key}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update setting: {str(e)}"
        )


@router.delete("/settings/{key}", response_model=ApiResponse)
async def delete_setting(
    key: str,
    db: Session = Depends(get_db)
) -> ApiResponse:
    """Delete a setting."""
    try:
        setting = db.query(Setting).filter(Setting.key == key).first()
        if not setting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Setting with key '{key}' not found"
            )
        
        db.delete(setting)
        db.commit()
        
        # Clear settings cache to ensure fresh data
        settings_manager.clear_cache()
        
        logger.info(f"Deleted setting '{key}'")
        return success_response(message=f"Setting '{key}' deleted successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting setting '{key}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete setting: {str(e)}"
        )


@router.get("/settings/{key}/typed-value")
async def get_setting_typed_value(
    key: str,
    db: Session = Depends(get_db)
):
    """Get a setting value converted to its proper type."""
    try:
        setting = db.query(Setting).filter(Setting.key == key).first()
        if not setting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Setting with key '{key}' not found"
            )
        
        return {
            "key": setting.key,
            "value": setting.get_typed_value(),
            "value_type": setting.value_type
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting typed value for setting '{key}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get setting value: {str(e)}"
        )


def _validate_setting_value(value, value_type: str) -> None:
    """Validate that the setting value matches the expected type."""
    try:
        if value_type == "number":
            # Accept both string and numeric types
            float(value)
        elif value_type == "boolean":
            # Accept both string and boolean types
            if isinstance(value, bool):
                pass
            elif isinstance(value, str):
                if value.lower() not in ("true", "false", "1", "0", "yes", "no"):
                    raise ValueError("Invalid boolean value")
            else:
                raise ValueError("Invalid boolean value type")
        elif value_type == "json":
            import json
            if isinstance(value, str):
                json.loads(value)
            else:
                # Already a parsed object, ensure it's serializable
                json.dumps(value)
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid value for type '{value_type}': {str(e)}"
        )


def get_setting_value(db: Session, key: str, default_value=None, value_type: str = "string"):
    """
    Utility function to get a setting value with proper type conversion.
    Returns the default value if the setting doesn't exist.
    """
    try:
        setting = db.query(Setting).filter(Setting.key == key).first()
        if not setting:
            return default_value
        return setting.get_typed_value()
    except Exception as e:
        logger.warning(f"Error getting setting '{key}', using default: {e}")
        return default_value


def ensure_default_settings(db: Session):
    """Ensure default settings exist in the database."""
    default_settings = [
        {
            "key": "temperature_threshold",
            "value": "30.0",
            "value_type": ValueTypeEnum.NUMBER,
            "description": "Temperature threshold in Celsius for triggering alerts",
            "category": "alerts",
            "created_by": "system"
        }
    ]
    
    for setting_data in default_settings:
        existing = db.query(Setting).filter(Setting.key == setting_data["key"]).first()
        if not existing:
            setting = Setting(**setting_data)
            db.add(setting)
    
    try:
        db.commit()
        # Clear settings cache after initializing defaults
        settings_manager.clear_cache()
        logger.info("Default settings initialized")
    except Exception as e:
        db.rollback()
        logger.error(f"Error initializing default settings: {e}")
