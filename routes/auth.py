from fastapi import APIRouter, Request, Form, Depends, HTTPException, status, Response
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from cryptography.fernet import Fernet
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from sqlalchemy import select, update
from typing import Optional
from config import settings, async_session, templates, master_fernet, http_client
from models import User, AuthSession
from services.flash import flash, get_flashed_message
from services.validator import validate_password
import uuid
import secrets
import hashlib

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter(prefix="/auth", tags=["auth"])

def now_utc():
    return datetime.utcnow()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = now_utc() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def gen_refresh_token():
    return secrets.token_urlsafe(48)

def hash_refresh_token(raw: str):
    pepper = settings.REFRESH_TOKEN_PEPPER or settings.SECRET_KEY or ""
    return hashlib.sha256((raw + pepper).encode()).hexdigest()

def set_access_cookie(resp: Response, token: str):
    resp.set_cookie(
        settings.ACCESS_TOKEN_COOKIE_NAME,
        f"Bearer {token}",
        httponly=True,
        secure=True,
        samesite="lax",
        path="/"
    )

def set_refresh_cookie(resp: Response, token: str):
    resp.set_cookie(
        settings.REFRESH_TOKEN_COOKIE_NAME,
        token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    )

def set_csrf_refresh_cookie(resp: Response, token: str):
    resp.set_cookie(
        settings.CSRF_REFRESH_COOKIE_NAME,
        token,
        httponly=False,
        secure=True,
        samesite="lax",
        path="/auth/refresh",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    )

def clear_auth_cookies(resp: Response):
    resp.delete_cookie(settings.ACCESS_TOKEN_COOKIE_NAME, path="/")
    resp.delete_cookie(settings.REFRESH_TOKEN_COOKIE_NAME, path="/")
    resp.delete_cookie(settings.CSRF_REFRESH_COOKIE_NAME, path="/auth/refresh")

def set_auth_cookies_in_response_if_needed(request: Request, response: Response):
    data = getattr(request.state, "new_auth_cookies", None)
    if not data:
        return
    set_access_cookie(response, data["access"])
    set_refresh_cookie(response, data["refresh"])
    set_csrf_refresh_cookie(response, data["csrf"])

