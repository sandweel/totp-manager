from fastapi import APIRouter, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.future import select
import pyotp

from config import async_session, fernet, templates, TOTPItem


router = APIRouter(prefix="/totp", tags=["totp"])

@router.get("/create", response_class=HTMLResponse)
async def get_create(request: Request):
    return templates.TemplateResponse("totp/create.html", {"request": request})

@router.post("/create", response_class=HTMLResponse)
async def post_create(
    request: Request,
    name: str = Form(...),
    secret: str = Form(...)
):
    if len(name) > 32:
        return templates.TemplateResponse(
            "totp/create.html",
            {"request": request, "error": f"Name is too long (max 32 characters).", "name": name, "secret": secret},
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

    token = fernet.encrypt(secret.encode()).decode()
    async with async_session() as session:
        item = TOTPItem(name=name, encrypted_secret=token)
        session.add(item)
        await session.commit()

    return RedirectResponse(router.url_path_for("get_list"), status_code=status.HTTP_303_SEE_OTHER)

@router.get("/list", response_class=HTMLResponse)
async def get_list(request: Request):
    async with async_session() as session:
        result = await session.execute(select(TOTPItem))
        items = result.scalars().all()

    totps = []
    for i in items:
        try:
            secret = fernet.decrypt(i.encrypted_secret.encode()).decode()
            totp = pyotp.TOTP(secret)
            code = totp.now()
        except Exception:
            code = "Error"
        totps.append({"id": i.id, "name": i.name, "code": code})

    return templates.TemplateResponse("totp/list.html", {"request": request, "totps": totps})

@router.post("/{item_id}/delete", response_class=RedirectResponse)
async def delete_item(item_id: int):
    async with async_session() as session:
        item = await session.get(TOTPItem, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        await session.delete(item)
        await session.commit()

    return RedirectResponse(router.url_path_for("get_list"), status_code=status.HTTP_303_SEE_OTHER)
