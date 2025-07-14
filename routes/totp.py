# routes/totp.py
from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from config import templates
from services.totp_service import TotpService
from routes.auth import get_current_user

router = APIRouter(prefix="/totp", tags=["totp"])

@router.get("/create", response_class=HTMLResponse)
async def get_create(request: Request, current_user=Depends(get_current_user)):
    return templates.TemplateResponse("totp/create.html", {"request": request})

@router.post("/create", response_class=HTMLResponse)
async def post_create(
    request: Request,
    name: str = Form(...),
    secret: str = Form(...),
    current_user=Depends(get_current_user)
):
    if len(name) > 32:
        return templates.TemplateResponse(
            "totp/create.html",
            {"request": request, "error": "Name is too long (max 32 characters).", "name": name, "secret": secret},
        )
    if not name.strip():
        return templates.TemplateResponse(
            "totp/create.html",
            {"request": request, "error": "Name is required.", "name": name, "secret": secret},
        )
    if not secret.strip():
        return templates.TemplateResponse(
            "totp/create.html",
            {"request": request, "error": "Secret is required.", "name": name, "secret": secret},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    await TotpService.create(name, secret, current_user)
    return RedirectResponse(router.url_path_for("get_list"), status_code=status.HTTP_303_SEE_OTHER)

@router.get("/list", response_class=HTMLResponse)
async def get_list(request: Request, current_user=Depends(get_current_user)):
    totps = await TotpService.list_all(current_user)
    return templates.TemplateResponse("totp/list.html", {"request": request, "totps": totps})

@router.post("/{item_id}/delete", response_class=RedirectResponse)
async def delete_item(item_id: int, current_user=Depends(get_current_user)):
    deleted = await TotpService.delete(item_id, current_user)
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    return RedirectResponse(router.url_path_for("get_list"), status_code=status.HTTP_303_SEE_OTHER)
