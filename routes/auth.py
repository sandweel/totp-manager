from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import RedirectResponse, HTMLResponse
from typing import Optional

from config import templates
from models import User, Session as SessionDB
from services.flash import flash, get_flashed_message
from services.auth import (
    set_auth_cookies,
    clear_auth_cookies,
    get_current_user_if_exists,
    get_authenticated_user,
    now_utc,
)
from services.auth_service import AuthService
from services.session_service import SessionService

router = APIRouter(prefix="/auth", tags=["auth"])

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
    
    # Use AuthService for registration
    success, user_email, error_msg = await AuthService.register_user(email, password, confirm_password)
    
    if not success:
        flash(request, error_msg, "error")
        flash_data = get_flashed_message(request)
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "flash": flash_data, "email": email},
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    flash(request, "Confirmation email sent. Please check your email", "success")
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/confirm")
async def confirm_email(request: Request, token: str):
    success, error_msg = await AuthService.confirm_email(token)
    
    if not success:
        flash(request, error_msg, "error")
    else:
        flash(request, "Email successfully confirmed!", "success")
    
    return RedirectResponse(url="/auth/login", status_code=302)

@router.get("/login", response_class=HTMLResponse)
async def get_login(request: Request, user: Optional[User] = Depends(get_current_user_if_exists)):
    if user:
        return RedirectResponse(url="/totp/list", status_code=status.HTTP_303_SEE_OTHER)
    flash_data = get_flashed_message(request)
    return templates.TemplateResponse("auth/login.html", {"request": request, "flash": flash_data, "user": user})

@router.post("/login")
async def post_login(request: Request, email: str = Form(...), password: str = Form(...),
                     user: Optional[User] = Depends(get_current_user_if_exists)):
    if user:
        return RedirectResponse(url="/totp/list", status_code=status.HTTP_303_SEE_OTHER)
    
    # Use AuthService for login
    success, access_token, refresh_token, error_msg = await AuthService.login_user(email, password, request)
    
    if not success:
        flash(request, error_msg, "error")
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "email": email, "flash": get_flashed_message(request)},
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    redirect_response = RedirectResponse(url="/totp/list", status_code=status.HTTP_302_FOUND)
    set_auth_cookies(redirect_response, access_token, refresh_token)
    return redirect_response

@router.get("/logout")
async def logout(request: Request):
    await AuthService.logout_user(request)
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    clear_auth_cookies(response)
    return response

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
    
    success, error_msg = await AuthService.request_password_reset(email)
    
    if not success:
        flash(request, error_msg, "error")
        return RedirectResponse(url="/auth/reset-password", status_code=status.HTTP_303_SEE_OTHER)
    
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
    
    success, error_msg = await AuthService.reset_password(token, password, confirm_password)
    
    if not success:
        flash(request, error_msg, "error")
        flash_data = get_flashed_message(request)
        return templates.TemplateResponse("auth/reset_password.html", {"request": request, "flash": flash_data, "token": token})
    
    flash(request, "Password reset successfully. You can now log in.", "success")
    return RedirectResponse(url="/auth/login", status_code=302)

@router.get("/profile", response_class=HTMLResponse)
async def get_profile(request: Request, user: User = Depends(get_authenticated_user)):
    flash_data = get_flashed_message(request)
    
    # Get user sessions with location info
    sessions_with_location = await SessionService.get_user_sessions(user)
    sessions = [item['session'] for item in sessions_with_location]
    
    current_sid = getattr(request.state, 'current_sid', None)
    
    return templates.TemplateResponse("auth/profile.html", {
        "request": request, 
        "flash": flash_data, 
        "user": user,
        "sessions": sessions,
        "sessions_with_location": sessions_with_location,
        "current_sid": current_sid,
        "now": now_utc()
    })

@router.post("/profile/change-password")
async def change_password(request: Request, 
                        current_password: str = Form(...),
                        new_password: str = Form(...),
                        confirm_password: str = Form(...),
                        user: User = Depends(get_authenticated_user)):
    
    success, error_msg = await AuthService.change_password(user, current_password, new_password, confirm_password)
    
    if not success:
        flash(request, error_msg, "error")
    else:
        flash(request, "Password changed successfully", "success")
    
    return RedirectResponse(url="/auth/profile", status_code=status.HTTP_303_SEE_OTHER)
