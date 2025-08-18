from fastapi import APIRouter, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, update
from typing import Optional
from config import templates
from models import AuthSession, User
from routes.auth import get_authenticated_user, now_utc, clear_auth_cookies
from services.flash import flash, get_flashed_message
from config import async_session, settings

router = APIRouter(prefix="/auth", tags=["sessions"])

def ensure_csrf(request: Request):
    if "_csrf" not in request.session:
        import secrets
        request.session["_csrf"] = secrets.token_urlsafe(24)
    return request.session["_csrf"]

def validate_csrf(request: Request, token: str):
    stored = request.session.get("_csrf")
    return stored and token and stored == token

@router.get("/sessions", response_class=HTMLResponse)
async def sessions_page(request: Request, user: User = Depends(get_authenticated_user)):
    async with async_session() as session:
        result = await session.execute(
            select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).order_by(AuthSession.last_used_at.desc())
        )
        rows = result.scalars().all()
    csrf = ensure_csrf(request)
    flash_data = get_flashed_message(request)
    current_sid = None
    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if token:
        from jose import jwt
        try:
            token_value = token.split(" ")[1] if " " in token else token
            payload = jwt.decode(token_value, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            current_sid = payload.get("sid")
        except Exception:
            current_sid = None
    return templates.TemplateResponse("auth/sessions.html", {"request": request, "user": user, "sessions": rows, "csrf_token": csrf, "current_sid": current_sid, "flash": flash_data})

@router.post("/sessions/revoke-all")
async def revoke_all_sessions(request: Request, csrf_token: str = Form(...), user: User = Depends(get_authenticated_user)):
    if not validate_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    async with async_session() as session_db:
        await session_db.execute(update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).values(revoked_at=now_utc()))
        await session_db.commit()
    resp = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    clear_auth_cookies(resp)
    return resp

@router.post("/sessions/{session_id}/revoke")
async def revoke_session(session_id: str, request: Request, csrf_token: str = Form(...), user: User = Depends(get_authenticated_user)):
    if not validate_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    async with async_session() as session_db:
        result = await session_db.execute(select(AuthSession).where(AuthSession.id == session_id, AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)))
        row = result.scalars().first()
        if not row:
            flash(request, "Session not found or already revoked", "error")
            return RedirectResponse(url="/auth/sessions", status_code=status.HTTP_303_SEE_OTHER)
        row.revoked_at = now_utc()
        session_db.add(row)
        await session_db.commit()
    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    current_sid = None
    if token:
        from jose import jwt
        try:
            token_value = token.split(" ")[1] if " " in token else token
            payload = jwt.decode(token_value, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            current_sid = payload.get("sid")
        except Exception:
            current_sid = None
    if current_sid == session_id:
        resp = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
        from routes.auth import clear_auth_cookies
        clear_auth_cookies(resp)
        return resp
    flash(request, "Session revoked", "success")
    return RedirectResponse(url="/auth/sessions", status_code=status.HTTP_303_SEE_OTHER)
