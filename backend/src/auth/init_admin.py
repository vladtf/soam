"""
Initialize default admin user on application startup.
"""
from sqlalchemy.orm import Session
from src.database.models import User, UserRole
from src.auth.security import hash_password
from src.auth.config import auth_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


def init_default_admin(db: Session) -> bool:
    """
    Create the default admin user if it doesn't exist.
    
    Args:
        db: Database session
        
    Returns:
        True if admin was created, False if already exists
    """
    try:
        # Check if admin user exists
        admin = db.query(User).filter(User.username == auth_settings.DEFAULT_ADMIN_USERNAME).first()
        
        if admin:
            logger.info("ℹ️ Admin user '%s' already exists", auth_settings.DEFAULT_ADMIN_USERNAME)
            return False
        
        # Create default admin user with all roles
        admin = User(
            username=auth_settings.DEFAULT_ADMIN_USERNAME,
            email=auth_settings.DEFAULT_ADMIN_EMAIL,
            password_hash=hash_password(auth_settings.DEFAULT_ADMIN_PASSWORD),
            roles=[UserRole.ADMIN.value, UserRole.USER.value, UserRole.VIEWER.value],
            is_active=True
        )
        
        db.add(admin)
        db.commit()
        
        logger.info("✅ Default admin user created: %s (password: %s)", 
                   auth_settings.DEFAULT_ADMIN_USERNAME, 
                   auth_settings.DEFAULT_ADMIN_PASSWORD)
        
        return True
        
    except Exception as e:
        logger.error("❌ Failed to create default admin user: %s", e)
        db.rollback()
        raise
