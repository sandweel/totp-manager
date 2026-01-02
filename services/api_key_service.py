import secrets
import hashlib
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Tuple
from datetime import datetime
from config import async_session
from models import ApiKey, User
from services.auth import now_utc


def hash_api_key(key: str) -> str:
    """Hash API key for secure storage"""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    """Generate new API key (32 bytes, base64-encoded)"""
    # Generate 32 bytes of random data and encode in URL-safe base64
    raw_key = secrets.token_urlsafe(32)
    # Format: totp_<base64_key> for easy identification
    return f"totp_{raw_key}"


class ApiKeyService:
    @staticmethod
    async def create_api_key(user: User, name: Optional[str] = None) -> Tuple[str, ApiKey]:
        """
        Create new API key for user
        Returns: (plain_key, api_key_object)
        """
        plain_key = generate_api_key()
        key_hash = hash_api_key(plain_key)
        
        async with async_session() as session:
            api_key = ApiKey(
                user_id=user.id,
                key_hash=key_hash,
                name=name,
                created_at=now_utc()
            )
            session.add(api_key)
            await session.commit()
            await session.refresh(api_key)
            return plain_key, api_key

    @staticmethod
    async def validate_api_key(api_key: str) -> Optional[User]:
        """
        Validate API key and return user
        Returns: User if key is valid, None otherwise
        """
        key_hash = hash_api_key(api_key)
        
        async with async_session() as session:
            result = await session.execute(
                select(ApiKey, User)
                .join(User, ApiKey.user_id == User.id)
                .where(
                    ApiKey.key_hash == key_hash,
                    ApiKey.revoked_at.is_(None)
                )
            )
            row = result.first()
            
            if not row:
                return None
            
            api_key_obj, user = row
            
            # Check that user is active
            if not user.is_active or not user.is_verified:
                return None
            
            # Update last_used_at
            await session.execute(
                update(ApiKey)
                .where(ApiKey.id == api_key_obj.id)
                .values(last_used_at=now_utc())
            )
            await session.commit()
            
            return user

    @staticmethod
    async def revoke_api_key(key_id: int, user: User) -> bool:
        """
        Revoke user's API key
        Returns: True if successful, False if key not found
        """
        async with async_session() as session:
            result = await session.execute(
                select(ApiKey)
                .where(
                    ApiKey.id == key_id,
                    ApiKey.user_id == user.id,
                    ApiKey.revoked_at.is_(None)
                )
            )
            api_key = result.scalars().first()
            
            if not api_key:
                return False
            
            await session.execute(
                update(ApiKey)
                .where(ApiKey.id == key_id)
                .values(revoked_at=now_utc())
            )
            await session.commit()
            return True

    @staticmethod
    async def revoke_all_api_keys(user: User) -> int:
        """
        Revoke all user's API keys
        Returns: number of revoked keys
        """
        async with async_session() as session:
            result = await session.execute(
                update(ApiKey)
                .where(
                    ApiKey.user_id == user.id,
                    ApiKey.revoked_at.is_(None)
                )
                .values(revoked_at=now_utc())
            )
            await session.commit()
            return result.rowcount

    @staticmethod
    async def delete_api_key(key_id: int, user: User) -> bool:
        """
        Completely delete API key from database
        Returns: True if successful, False if key not found
        """
        from sqlalchemy import delete
        
        async with async_session() as session:
            result = await session.execute(
                delete(ApiKey)
                .where(
                    ApiKey.id == key_id,
                    ApiKey.user_id == user.id
                )
            )
            await session.commit()
            return result.rowcount > 0

    @staticmethod
    async def list_user_api_keys(user: User):
        """
        Get list of all user's API keys (without the keys themselves)
        """
        async with async_session() as session:
            result = await session.execute(
                select(ApiKey)
                .where(ApiKey.user_id == user.id)
                .order_by(ApiKey.created_at.desc())
            )
            api_keys = result.scalars().all()
            
            return [
                {
                    "id": key.id,
                    "name": key.name,
                    "created_at": key.created_at,
                    "last_used_at": key.last_used_at,
                    "is_revoked": key.revoked_at is not None,
                    "revoked_at": key.revoked_at
                }
                for key in api_keys
            ]

