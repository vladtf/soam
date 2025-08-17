"""
Settings manager for application configuration.
"""
import logging
from typing import Optional, Any, Dict
from sqlalchemy.orm import sessionmaker
from src.database.database import engine
from src.database.models import Setting

logger = logging.getLogger(__name__)


class SettingsManager:
    """Manages application settings with database storage and caching."""
    
    def __init__(self):
        """Initialize the settings manager."""
        self._cache: Dict[str, Any] = {}
        self._cache_enabled = True
    
    def get_setting(self, key: str, default: Any = None, setting_type: type = str) -> Any:
        """
        Get a setting value from database with optional caching.
        
        Args:
            key: Setting key
            default: Default value if setting not found
            setting_type: Type to convert the setting value to (str, int, float, bool)
            
        Returns:
            Setting value converted to the specified type, or default if not found
        """
        # Check cache first
        if self._cache_enabled and key in self._cache:
            return self._cache[key]
        
        try:
            SessionLocal = sessionmaker(bind=engine)
            session = SessionLocal()
            try:
                setting = session.query(Setting).filter(Setting.key == key).first()
                if setting:
                    value = self._convert_value(setting.value, setting_type)
                    # Cache the value
                    if self._cache_enabled:
                        self._cache[key] = value
                    return value
                else:
                    logger.debug(f"Setting '{key}' not found in database, using default: {default}")
                    return default
            finally:
                session.close()
        except Exception as e:
            logger.warning(f"Failed to get setting '{key}' from database: {e}")
            return default
    
    def set_setting(self, key: str, value: Any, description: Optional[str] = None) -> bool:
        """
        Set a setting value in the database.
        
        Args:
            key: Setting key
            value: Setting value
            description: Optional description
            
        Returns:
            True if successful, False otherwise
        """
        try:
            SessionLocal = sessionmaker(bind=engine)
            session = SessionLocal()
            try:
                # Convert value to string for storage
                str_value = str(value)
                
                # Check if setting exists
                setting = session.query(Setting).filter(Setting.key == key).first()
                
                if setting:
                    # Update existing setting
                    setting.value = str_value
                    if description is not None:
                        setting.description = description
                else:
                    # Create new setting
                    setting = Setting(
                        key=key,
                        value=str_value,
                        description=description
                    )
                    session.add(setting)
                
                session.commit()
                
                # Update cache
                if self._cache_enabled:
                    self._cache[key] = value
                
                logger.info(f"Setting '{key}' updated to '{value}'")
                return True
                
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to set setting '{key}': {e}")
                return False
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Failed to connect to database for setting '{key}': {e}")
            return False
    
    def get_temperature_threshold(self, default: float = 30.0) -> float:
        """
        Get the temperature threshold for alerts.
        
        Args:
            default: Default threshold value in Celsius
            
        Returns:
            Temperature threshold in Celsius
        """
        return self.get_setting("temperature_threshold", default, float)
    
    def set_temperature_threshold(self, threshold: float) -> bool:
        """
        Set the temperature threshold for alerts.
        
        Args:
            threshold: Temperature threshold in Celsius
            
        Returns:
            True if successful, False otherwise
        """
        return self.set_setting(
            "temperature_threshold", 
            threshold, 
            "Temperature threshold for alerts in Celsius"
        )
    
    def get_auto_refresh_interval(self, default: int = 30000) -> int:
        """
        Get the auto refresh interval for dashboard.
        
        Args:
            default: Default interval value in milliseconds
            
        Returns:
            Auto refresh interval in milliseconds
        """
        return self.get_setting("auto_refresh_interval", default, int)
    
    def set_auto_refresh_interval(self, interval: int) -> bool:
        """
        Set the auto refresh interval for dashboard.
        
        Args:
            interval: Refresh interval in milliseconds
            
        Returns:
            True if successful, False otherwise
        """
        return self.set_setting(
            "auto_refresh_interval", 
            interval, 
            "Auto refresh interval for dashboard in milliseconds"
        )
    
    def get_max_alert_history(self, default: int = 100) -> int:
        """
        Get the maximum number of alerts to keep in history.
        
        Args:
            default: Default max alerts value
            
        Returns:
            Maximum number of alerts to keep
        """
        return self.get_setting("max_alert_history", default, int)
    
    def set_max_alert_history(self, max_alerts: int) -> bool:
        """
        Set the maximum number of alerts to keep in history.
        
        Args:
            max_alerts: Maximum number of alerts
            
        Returns:
            True if successful, False otherwise
        """
        return self.set_setting(
            "max_alert_history", 
            max_alerts, 
            "Maximum number of alerts to keep in history"
        )
    
    def clear_cache(self) -> None:
        """Clear the settings cache."""
        self._cache.clear()
        logger.info("Settings cache cleared")
    
    def disable_cache(self) -> None:
        """Disable settings caching."""
        self._cache_enabled = False
        self.clear_cache()
        logger.info("Settings caching disabled")
    
    def enable_cache(self) -> None:
        """Enable settings caching."""
        self._cache_enabled = True
        logger.info("Settings caching enabled")
    
    def _convert_value(self, value: str, target_type: type) -> Any:
        """
        Convert string value to target type.
        
        Args:
            value: String value from database
            target_type: Target type to convert to
            
        Returns:
            Converted value
        """
        if target_type == str:
            return value
        elif target_type == int:
            return int(value)
        elif target_type == float:
            return float(value)
        elif target_type == bool:
            return value.lower() in ('true', '1', 'yes', 'on')
        else:
            raise ValueError(f"Unsupported type: {target_type}")


# Global instance for convenience
settings_manager = SettingsManager()
