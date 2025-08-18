from fastapi import APIRouter, Request, Form, Depends, HTTPException, status, Response
from fastapi.responses import RedirectResponse, HTMLResponse
from cryptography.fernet import Fernet
from passlib.context import CryptContext
from jose import jwt
from jose.exceptions import JWTError, ExpiredSignatureError
from datetime import datetime, timedelta
from sqlalchemy import select, update
from typing import Optional
from config import settings, async_session, templates, master_fernet, http_client
from models import User, Session as SessionDB
from services.flash import flash, get_flashed_message
from services.validator import validate_password
import uuid
import hashlib

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter(prefix="/auth", tags=["auth"])

def now_utc():
    return datetime.utcnow()

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

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

@router.get("/register", response_class=HTMLResponse)
async def get_register(request: Request, user: Optional[User] = Depends(get_current_user_if_exists)):
    if user:
        return RedirectResponse(url="/totp/list", status_code=status.HTTP_303_SEE_OTHER)
    flash_data = get_flashed_message(request)
    return templates.TemplateResponse("auth/register.html", {"request": request, "flash": flash_data, "user": user})

@router.post("/register", response_class=HTMLResponse)
async def post_register(request: Request, email: str = Form(...), password: str = Form(...), confirm_password: str = Form(...),
                        user: Optional[User] = Depends(get_current_user_if_exists)):
    if user:
        return RedirectResponse(url="/totp/list", status_code=status.HTTP_303_SEЕ_OTHER)
    if password != confirm_password:
        flash(request, "Passwords do not match", "error")
        flash_data = get_flashed_message(request)
        return templates.TemplateResponse("auth/register.html",
                                          {"request": request, "flash": flash_data, "email": email},
                                          status_code=status.HTTP_303_SEЕ_OTHER)
    error_msg = validate_password(password)
    if error_msg:
        flash(request, error_msg, "error")
        flash_data = get_flashed_message(request)
        return templates.TemplateResponse("auth/register.html",
                                          {"request": request, "flash": flash_data, "email": email},
                                          status_code=status.HTTP_303_SEЕ_OTHER)
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email))
        if result.scalars().first():
            flash(request, "Email already registered", "error")
            return RedirectResponse(url="/auth/register", status_code=status.HTTP_303_SEЕ_OTHER)
        hashed_password = pwd_context.hash(password)
        user_dek = Fernet.generate_key()
        encrypted_dek = master_fernet.encrypt(user_dek).decode()
        user = User(email=email, hashed_password=hashed_password, encrypted_dek=encrypted_dek)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    confirm_token = create_access_token({"sub": str(user.id)}, expires_delta=timedelta(hours=24))
    link = f"{settings.FRONTEND_URL}/auth/confirm?token={confirm_token}"
    try:
        html_content = templates.get_template("email/confirmation_email.html").render(link=link, year=datetime.now().year)
        await http_client.post(
            f"https://api.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages",
            auth=("api", settings.MAILGUN_API_KEY),
            data={"from": f"no-reply@{settings.MAILGUN_DOMAIN}", "to": [email], "subject": "Confirm your account",
                  "html": html_content}
        )
        flash(request, "Confirmation email sent. Please check your email", "success")
    except Exception:
        flash(request, "Failed to send confirmation email. Please try again.", "error")
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEЕ_OTHER)

@router.get("/confirm")
async def confirm_email(request: Request, token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
    except JWTError:
        flash(request, "Invalid or expired token", "error")
        return RedirectResponse(url="/auth/login", status_code=302)
    if user_id is None:
        flash(request, "Invalid token: User ID missing", "error")
        return RedirectResponse(url="/auth/login", status_code=302)
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalars().first()
        if not user:
            flash(request, "User not found", "error")
            return RedirectResponse(url="/auth/login", status_code=302)
        if user.is_verified:
            flash(request, "Email already confirmed", "info")
            return RedirectResponse(url="/auth/login", status_code=302)
        user.is_verified = True
        db.add(user)
        await db.commit()
    flash(request, "Email successfully confirmed!", "success")
    return RedirectResponse(url="/auth/login", status_code=302)

@router.get("/login", response_class=HTMLResponse)
async def get_login(request: Request, user: Optional[User] = Depends(get_current_user_if_exists)):
    if user:
        return RedirectResponse(url="/totp/list", status_code=status.HTTP_303_SEЕ_OTHER)
    flash_data = get_flashed_message(request)
    return templates.TemplateResponse("auth/login.html", {"request": request, "flash": flash_data, "user": user})

@router.post("/login")
async def post_login(request: Request, response: Response, email: str = Form(...), password: str = Form(...),
                     user: Optional[User] = Depends(get_current_user_if_exists)):
    if user:
        return RedirectResponse(url="/totp/list", status_code=status.HTTP_303_SEЕ_OTHER)
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
    if not user or not pwd_context.verify(password, user.hashed_password) or not user.is_verified:
        flash(request, "Invalid credentials or unverified email.", "error")
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "email": email, "flash": get_flashed_message(request)},
            status_code=status.HTTP_303_SEЕ_OTHER
        )
    access, refresh, _sid = await persist_new_session(user, request)
    redirect_response = RedirectResponse(url="/totp/list", status_code=status.HTTP_302_FOUND)
    set_auth_cookies(redirect_response, access, refresh)
    return redirect_response

