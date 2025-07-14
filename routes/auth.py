from fastapi import APIRouter, Request, Form, Depends, HTTPException, status, Response
from fastapi.responses import RedirectResponse, HTMLResponse
from cryptography.fernet import Fernet
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings, async_session, templates, master_fernet, http_client
from models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter(prefix="/auth", tags=["auth"])

def create_access_token(data, expires_delta=None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/auth/login"})
    try:
        payload = jwt.decode(token.split()[1], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/auth/login"})
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == int(user_id)))
        user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/auth/login"})
    return user

@router.get("/register", response_class=HTMLResponse)
async def get_register(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request})

@router.post("/register", response_class=HTMLResponse)
async def post_register(request: Request, email: str = Form(...), password: str = Form(...)):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        if result.scalars().first():
            return templates.TemplateResponse("auth/register.html", {"request": request, "error": "Email already registered"})
        hashed_password = pwd_context.hash(password)
        user_dek = Fernet.generate_key()
        encrypted_dek = master_fernet.encrypt(user_dek).decode()
        user = User(email=email, hashed_password=hashed_password, encrypted_dek=encrypted_dek)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    token = create_access_token({"sub": str(user.id)}, expires_delta=timedelta(hours=24))
    link = f"{settings.FRONTEND_URL}/auth/confirm?token={token}"
    await http_client.post(
        f"https://api.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages",
        auth=("api", settings.MAILGUN_API_KEY),
        data={"from": f"no-reply@{settings.MAILGUN_DOMAIN}", "to": [email], "subject": "Confirm your account", "text": f"Click to confirm: {link}"}
    )
    return templates.TemplateResponse("auth/register.html", {"request": request, "msg": "Confirmation email sent"})

@router.get("/confirm")
async def confirm_email(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid token")
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == int(user_id)))
        user = result.scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.is_verified = True
        session.add(user)
        await session.commit()
    return RedirectResponse(url="/auth/login", status_code=302)

@router.get("/login", response_class=HTMLResponse)
async def get_login(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})

@router.post("/login")
async def post_login(response: Response, email: str = Form(...), password: str = Form(...)):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalars().first()
    if not user or not pwd_context.verify(password, user.hashed_password) or not user.is_verified:
        raise HTTPException(status_code=400, detail="Invalid credentials or email not verified")
    access_token = create_access_token({"sub": str(user.id)})
    response = RedirectResponse(url="/totp/list", status_code=302)
    response.set_cookie("access_token", f"Bearer {access_token}", httponly=True)
    return response

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie("access_token")
    return response

@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_request(request: Request):
    return templates.TemplateResponse("auth/reset_password_request.html", {"request": request})

@router.post("/reset-password")
async def send_reset_email(request: Request, email: str = Form(...)):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalars().first()
    if user:
        token = create_access_token({"sub": str(user.id)}, expires_delta=timedelta(hours=1))
        link = f"{settings.FRONTEND_URL}/auth/reset-password/confirm?token={token}"
        await http_client.post(
            f"https://api.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages",
            auth=("api", settings.MAILGUN_API_KEY),
            data={"from": f"no-reply@{settings.MAILGUN_DOMAIN}", "to": [email], "subject": "Reset your password", "text": f"Click to reset your password: {link}"}
        )
    return templates.TemplateResponse("auth/reset_password_request.html", {"request": request, "msg": "If email exists, reset link sent"})

@router.get("/reset-password/confirm", response_class=HTMLResponse)
async def reset_password_form(request: Request, token: str):
    return templates.TemplateResponse("auth/reset_password.html", {"request": request, "token": token})

@router.post("/reset-password/confirm")
async def reset_password(request: Request, token: str = Form(...), password: str = Form(...)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid token")
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == int(user_id)))
        user = result.scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.hashed_password = pwd_context.hash(password)
        session.add(user)
        await session.commit()
    return RedirectResponse(url="/auth/login", status_code=302)
