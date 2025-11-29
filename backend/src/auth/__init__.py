"""
Authentication and authorization module for SOAM.
Provides JWT-based authentication with role-based access control.
"""
from src.auth.dependencies import get_current_user, require_roles, require_admin, require_user_or_admin, require_any_role
from src.auth.security import verify_password, hash_password, create_access_token, create_refresh_token
from src.database.models import UserRole, User

__all__ = [
    "get_current_user",
    "require_roles",
    "require_admin",
    "require_user_or_admin",
    "require_any_role",
    "verify_password",
    "hash_password",
    "create_access_token",
    "create_refresh_token",
    "UserRole",
    "User",
]
