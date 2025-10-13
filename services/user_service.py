from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Tuple
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import uuid

from config import async_session, master_fernet
from models import User
from services.auth import hash_password, verify_password, create_access_token
from services.validator import validate_email, validate_password
from constants import AppConstants
from utils import generate_fernet_key


class UserService:
    @staticmethod
    async def create_user(email: str, password: str) -> Tuple[bool, Optional[User], Optional[str]]:
        """
        Create a new user
        Returns: (success, user, error_message)
        """
        # Validate email
        email_error = validate_email(email)
        if email_error:
            return False, None, email_error
        
        # Validate password
        password_error = validate_password(password)
        if password_error:
            return False, None, password_error
        
        async with async_session() as db:
            # Check if user already exists
            result = await db.execute(select(User).where(User.email == email))
            if result.scalars().first():
                return False, None, "Email already registered"
            
            # Create user
            hashed_password = hash_password(password)
            user_dek = generate_fernet_key()
            encrypted_dek = master_fernet.encrypt(user_dek).decode()
            
            user = User(
                email=email, 
                hashed_password=hashed_password, 
                encrypted_dek=encrypted_dek
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            
            return True, user, None

    @staticmethod
    async def get_user_by_email(email: str) -> Optional[User]:
        """Get user by email"""
        async with async_session() as db:
            result = await db.execute(select(User).where(User.email == email))
            return result.scalars().first()

    @staticmethod
    async def get_user_by_id(user_id: int) -> Optional[User]:
        """Get user by ID"""
        async with async_session() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            return result.scalars().first()

    @staticmethod
    async def verify_user_credentials(email: str, password: str) -> Tuple[bool, Optional[User], Optional[str]]:
        """
        Verify user credentials
        Returns: (is_valid, user, error_message)
        """
        user = await UserService.get_user_by_email(email)
        
        if not user or not verify_password(password, user.hashed_password) or not user.is_verified:
            return False, None, "Invalid credentials or unverified email."
        
        return True, user, None

    @staticmethod
    async def confirm_email(user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Confirm user email
        Returns: (success, error_message)
        """
        async with async_session() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalars().first()
            
            if not user:
                return False, "User not found"
            
            if user.is_verified:
                return False, "Email already confirmed"
            
            user.is_verified = True
            db.add(user)
            await db.commit()
            
            return True, None

    @staticmethod
    async def request_password_reset(email: str) -> Tuple[bool, Optional[str]]:
        """
        Request password reset
        Returns: (success, error_message)
        """
        async with async_session() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalars().first()
            
            if not user:
                return True, None  # Don't reveal if user exists
            
            from services.auth import now_utc
            now = now_utc()
            
            # Check rate limiting
            if user.password_reset_requested_at and now - user.password_reset_requested_at < timedelta(minutes=AppConstants.PASSWORD_RESET_COOLDOWN_MINUTES):
                return False, f"You have recently requested a password reset. Please wait {AppConstants.PASSWORD_RESET_COOLDOWN_MINUTES} minute(s) before trying again."
            
            # Generate reset token
            reset_token_id = str(uuid.uuid4())
            user.password_reset_token_id = reset_token_id
            user.password_reset_requested_at = now
            
            db.add(user)
            await db.commit()
            
            return True, None

    @staticmethod
    async def reset_password(user_id: int, reset_token_id: str, new_password: str) -> Tuple[bool, Optional[str]]:
        """
        Reset user password
        Returns: (success, error_message)
        """
        # Validate password
        password_error = validate_password(new_password)
        if password_error:
            return False, password_error
        
        async with async_session() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalars().first()
            
            if not user:
                return False, "User not found"
            
            if not user.password_reset_token_id or user.password_reset_token_id != reset_token_id:
                return False, "Invalid or expired reset link. Please try again."
            
            # Update password
            user.hashed_password = hash_password(new_password)
            user.password_reset_token_id = None
            user.password_reset_requested_at = None
            user.is_verified = True  # Mark as verified after password reset
            
            db.add(user)
            await db.commit()
            
            return True, None

    @staticmethod
    async def change_password(user: User, current_password: str, new_password: str) -> Tuple[bool, Optional[str]]:
        """
        Change user password
        Returns: (success, error_message)
        """
        # Verify current password
        if not verify_password(current_password, user.hashed_password):
            return False, "Current password is incorrect"
        
        # Validate new password
        password_error = validate_password(new_password)
        if password_error:
            return False, password_error
        
        async with async_session() as db:
            user.hashed_password = hash_password(new_password)
            db.add(user)
            await db.commit()
            
            return True, None

    @staticmethod
    async def generate_confirmation_token(user: User) -> str:
        """Generate email confirmation token"""
        return create_access_token({"sub": str(user.id)}, expires_delta=timedelta(hours=AppConstants.EMAIL_CONFIRMATION_EXPIRE_HOURS))

    @staticmethod
    async def generate_password_reset_token(user: User) -> str:
        """Generate password reset token"""
        return create_access_token(
            {"sub": str(user.id), "reset_id": user.password_reset_token_id}, 
            expires_delta=timedelta(hours=AppConstants.PASSWORD_RESET_EXPIRE_HOURS)
        )
