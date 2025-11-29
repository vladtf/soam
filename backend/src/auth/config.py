"""
Authentication configuration settings.
"""
import os
from dataclasses import dataclass


@dataclass
class AuthSettings:
    """Authentication settings with environment variable support."""
    SECRET_KEY: str = os.getenv("AUTH_SECRET_KEY", "soam-dev-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("AUTH_REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    
    # Default admin credentials (should be changed in production)
    DEFAULT_ADMIN_USERNAME: str = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin")
    DEFAULT_ADMIN_EMAIL: str = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@soam.local")


# Global settings instance
auth_settings = AuthSettings()