@router.get("/logout")
async def logout(request: Request):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            if payload.get("type") == "refresh":
                sid = payload.get("sid")
                async with async_session() as db:
                    await db.execute(
                        update(SessionDB)
                        .where(SessionDB.session_id == sid)
                        .values(revoked_at=now_utc())
                    )
                    await db.commit()
        except JWTError:
            pass
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    clear_auth_cookies(response)
    return response

@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_request(request: Request, user: Optional[User] = Depends(get_current_user_if_exists)):
    if user:
        return RedirectResponse(url="/totp/list", status_code=status.HTTP_303_SEЕ_OTHER)
    flash_data = get_flashed_message(request)
    return templates.TemplateResponse("auth/reset_password_request.html", {"request": request, "flash": flash_data, "user": user})

@router.post("/reset-password")
async def send_reset_email(request: Request, email: str = Form(...),
                           user: Optional[User] = Depends(get_current_user_if_exists)):
    if user:
        return RedirectResponse(url="/totp/list", status_code=status.HTTP_303_SEЕ_OTHER)
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        if user:
            now = now_utc()
            if user.password_reset_requested_at and now - user.password_reset_requested_at < timedelta(minutes=1):
                flash(request, "You have recently requested a password reset. Please wait a minute before trying again.", "error")
                return RedirectResponse(url="/auth/reset-password", status_code=status.HTTP_303_SEЕ_OTHER)
            reset_token_id = str(uuid.uuid4())
            user.password_reset_token_id = reset_token_id
            user.password_reset_requested_at = now
            db.add(user)
            await db.commit()
            token = create_access_token({"sub": str(user.id), "reset_id": reset_token_id}, expires_delta=timedelta(hours=1))
            link = f"{settings.FRONTEND_URL}/auth/reset-password/confirm?token={token}"
            try:
                html_content = templates.get_template("email/reset_password_email.html").render(link=link, year=datetime.now().year)
                await http_client.post(
                    f"https://api.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages",
                    auth=("api", settings.MAILGUN_API_KEY),
                    data={"from": f"no-reply@{settings.MAILGUN_DOMAIN}", "to": [email], "subject": "Reset your password",
                          "html": html_content}
                )
                flash(request, "If email exists, reset link sent. Check your inbox.", "success")
            except Exception:
                flash(request, "Failed to send reset email. Please try again.", "error")
        else:
            flash(request, "If email exists, reset link sent. Check your inbox.", "success")
    return RedirectResponse(url="/auth/reset-password", status_code=status.HTTP_303_SEЕ_OTHER)

@router.get("/reset-password/confirm", response_class=HTMLResponse)
async def reset_password_form(request: Request, token: str,
                              user: Optional[User] = Depends(get_current_user_if_exists)):
    if user:
        return RedirectResponse(url="/totp/list", status_code=status.HTTP_303_SEЕ_OTHER)
    flash_data = get_flashed_message(request)
    return templates.TemplateResponse("auth/reset_password.html", {"request": request, "token": token, "flash": flash_data, "user": user})

@router.post("/reset-password/confirm")
async def reset_password(request: Request, token: str = Form(...), password: str = Form(...),
                         confirm_password: str = Form(...),
                         user: Optional[User] = Depends(get_current_user_if_exists)):
    if user:
        return RedirectResponse(url="/totp/list", status_code=status.HTTP_303_SEЕ_OTHER)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        reset_id_from_token = payload.get("reset_id")
        if not reset_id_from_token:
            flash(request, "Invalid token: missing reset ID", "error")
            return RedirectResponse(url="/auth/reset-password", status_code=302)
    except JWTError:
        flash(request, "Invalid or expired token", "error")
        return RedirectResponse(url="/auth/reset-password", status_code=302)
    if user_id is None:
        flash(request, "Invalid token: User ID missing", "error")
        return RedirectResponse(url="/auth/reset-password", status_code=302)
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalars().first()
        if not user:
            flash(request, "User not found", "error")
            return RedirectResponse(url="/auth/reset-password", status_code=302)
        if not user.password_reset_token_id or user.password_reset_token_id != reset_id_from_token:
            flash(request, "Invalid or expired reset link. Please try again.", "error")
            return RedirectResponse(url="/auth/reset-password", status_code=302)
        if password != confirm_password:
            flash(request, "Passwords do not match", "error")
            flash_data = get_flashed_message(request)
            return templates.TemplateResponse("auth/reset_password.html", {"request": request, "flash": flash_data, "token": token})
        error_msg = validate_password(password)
        if error_msg:
            flash(request, error_msg, "error")
            flash_data = get_flashed_message(request)
            return templates.TemplateResponse("auth/reset_password.html", {"request": request, "flash": flash_data, "token": token})
        user.hashed_password = pwd_context.hash(password)
        user.password_reset_token_id = None
        user.password_reset_requested_at = None
        user.is_verified = True
        db.add(user)
        await db.commit()
    flash(request, "Password reset successfully. You can now log in.", "success")
    return RedirectResponse(url="/auth/login", status_code=302)
