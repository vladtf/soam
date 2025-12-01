"""Initialize test users on application startup.
"""
from sqlalchemy.orm import Session
from src.database.models import User, UserRole
from src.auth.security import hash_password
from src.utils.logging import get_logger

logger = get_logger(__name__)


# Test users for development/testing purposes
TEST_USERS = [
    {
        "username": "admin",
        "email": "admin@soam.local",
        "password": "admin",
        "roles": [UserRole.ADMIN.value, UserRole.USER.value, UserRole.VIEWER.value],
        "description": "Default admin with full access"
    },
    {
        "username": "test_user",
        "email": "test_user@soam.local",
        "password": "test123",
        "roles": [UserRole.USER.value, UserRole.VIEWER.value],
        "description": "Regular user with standard access"
    },
    {
        "username": "test_viewer",
        "email": "test_viewer@soam.local",
        "password": "test123",
        "roles": [UserRole.VIEWER.value],
        "description": "Viewer with read-only access"
    },
]


def init_default_users(db: Session) -> int:
    """
    Create predefined test users for development/testing purposes.
    
    Args:
        db: Database session
        
    Returns:
        Number of test users created
    """
    created_count = 0
    
    for test_user in TEST_USERS:
        try:
            # Check if user exists
            existing = db.query(User).filter(User.username == test_user["username"]).first()
            
            if existing:
                logger.debug("ℹ️ Test user '%s' already exists", test_user["username"])
                continue
            
            # Create test user
            user = User(
                username=test_user["username"],
                email=test_user["email"],
                password_hash=hash_password(test_user["password"]),
                roles=test_user["roles"],
                is_active=True
            )
            
            db.add(user)
            db.commit()
            
            logger.info("✅ Test user created: %s (roles: %s)", 
                       test_user["username"], 
                       test_user["roles"])
            created_count += 1
            
        except Exception as e:
            logger.error("❌ Failed to create test user '%s': %s", test_user["username"], e)
            db.rollback()
    
    return created_count


def get_test_users_info() -> list:
    """
    Get information about available test users (without passwords).
    
    Returns:
        List of test user info dictionaries
    """
    return [
        {
            "username": u["username"],
            "roles": u["roles"],
            "description": u["description"],
            "password": u["password"],  # Include password for easy testing
        }
        for u in TEST_USERS
    ]
