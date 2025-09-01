"""
Timestamp utilities for data connectors.
Shared functions for handling various timestamp formats in ingested data.
"""
from datetime import datetime, timezone
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


def extract_timestamp(timestamp_value: Any, default_to_now: bool = True) -> str:
    """Extract and normalize timestamp from data source.
    
    This utility handles various timestamp formats commonly found in IoT data:
    - ISO format strings (with or without 'Z' timezone)
    - Unix timestamps (int or float)
    - Datetime objects
    - None/missing values
    - Invalid formats
    
    Args:
        timestamp_value: The timestamp value from data source
        default_to_now: Whether to return current time for None/invalid values
        
    Returns:
        ISO format timestamp string or empty string
        
    Examples:
        >>> extract_timestamp("2025-09-01T18:05:10Z")
        "2025-09-01T18:05:10+00:00"
        
        >>> extract_timestamp(1725212710)
        "2025-09-01T18:05:10+00:00"
        
        >>> extract_timestamp(1725212710.123)
        "2025-09-01T18:05:10.123000+00:00"
    """
    if timestamp_value is None:
        return datetime.now(timezone.utc).isoformat() if default_to_now else ""
    
    try:
        # Handle different timestamp formats
        if isinstance(timestamp_value, str):
            # Try to parse ISO format strings
            try:
                dt = datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
                return dt.isoformat()
            except ValueError:
                # If parsing fails, use current time or None
                logger.warning(f"⚠️ Could not parse timestamp string: {timestamp_value}")
                return datetime.now(timezone.utc).isoformat() if default_to_now else ""
                
        elif isinstance(timestamp_value, (int, float)):
            # Handle Unix timestamps
            dt = datetime.fromtimestamp(timestamp_value, tz=timezone.utc)
            return dt.isoformat()
            
        elif hasattr(timestamp_value, 'isoformat'):
            # Already a datetime object
            return timestamp_value.isoformat()
            
        else:
            logger.warning(f"⚠️ Unknown timestamp type {type(timestamp_value)}: {timestamp_value}")
            return datetime.now(timezone.utc).isoformat() if default_to_now else ""
            
    except Exception as e:
        logger.warning(f"⚠️ Error processing timestamp {timestamp_value}: {e}")
        return datetime.now(timezone.utc).isoformat() if default_to_now else ""


def ensure_datetime(timestamp_value: Any) -> datetime:
    """Ensure a timestamp value is converted to a datetime object.
    
    Args:
        timestamp_value: The timestamp value to convert
        
    Returns:
        datetime object in UTC timezone
    """
    if timestamp_value is None:
        return datetime.now(timezone.utc)
    
    try:
        if isinstance(timestamp_value, str):
            # Try to parse ISO format strings
            try:
                return datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
            except ValueError:
                logger.warning(f"⚠️ Could not parse timestamp string: {timestamp_value}")
                return datetime.now(timezone.utc)
                
        elif isinstance(timestamp_value, (int, float)):
            # Handle Unix timestamps
            return datetime.fromtimestamp(timestamp_value, tz=timezone.utc)
            
        elif hasattr(timestamp_value, 'isoformat'):
            # Already a datetime object
            return timestamp_value
            
        else:
            logger.warning(f"⚠️ Unknown timestamp type {type(timestamp_value)}: {timestamp_value}")
            return datetime.now(timezone.utc)
            
    except Exception as e:
        logger.warning(f"⚠️ Error processing timestamp {timestamp_value}: {e}")
        return datetime.now(timezone.utc)
