from typing import Optional, Tuple
from datetime import datetime, timedelta
from jose import jwt
from jose.exceptions import JWTError, ExpiredSignatureError
from fastapi import Request, HTTPException, status
from config import settings
from services.user_service import UserService
from services.session_service import SessionService
from services.email_service import EmailService


class AuthService:
    @staticmethod
    async def register_user(email: str, password: str, confirm_password: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Register a new user
        Returns: (success, user_email, error_message)
        """
        # Validate passwords match
        if password != confirm_password:
            return False, None, "Passwords do not match"
        
        # Create user
        success, user, error = await UserService.create_user(email, password)
        if not success:
            return False, None, error
        
        # Generate confirmation token
        confirmation_token = await UserService.generate_confirmation_token(user)
        
        # Send confirmation email
        email_success, email_error = await EmailService.send_confirmation_email(email, confirmation_token)
        if not email_success:
            return False, email, f"User created but {email_error}"
        
        return True, email, None

    @staticmethod
    async def login_user(email: str, password: str, request: Request) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Login user
        Returns: (success, access_token, refresh_token, error_message)
        """
        # Verify credentials
        is_valid, user, error = await UserService.verify_user_credentials(email, password)
        if not is_valid:
            return False, None, None, error
        
        # Create session
        access_token, refresh_token, session_id = await SessionService.create_session(user, request)
        
        return True, access_token, refresh_token, None

    @staticmethod
    async def logout_user(request: Request) -> bool:
        """
        Logout user by revoking refresh token
        Returns: success
        """
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            return True
        
        try:
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            if payload.get("type") == "refresh":
                sid = payload.get("sid")
                if sid:
                    # Revoke session
                    from config import async_session
                    from models import Session as SessionDB
                    from services.auth import now_utc
                    from sqlalchemy import update
                    
                    async with async_session() as db:
                        await db.execute(
                            update(SessionDB)
                            .where(SessionDB.session_id == sid)
                            .values(revoked_at=now_utc())
                        )
                        await db.commit()
        except JWTError:
            pass
        
        return True

    @staticmethod
    async def confirm_email(token: str) -> Tuple[bool, Optional[str]]:
        """
        Confirm user email with token
        Returns: (success, error_message)
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")
        except JWTError:
            return False, "Invalid or expired token"
        
        if not user_id:
            return False, "Invalid token: User ID missing"
        
        return await UserService.confirm_email(int(user_id))

    @staticmethod
    async def request_password_reset(email: str) -> Tuple[bool, Optional[str]]:
        """
        Request password reset
        Returns: (success, error_message)
        """
        # Request reset from user service
        success, error = await UserService.request_password_reset(email)
        if not success:
            return False, error
        
        # Get user to generate token
        user = await UserService.get_user_by_email(email)
        if not user:
            return True, None  # Don't reveal if user exists
        
        # Generate reset token
        reset_token = await UserService.generate_password_reset_token(user)
        
        # Send reset email
        email_success, email_error = await EmailService.send_password_reset_email(email, reset_token)
        if not email_success:
            return False, email_error
        
        return True, None

    @staticmethod
    async def reset_password(token: str, new_password: str, confirm_password: str) -> Tuple[bool, Optional[str]]:
        """
        Reset password with token
        Returns: (success, error_message)
        """
        # Validate passwords match
        if new_password != confirm_password:
            return False, "Passwords do not match"
        
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")
            reset_id_from_token = payload.get("reset_id")
        except JWTError:
            return False, "Invalid or expired token"
        
        if not user_id or not reset_id_from_token:
            return False, "Invalid token: missing required fields"
        
        return await UserService.reset_password(int(user_id), reset_id_from_token, new_password)

    @staticmethod
    async def change_password(user, current_password: str, new_password: str, confirm_password: str) -> Tuple[bool, Optional[str]]:
        """
        Change user password
        Returns: (success, error_message)
        """
        # Validate passwords match
        if new_password != confirm_password:
            return False, "New passwords do not match"
        
        return await UserService.change_password(user, current_password, new_password)
