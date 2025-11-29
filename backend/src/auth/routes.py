"""
Authentication API routes.
Provides login, registration, token refresh, and user management endpoints.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field

from src.database.database import get_db
from src.database.models import User, UserRole
from src.api.models import ApiResponse, ApiListResponse
from src.api.response_utils import success_response, list_response, bad_request_error, not_found_error, internal_server_error
from src.utils.logging import get_logger
from src.auth.security import verify_password, hash_password, create_access_token, create_refresh_token, decode_token
from src.auth.dependencies import get_current_user, require_admin

logger = get_logger(__name__)
router = APIRouter(prefix="/api/auth", tags=["authentication"])


# =============================================================================
# Request/Response Models
# =============================================================================

class LoginRequest(BaseModel):
    """Login request payload."""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    """User registration request payload."""
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr
    password: str = Field(..., min_length=4, max_length=100)


class RefreshRequest(BaseModel):
    """Token refresh request payload."""
    refresh_token: str


class UpdateUserRequest(BaseModel):
    """User update request payload (admin only)."""
    email: Optional[EmailStr] = None
    roles: Optional[List[UserRole]] = None
    is_active: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    """Password change request payload."""
    current_password: str
    new_password: str = Field(..., min_length=4, max_length=100)


# =============================================================================
# Public Authentication Endpoints
# =============================================================================

@router.post("/login", response_model=ApiResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user and return JWT tokens.
    
    Returns access_token (short-lived) and refresh_token (long-lived).
    """
    try:
        user = db.query(User).filter(User.username == request.username).first()
        
        if not user or not verify_password(request.password, user.password_hash):
            raise bad_request_error("Invalid username or password")
        
        if not user.is_active:
            raise bad_request_error("User account is disabled")
        
        # Create tokens with user info
        token_data = {"sub": user.username, "roles": user.roles or []}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token({"sub": user.username})
        
        logger.info("✅ User '%s' logged in successfully", user.username)
        
        return success_response({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user.to_dict()
        }, "Login successful")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Login error: %s", e)
        raise internal_server_error("Login failed", str(e))


