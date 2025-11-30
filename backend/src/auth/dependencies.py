"""
FastAPI dependencies for authentication and authorization.
"""
from typing import List, Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.database.models import User, UserRole
from src.auth.security import decode_token

# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from JWT token.
    
    Raises:
        HTTPException: If token is missing, invalid, or user not found
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user = db.query(User).filter(User.username == username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User | None:
    """
    Get the current user if authenticated, or None if not.
    Useful for endpoints that work with or without authentication.
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def get_user_roles_from_token(authorization: str | None, db: Session) -> List[str]:
    """
    Extract user roles from JWT token without raising exceptions.
    
    Useful for optional access control where you want to check permissions
    but not require authentication.
    
    Args:
        authorization: The Authorization header value (e.g., "Bearer <token>")
        db: Database session
        
    Returns:
        List of role strings if token is valid, empty list otherwise
    """
    if not authorization or not authorization.startswith("Bearer "):
        return []
    
    token = authorization.replace("Bearer ", "")
    try:
        payload = decode_token(token)
        if not payload:
            return []
        username = payload.get("sub")
        if not username:
            return []
        
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return []
        
        # Return role values as strings (not UserRole enums)
        return [r.value if hasattr(r, 'value') else str(r) for r in user.get_roles()]
    except Exception:
        return []


def require_roles(allowed_roles: List[UserRole]) -> Callable:
    """
    Dependency factory for role-based access control.
    
    Args:
        allowed_roles: List of roles that are allowed to access the endpoint.
                       User must have at least ONE of these roles.
        
    Returns:
        Dependency function that validates user has at least one required role
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if not current_user.has_any_role(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles (any of): {[r.value for r in allowed_roles]}"
            )
        return current_user
    return role_checker


# Convenience dependencies for common role patterns
require_admin = require_roles([UserRole.ADMIN])
require_user_or_admin = require_roles([UserRole.ADMIN, UserRole.USER])
require_any_role = require_roles([UserRole.ADMIN, UserRole.USER, UserRole.VIEWER])