async def create_session_and_tokens(request: Request, user: User):
    session_id = str(uuid.uuid4())
    refresh_raw = gen_refresh_token()
    refresh_hash = hash_refresh_token(refresh_raw)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:256]
    async with async_session() as session:
        db_sess = AuthSession(
            id=session_id,
            user_id=user.id,
            refresh_token_hash=refresh_hash,
            created_at=now_utc(),
            last_used_at=now_utc(),
            expires_at=now_utc() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            ip=ip,
            user_agent=ua,
            revoked_at=None,
            replaced_by_session_id=None
        )
        session.add(db_sess)
        await session.commit()
    access = create_access_token({"sub": str(user.id), "sid": session_id}, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    csrf = secrets.token_urlsafe(24)
    return access, refresh_raw, csrf, session_id

async def rotate_refresh(existing: AuthSession):
    new_raw = gen_refresh_token()
    new_hash = hash_refresh_token(new_raw)
    existing.refresh_token_hash = new_hash
    existing.last_used_at = now_utc()
    existing.expires_at = now_utc() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return new_raw

async def try_refresh_from_cookies(request: Request):
    refresh_raw = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if not refresh_raw:
        return None
    refresh_hash = hash_refresh_token(refresh_raw)
    async with async_session() as session:
        result = await session.execute(select(AuthSession).where(AuthSession.refresh_token_hash == refresh_hash))
        db_sess = result.scalars().first()
        if not db_sess:
            return None
        if db_sess.revoked_at is not None:
            return None
        if db_sess.expires_at <= now_utc():
            return None
        result = await session.execute(select(User).where(User.id == db_sess.user_id))
        user = result.scalars().first()
        if not user:
            return None
        new_refresh_raw = await rotate_refresh(db_sess)
        session.add(db_sess)
        await session.commit()
        access = create_access_token({"sub": str(user.id), "sid": db_sess.id}, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        csrf = secrets.token_urlsafe(24)
        return {"user": user, "access": access, "refresh": new_refresh_raw, "csrf": csrf}

async def get_authenticated_user(request: Request) -> User:
    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if token:
        try:
            token_value = token.split(" ")[1] if " " in token else token
            payload = jwt.decode(token_value, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")
            if user_id is not None:
                async with async_session() as session:
                    result = await session.execute(select(User).where(User.id == int(user_id)))
                    user = result.scalars().first()
                if user:
                    return user
        except JWTError:
            pass
    refreshed = await try_refresh_from_cookies(request)
    if refreshed:
        request.state.new_auth_cookies = {"access": refreshed["access"], "refresh": refreshed["refresh"], "csrf": refreshed["csrf"]}
        return refreshed["user"]
    raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/auth/login"})

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
        return RedirectResponse(url="/totp/list", status_code=status.HTTP_303_SEE_OTHER)
    if password != confirm_password:
        flash(request, "Passwords do not match", "error")
        flash_data = get_flashed_message(request)
        return templates.TemplateResponse("auth/register.html",
                                          {"request": request, "flash": flash_data, "email": email},
                                          status_code=status.HTTP_303_SEE_OTHER)
    error_msg = validate_password(password)
    if error_msg:
        flash(request, error_msg, "error")
        flash_data = get_flashed_message(request)
        return templates.TemplateResponse("auth/register.html",
                                          {"request": request, "flash": flash_data, "email": email},
                                          status_code=status.HTTP_303_SEE_OTHER)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        if result.scalars().first():
            flash(request, "Email already registered", "error")
            return RedirectResponse(url="/auth/register", status_code=status.HTTP_303_SEE_OTHER)
        hashed_password = pwd_context.hash(password)
        user_dek = Fernet.generate_key()
        encrypted_dek = master_fernet.encrypt(user_dek).decode()
        user = User(email=email, hashed_password=hashed_password, encrypted_dek=encrypted_dek)
        session.add(user)
        await session.commit()
        await session.refresh(user)
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
    except Exception as e:
        flash(request, "Failed to send confirmation email. Please try again.", "error")
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

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
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == int(user_id)))
        user = result.scalars().first()
        if not user:
            flash(request, "User not found", "error")
            return RedirectResponse(url="/auth/login", status_code=302)
        if user.is_verified:
            flash(request, "Email already confirmed", "info")
            return RedirectResponse(url="/auth/login", status_code=302)
        user.is_verified = True
        session.add(user)
        await session.commit()
    flash(request, "Email successfully confirmed!", "success")
    return RedirectResponse(url="/auth/login", status_code=302)

@router.get("/login", response_class=HTMLResponse)
async def get_login(request: Request, user: Optional[User] = Depends(get_current_user_if_exists)):
    if user:
        return RedirectResponse(url="/totp/list", status_code=status.HTTP_303_SEE_OTHER)
    flash_data = get_flashed_message(request)
    return templates.TemplateResponse("auth/login.html", {"request": request, "flash": flash_data, "user": user})

@router.post("/login")
async def post_login(request: Request, response: Response, email: str = Form(...), password: str = Form(...),
                     user: Optional[User] = Depends(get_current_user_if_exists)):
    if user:
        return RedirectResponse(url="/totp/list", status_code=status.HTTP_303_SEE_OTHER)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalars().first()
    if not user or not pwd_context.verify(password, user.hashed_password) or not user.is_verified:
        flash(request, "Invalid credentials or unverified email.", "error")
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "email": email, "flash": get_flashed_message(request)},
            status_code=status.HTTP_303_SEE_OTHER
        )
    access, refresh_raw, csrf_refresh, sid = await create_session_and_tokens(request, user)
    redirect_response = RedirectResponse(url="/totp/list", status_code=status.HTTP_302_FOUND)
    set_access_cookie(redirect_response, access)
    set_refresh_cookie(redirect_response, refresh_raw)
    set_csrf_refresh_cookie(redirect_response, csrf_refresh)
    return redirect_response

