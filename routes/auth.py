from fastapi import APIRouter, Request, Form, Depends, HTTPException, status, Response
from fastapi.responses import RedirectResponse, HTMLResponse
from cryptography.fernet import Fernet
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from sqlalchemy import select
from typing import Optional
from config import settings, async_session, templates, master_fernet, http_client
from models import User
from services.flash import flash, get_flashed_message
from services.validator import validate_password
import uuid

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter(prefix="/auth", tags=["auth"])

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_authenticated_user(request: Request) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/auth/login"})
    try:
        token_value = token.split(" ")[1] if " " in token else token
        payload = jwt.decode(token_value, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/auth/login"})

    if user_id is None:
        raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/auth/login"})

    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == int(user_id)))
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
        print(f"Error sending email: {e}")
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

    access_token = create_access_token({"sub": str(user.id)})
    redirect_response = RedirectResponse(url="/totp/list", status_code=status.HTTP_302_FOUND)
    redirect_response.set_cookie("access_token", f"Bearer {access_token}", httponly=True)
    return redirect_response


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
            now = datetime.utcnow()
            if user.password_reset_requested_at and now - user.password_reset_requested_at < timedelta(minutes=1):
                flash(request, "You have recently requested a password reset. Please wait a minute before trying again.", "error")
                return RedirectResponse(url="/auth/reset-password", status_code=status.HTTP_303_SEE_OTHER)

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
                print(f"Error sending reset email: {e}")
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

    flash(request, "Password reset successfully. You can now log in.", "success")
    return RedirectResponse(url="/auth/login", status_code=302)

@router.get("/logout")
async def logout(user: User = Depends(get_authenticated_user)):
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("access_token")
    return response
