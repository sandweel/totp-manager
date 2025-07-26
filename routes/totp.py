
from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import io
from starlette.responses import StreamingResponse

from config import templates
from services.flash import flash, get_flashed_message
from services.totp_service import TotpService
from routes.auth import get_authenticated_user
from services.validator import validate_totp
from services.import_export import build_migration_uri, build_qr_png, decode_migration_uri

router = APIRouter(prefix="/totp", tags=["totp"])

@router.get("/create", response_class=HTMLResponse)
async def get_create(request: Request, user=Depends(get_authenticated_user)):
    flash_data = get_flashed_message(request)
    return templates.TemplateResponse(
        "totp/create.html",
        {"request": request, "user": user, "flash": flash_data}
    )

@router.post("/create", response_class=HTMLResponse)
async def post_create(request: Request, account: str = Form(...), issuer: str = Form(...), secret: str = Form(...), user=Depends(get_authenticated_user)):
    error_msg = validate_totp(account, issuer, secret)
    if error_msg:
        flash(request, error_msg, "error")
        flash_data = get_flashed_message(request)
        return templates.TemplateResponse(
            "totp/create.html",
            {"request": request, "user": user, "account": account, "issuer": issuer, "flash": flash_data}, status_code=status.HTTP_303_SEE_OTHER
        )

    await TotpService.create(account, issuer, secret, user)
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

@router.get("/list-all")
async def api_totp_list(user=Depends(get_authenticated_user)):
    totps = await TotpService.list_all(user)
    return JSONResponse(content=[
        {"id": t["id"], "account": t["account"], "issuer": t["issuer"], "code": t["code"]}
        for t in totps
    ])

@router.post("/export")
async def export_qr(request: Request, ids: str = Form(...), user=Depends(get_authenticated_user)):
    id_list = [int(x) for x in ids.split(",") if x]
    raw_items = await TotpService.export_raw(user, id_list)
    if not raw_items:
        flash(request, "No items selected to export.", "error")
        return RedirectResponse(router.url_path_for("get_list"), status_code=status.HTTP_303_SEE_OTHER)

    png_bytes = build_qr_png(raw_items)

    return StreamingResponse(io.BytesIO(png_bytes), media_type="image/png", headers={"Content-Disposition": 'inline; filename="totp_export.png"'})

@router.post("/import", response_class=RedirectResponse)
async def import_totps(request: Request, uri: str = Form(...), user=Depends(get_authenticated_user)):
    try:
        otp_uris = decode_migration_uri(uri.strip())
        created = 0
        for otp_uri in otp_uris:
            from urllib.parse import urlparse, parse_qs, unquote
            p = urlparse(otp_uri)
            if p.scheme != "otpauth" or p.hostname.lower() != "totp":
                raise ValueError("Unsupported URI: " + otp_uri)
            label = unquote(p.path[1:])
            issuer_field, account = label.split(":", 1)
            qs = parse_qs(p.query)
            secret = qs.get("secret", [None])[0]
            if not secret:
                raise ValueError("Secret not found in URI.")
            issuer_qs = qs.get("issuer", [issuer_field])[0]
            await TotpService.create(account, issuer_qs, secret, user)
            created += 1
        flash(request, f"Imported {created} item(s).", "success")
    except Exception as e:
        flash(request, str(e), "error")

    return RedirectResponse(router.url_path_for("get_list"), status_code=303)