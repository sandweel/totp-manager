from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy import select, update
from typing import Optional, List
from datetime import datetime
from config import async_session, templates
from models import Session as SessionDB, User
from routes.auth import get_authenticated_user, clear_auth_cookies

router = APIRouter(prefix="/auth/sessions", tags=["sessions"])

def now_utc():
    return datetime.utcnow()

@router.get("", response_class=HTMLResponse)
async def list_sessions(request: Request, user: User = Depends(get_authenticated_user)):
    async with async_session() as db:
        result = await db.execute(
            select(SessionDB).where(SessionDB.user_id == user.id).order_by(SessionDB.created_at.desc())
        )
        sessions: List[SessionDB] = result.scalars().all()
    current_sid = getattr(request.state, "current_sid", None)
    return templates.TemplateResponse(
        "sessions/list.html",
        {
            "request": request,
            "user": user,
            "sessions": sessions,
            "current_sid": current_sid,
            "now": now_utc(),
        },
    )

@router.post("/{session_id}/revoke")
async def revoke_session(request: Request, session_id: str, user: User = Depends(get_authenticated_user)):
    async with async_session() as db:
        result = await db.execute(
            select(SessionDB).where(SessionDB.user_id == user.id, SessionDB.session_id == session_id)
        )
        s = result.scalars().first()
        if not s:
            raise HTTPException(status_code=404, detail="Not found")
        if s.revoked_at is None:
            await db.execute(
                update(SessionDB).where(SessionDB.id == s.id).values(revoked_at=now_utc())
            )
            await db.commit()
    current_sid = getattr(request.state, "current_sid", None)
    if current_sid and current_sid == session_id:
        response = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
        clear_auth_cookies(response)
        return response
    return RedirectResponse(url="/auth/sessions", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/revoke-all")
async def revoke_all_sessions(request: Request, user: User = Depends(get_authenticated_user)):
    async with async_session() as db:
        await db.execute(
            update(SessionDB).where(SessionDB.user_id == user.id, SessionDB.revoked_at.is_(None)).values(revoked_at=now_utc())
        )
        await db.commit()
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    clear_auth_cookies(response)
    return response
