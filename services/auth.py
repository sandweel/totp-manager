from datetime import datetime, timedelta
from typing import Optional
from fastapi import Request, HTTPException, status, Response
from jose import jwt
from jose.exceptions import JWTError, ExpiredSignatureError
from sqlalchemy import select, update
from passlib.context import CryptContext
from config import settings, async_session
from models import User, Session as SessionDB
import hashlib
import uuid

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def now_utc():
    return datetime.utcnow()

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = now_utc() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(user_id: int, session_id: str, jti: str, expires_delta: timedelta):
    payload = {
        "sub": str(user_id),
        "sid": session_id,
        "jti": jti,
        "type": "refresh",
        "exp": now_utc() + expires_delta,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    response.set_cookie(
        "access_token",
        f"Bearer {access_token}",
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/",
    )

def clear_auth_cookies(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")

async def persist_new_session(user: User, request: Request, parent_session_id: Optional[str] = None):
    session_id = str(uuid.uuid4())
    jti = str(uuid.uuid4())
    refresh = create_refresh_token(
        user_id=user.id,
        session_id=session_id,
        jti=jti,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    async with async_session() as db:
        row = SessionDB(
            session_id=session_id,
            user_id=user.id,
            refresh_token_hash=hash_token(refresh),
            refresh_token_expires_at=now_utc() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            created_at=now_utc(),
            last_used_at=now_utc(),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            parent_session_id=parent_session_id,
        )
        db.add(row)
        await db.commit()
    access = create_access_token({"sub": str(user.id), "sid": session_id})
    return access, refresh, session_id

async def try_refresh_from_cookies(request: Request) -> Optional[User]:
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return None
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        user_id = int(payload.get("sub"))
        sid = payload.get("sid")
        jti = payload.get("jti")
        if not sid or not jti:
            return None
    except ExpiredSignatureError:
        return None
    except JWTError:
        return None
    async with async_session() as db:
        result = await db.execute(
            select(SessionDB, User).join(User, User.id == SessionDB.user_id).where(
                SessionDB.session_id == sid, SessionDB.user_id == user_id
            )
        )
        row = result.first()
        if not row:
            return None
        db_sess, user = row
        if db_sess.revoked_at is not None:
            return None
        if db_sess.replaced_by_session_id is not None:
            return None
        if db_sess.refresh_token_expires_at <= now_utc():
            return None
        if db_sess.refresh_token_hash != hash_token(refresh_token):
            return None
        parent_sid = db_sess.session_id
        access, new_refresh, new_sid = await persist_new_session(user, request, parent_session_id=parent_sid)
        await db.execute(
            update(SessionDB)
            .where(SessionDB.id == db_sess.id)
            .values(revoked_at=now_utc(), replaced_by_session_id=new_sid, last_used_at=now_utc())
        )
        await db.commit()
    request.state.new_tokens = (access, new_refresh)
    request.state.current_sid = new_sid
    return user

async def get_authenticated_user(request: Request) -> User:
    token = request.cookies.get("access_token")
    if token and " " in token:
        token = token.split(" ")[1]
    user_id = None
    try:
        if token:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            if payload.get("type") != "access":
                raise JWTError()
            user_id = payload.get("sub")
            sid = payload.get("sid")
            if sid:
                request.state.current_sid = sid
    except ExpiredSignatureError:
        user = await try_refresh_from_cookies(request)
        if user:
            return user
        raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/auth/login"})
    except JWTError:
        user = await try_refresh_from_cookies(request)
        if user:
            return user
        raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/auth/login"})
    if not user_id:
        user = await try_refresh_from_cookies(request)
        if user:
            return user
        raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/auth/login"})
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/auth/login"})
    return user

async def get_current_user_if_exists(request: Request) -> Optional[User]:
    try:
        return await get_authenticated_user(request)
    except HTTPException:
        return None