@router.post("/refresh")
async def refresh(request: Request):
    csrf_cookie = request.cookies.get(settings.CSRF_REFRESH_COOKIE_NAME)
    csrf_header = request.headers.get("X-CSRF-Token")
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        return JSONResponse({"detail": "CSRF failed"}, status_code=401)
    refreshed = await try_refresh_from_cookies(request)
    if not refreshed:
        return JSONResponse({"detail": "Invalid refresh"}, status_code=401)
    resp = JSONResponse({"ok": True})
    set_access_cookie(resp, refreshed["access"])
    set_refresh_cookie(resp, refreshed["refresh"])
    set_csrf_refresh_cookie(resp, refreshed["csrf"])
    return resp

@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_request(request: Request, user: Optional[User] = Depends(get_current_user_if_exists)):
    if user:
        return RedirectResponse(url="/totp/list", status_code=status.HTTP_303_SEE_OTHER)
    flash_data = get_flashed_message(request)
    return templates.TemplateResponse("auth/reset_password_request.html", {"request": request, "flash": flash_data, "user": user})

@router.post("/reset-password")
async def send_reset_email(request: Request, email: str = Form(...),
                           user: Optional[User] = Depends(get_current_user_if_exists)):
    if user:
        return RedirectResponse(url="/totp/list", status_code=status.HTTP_303_SEE_OTHER)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        if user:
            now = now_utc()
            if user.password_reset_requested_at and now - user.password_reset_requested_at < timedelta(minutes=1):
                flash(request, "You have recently requested a password reset. Please wait a minute before trying again.", "error")
                return RedirectResponse(url="/auth/reset-password", status_code=status.HTTP_303_SEE_OTHER)
            import uuid
            reset_token_id = str(uuid.uuid4())
            user.password_reset_token_id = reset_token_id
            user.password_reset_requested_at = now
            session.add(user)
            await session.commit()
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
            except Exception as e:
                flash(request, "Failed to send reset email. Please try again.", "error")
        else:
            flash(request, "If email exists, reset link sent. Check your inbox.", "success")
    return RedirectResponse(url="/auth/reset-password", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/reset-password/confirm", response_class=HTMLResponse)
async def reset_password_form(request: Request, token: str,
                              user: Optional[User] = Depends(get_current_user_if_exists)):
    if user:
        return RedirectResponse(url="/totp/list", status_code=status.HTTP_303_SEE_OTHER)
    flash_data = get_flashed_message(request)
    return templates.TemplateResponse("auth/reset_password.html", {"request": request, "token": token, "flash": flash_data, "user": user})

@router.post("/reset-password/confirm")
async def reset_password(request: Request, token: str = Form(...), password: str = Form(...),
                         confirm_password: str = Form(...),
                         user: Optional[User] = Depends(get_current_user_if_exists)):
    if user:
        return RedirectResponse(url="/totp/list", status_code=status.HTTP_303_SEE_OTHER)
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
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == int(user_id)))
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
        session.add(user)
        await session.commit()
    async with async_session() as session:
        await session.execute(update(AuthSession).where(AuthSession.user_id == int(user_id)).values(revoked_at=now_utc()))
        await session.commit()
    flash(request, "Password reset successfully. You can now log in.", "success")
    return RedirectResponse(url="/auth/login", status_code=302)

@router.get("/logout")
async def logout(request: Request, user: User = Depends(get_authenticated_user)):
    resp = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    sid = None
    if token:
        try:
            token_value = token.split(" ")[1] if " " in token else token
            payload = jwt.decode(token_value, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            sid = payload.get("sid")
        except JWTError:
            pass
    if not sid:
        refresh_raw = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
        if refresh_raw:
            refresh_hash = hash_refresh_token(refresh_raw)
            async with async_session() as session_db:
                result = await session_db.execute(select(AuthSession).where(AuthSession.refresh_token_hash == refresh_hash))
                db_sess = result.scalars().first()
                if db_sess:
                    sid = db_sess.id
    if sid:
        async with async_session() as session_db:
            result = await session_db.execute(select(AuthSession).where(AuthSession.id == sid, AuthSession.user_id == user.id))
            db_sess = result.scalars().first()
            if db_sess:
                db_sess.revoked_at = now_utc()
                session_db.add(db_sess)
                await session_db.commit()
    clear_auth_cookies(resp)
    return resp
