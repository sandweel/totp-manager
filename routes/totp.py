from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from config import templates
from services.flash import flash, get_flashed_message
from services.totp_service import TotpService
from routes.auth import get_authenticated_user
from services.validator import validate_totp
import re

router = APIRouter(prefix="/totp", tags=["totp"])

@router.get("/create", response_class=HTMLResponse)
async def get_create(request: Request, user=Depends(get_authenticated_user)):
    flash_data = get_flashed_message(request)
    return templates.TemplateResponse(
        "totp/create.html",
        {"request": request, "user": user, "flash": flash_data}
    )

@router.post("/create", response_class=HTMLResponse)
async def post_create(request: Request, name: str = Form(...), secret: str = Form(...), user=Depends(get_authenticated_user)):
    error_msg = validate_totp(name, secret)
    if error_msg:
        flash(request, error_msg, "error")
        flash_data = get_flashed_message(request)
        return templates.TemplateResponse(
            "totp/create.html",
            {"request": request, "user": user, "name": name, "flash": flash_data},
            status_code=status.HTTP_303_SEE_OTHER
        )

    await TotpService.create(name, secret, user)
    flash(request, "TOTP successfully created!", "success")
    return RedirectResponse(router.url_path_for("get_list"), status_code=status.HTTP_303_SEE_OTHER)

@router.get("/list", response_class=HTMLResponse)
async def get_list(request: Request, user=Depends(get_authenticated_user)):
    totps = await TotpService.list_all(user)
    flash_data = get_flashed_message(request)
    return templates.TemplateResponse("totp/list.html", {"request": request, "totps": totps, "user": user, "flash": flash_data})

@router.post("/{item_id}/delete", response_class=RedirectResponse)
async def delete_item(request: Request, item_id: int, user=Depends(get_authenticated_user)):
    deleted = await TotpService.delete(item_id, user)
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    flash(request, "TOTP deleted successfully.", "success")
    return RedirectResponse(router.url_path_for("get_list"), status_code=status.HTTP_303_SEE_OTHER)