@router.post("/register", response_model=ApiResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user account.
    
    New users are assigned the USER role by default.
    """
    try:
        # Check if username already exists
        if db.query(User).filter(User.username == request.username).first():
            raise bad_request_error("Username already exists")
        
        # Check if email already exists
        if db.query(User).filter(User.email == request.email).first():
            raise bad_request_error("Email already registered")
        
        # Create new user with USER role by default
        user = User(
            username=request.username,
            email=request.email,
            password_hash=hash_password(request.password),
            roles=[UserRole.USER.value],
            is_active=True
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info("✅ New user registered: %s (%s)", user.username, user.email)
        
        return success_response(user.to_dict(), "Registration successful")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Registration error: %s", e)
        db.rollback()
        raise internal_server_error("Registration failed", str(e))


@router.post("/refresh", response_model=ApiResponse)
async def refresh_token(request: RefreshRequest, db: Session = Depends(get_db)):
    """
    Refresh access token using a valid refresh token.
    
    Returns a new access token (refresh token remains the same).
    """
    try:
        payload = decode_token(request.refresh_token)
        
        if not payload:
            raise bad_request_error("Invalid or expired refresh token")
        
        if payload.get("type") != "refresh":
            raise bad_request_error("Invalid token type")
        
        username = payload.get("sub")
        if not username:
            raise bad_request_error("Invalid token payload")
        
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            raise bad_request_error("User not found")
        
        if not user.is_active:
            raise bad_request_error("User account is disabled")
        
        # Create new access token
        token_data = {"sub": user.username, "roles": user.roles or []}
        access_token = create_access_token(token_data)
        
        logger.info("✅ Token refreshed for user '%s'", user.username)
        
        return success_response({
            "access_token": access_token,
            "token_type": "bearer"
        }, "Token refreshed")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Token refresh error: %s", e)
        raise internal_server_error("Token refresh failed", str(e))


# =============================================================================
# Authenticated User Endpoints
# =============================================================================

@router.get("/me", response_model=ApiResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information."""
    return success_response(current_user.to_dict(), "User info retrieved")


@router.post("/logout", response_model=ApiResponse)
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout current user.
    
    Note: JWT tokens are stateless, so the client should discard the tokens.
    This endpoint is provided for logging purposes and future token blacklisting.
    """
    logger.info("✅ User '%s' logged out", current_user.username)
    return success_response(None, "Logout successful")


@router.post("/change-password", response_model=ApiResponse)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change the current user's password."""
    try:
        # Verify current password
        if not verify_password(request.current_password, current_user.password_hash):
            raise bad_request_error("Current password is incorrect")
        
        # Update password
        current_user.password_hash = hash_password(request.new_password)
        db.commit()
        
        logger.info("✅ Password changed for user '%s'", current_user.username)
        
        return success_response(None, "Password changed successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Password change error: %s", e)
        db.rollback()
        raise internal_server_error("Password change failed", str(e))


# =============================================================================
# Admin User Management Endpoints
# =============================================================================

@router.get("/users", response_model=ApiListResponse)
async def list_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all users (admin only)."""
    try:
        users = db.query(User).order_by(User.created_at.desc()).all()
        return list_response([u.to_dict() for u in users], "Users retrieved")
    except Exception as e:
        logger.error("❌ Error listing users: %s", e)
        raise internal_server_error("Failed to list users", str(e))


@router.get("/users/{user_id}", response_model=ApiResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get a specific user by ID (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise not_found_error("User not found")
    return success_response(user.to_dict(), "User retrieved")


@router.patch("/users/{user_id}", response_model=ApiResponse)
async def update_user(
    user_id: int,
    request: UpdateUserRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update a user's information (admin only)."""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise not_found_error("User not found")
        
        changes = []
        
        if request.email is not None and request.email != user.email:
            # Check email uniqueness
            if db.query(User).filter(User.email == request.email, User.id != user_id).first():
                raise bad_request_error("Email already in use")
            user.email = request.email
            changes.append(f"email -> {request.email}")
        
        if request.roles is not None:
            new_roles = [r.value for r in request.roles]
            if new_roles != user.roles:
                user.roles = new_roles
                changes.append(f"roles -> {new_roles}")
        
        if request.is_active is not None and request.is_active != user.is_active:
            # Prevent admin from disabling themselves
            if user.id == current_user.id and not request.is_active:
                raise bad_request_error("Cannot disable your own account")
            user.is_active = request.is_active
            changes.append(f"is_active -> {request.is_active}")
        
        if changes:
            db.commit()
            db.refresh(user)
            logger.info("✅ User '%s' updated by admin '%s': %s", 
                       user.username, current_user.username, "; ".join(changes))
        
        return success_response(user.to_dict(), "User updated")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Error updating user: %s", e)
        db.rollback()
        raise internal_server_error("Failed to update user", str(e))


@router.delete("/users/{user_id}", response_model=ApiResponse)
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a user (admin only)."""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise not_found_error("User not found")
        
        # Prevent admin from deleting themselves
        if user.id == current_user.id:
            raise bad_request_error("Cannot delete your own account")
        
        username = user.username
        db.delete(user)
        db.commit()
        
        logger.info("✅ User '%s' deleted by admin '%s'", username, current_user.username)
        
        return success_response(None, f"User '{username}' deleted")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Error deleting user: %s", e)
        db.rollback()
        raise internal_server_error("Failed to delete user", str(e))


@router.post("/users/{user_id}/reset-password", response_model=ApiResponse)
async def reset_user_password(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Reset a user's password to a temporary password (admin only).
    
    Returns the temporary password that should be shared with the user.
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise not_found_error("User not found")
        
        # Generate temporary password (username + "123")
        temp_password = f"{user.username}123"
        user.password_hash = hash_password(temp_password)
        db.commit()
        
        logger.info("✅ Password reset for user '%s' by admin '%s'", 
                   user.username, current_user.username)
        
        return success_response({
            "username": user.username,
            "temporary_password": temp_password,
            "message": "User should change password after login"
        }, "Password reset successful")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Error resetting password: %s", e)
        db.rollback()
        raise internal_server_error("Failed to reset password", str(e))
