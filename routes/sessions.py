from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse
from config import async_session
from models import Session as SessionDB, User
from services.auth import get_authenticated_user, clear_auth_cookies
from services.session_service import SessionService

router = APIRouter(prefix="/auth/sessions", tags=["sessions"])

@router.post("/{session_id}/revoke")
async def revoke_session(request: Request, session_id: str, user: User = Depends(get_authenticated_user)):
    success, error_msg = await SessionService.revoke_session(session_id, user)
    
    if not success:
        raise HTTPException(status_code=404, detail=error_msg or "Session not found")
    
    current_sid = getattr(request.state, "current_sid", None)
    if current_sid and current_sid == session_id:
        response = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
        clear_auth_cookies(response)
        return response
    return RedirectResponse(url="/auth/profile?tab=sessions", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/revoke-all")
async def revoke_all_sessions(request: Request, user: User = Depends(get_authenticated_user)):
    await SessionService.revoke_all_sessions(user)
    response = RedirectResponse(url="/auth/profile?tab=sessions", status_code=status.HTTP_302_FOUND)
    clear_auth_cookies(response)
    return response
