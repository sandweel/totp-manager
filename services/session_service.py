from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Tuple, List
from datetime import datetime, timedelta
import uuid

from config import async_session
from models import Session as SessionDB, User
from services.auth import now_utc, hash_token, create_refresh_token, create_access_token
from services.geoip import get_location_from_ip, format_location, get_country_flag
from constants import AppConstants


class SessionService:
    @staticmethod
    async def create_session(user: User, request, parent_session_id: Optional[str] = None) -> Tuple[str, str, str]:
        """
        Create a new session
        Returns: (access_token, refresh_token, session_id)
        """
        async with async_session() as db:
            session_id = str(uuid.uuid4())
            jti = str(uuid.uuid4())
            
            refresh_token = create_refresh_token(
                user_id=user.id,
                session_id=session_id,
                jti=jti,
                expires_delta=timedelta(days=AppConstants.REFRESH_TOKEN_EXPIRE_DAYS)
            )
            
            session = SessionDB(
                session_id=session_id,
                user_id=user.id,
                refresh_token_hash=hash_token(refresh_token),
                refresh_token_expires_at=now_utc() + timedelta(days=AppConstants.REFRESH_TOKEN_EXPIRE_DAYS),
                created_at=now_utc(),
                last_used_at=now_utc(),
                ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                parent_session_id=parent_session_id,
            )
            
            db.add(session)
            await db.commit()
            
            access_token = create_access_token({"sub": str(user.id), "sid": session_id})
            
            return access_token, refresh_token, session_id

    @staticmethod
    async def revoke_session(session_id: str, user: User) -> Tuple[bool, Optional[str]]:
        """
        Revoke a specific session
        Returns: (success, error_message)
        """
        async with async_session() as db:
            result = await db.execute(
                select(SessionDB).where(
                    SessionDB.user_id == user.id, 
                    SessionDB.session_id == session_id
                )
            )
            session = result.scalars().first()
            
            if not session:
                return False, "Session not found"
            
            if session.revoked_at is None:
                await db.execute(
                    update(SessionDB)
                    .where(SessionDB.id == session.id)
                    .values(revoked_at=now_utc())
                )
                await db.commit()
            
            return True, None

    @staticmethod
    async def revoke_all_sessions(user: User) -> bool:
        """
        Revoke all sessions for a user
        Returns: success
        """
        async with async_session() as db:
            await db.execute(
                update(SessionDB)
                .where(
                    SessionDB.user_id == user.id, 
                    SessionDB.revoked_at.is_(None)
                )
                .values(revoked_at=now_utc())
            )
            await db.commit()
            return True

    @staticmethod
    async def get_user_sessions(user: User) -> List[dict]:
        """
        Get all sessions for a user with location info
        Returns: List of session dictionaries with location data
        """
        async with async_session() as db:
            result = await db.execute(
                select(SessionDB).where(SessionDB.user_id == user.id)
            )
            sessions = result.scalars().all()
            
            sessions_with_location = []
            for session in sessions:
                location = get_location_from_ip(session.ip) if session.ip else None
                flag = get_country_flag(location.get('country_code')) if location else "🏳️"
                
                sessions_with_location.append({
                    'session': session,
                    'location': format_location(location),
                    'flag': flag
                })
            
            return sessions_with_location

    @staticmethod
    async def revoke_session_by_token_hash(token_hash: str) -> bool:
        """
        Revoke session by refresh token hash
        Returns: success
        """
        async with async_session() as db:
            await db.execute(
                update(SessionDB)
                .where(SessionDB.refresh_token_hash == token_hash)
                .values(revoked_at=now_utc())
            )
            await db.commit()
            return True
