from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import io
from starlette.responses import StreamingResponse
from config import templates
from services.flash import flash, get_flashed_message
from services.totp_service import TotpService
from services.auth import get_authenticated_user
from services.validator import validate_totp
from services.import_export import build_qr_png
from services.import_export_service import ImportExportService

router = APIRouter(prefix="/totp", tags=["totp"])


@router.get("/create", response_class=HTMLResponse)
async def get_create(request: Request, user=Depends(get_authenticated_user)):
    flash_data = get_flashed_message(request)
    return templates.TemplateResponse(
        "totp/create.html",
        {"request": request, "user": user, "flash": flash_data}
    )


@router.post("/create", response_class=HTMLResponse)
async def post_create(request: Request, account: str = Form(...), issuer: str = Form(...), secret: str = Form(...),
                      user=Depends(get_authenticated_user)):
    error_msg = validate_totp(account, issuer, secret)
    if error_msg:
        flash(request, error_msg, "error")
        flash_data = get_flashed_message(request)
        return templates.TemplateResponse(
            "totp/create.html",
            {"request": request, "user": user, "account": account, "issuer": issuer, "flash": flash_data},
            status_code=status.HTTP_303_SEE_OTHER
        )

    await TotpService.create(account, issuer, secret, user)
    flash(request, "TOTP successfully created!", "success")
    return RedirectResponse(router.url_path_for("get_list"), status_code=status.HTTP_303_SEE_OTHER)


@router.get("/list", response_class=HTMLResponse)
async def get_list(request: Request, user=Depends(get_authenticated_user)):
    totps = await TotpService.list_all(user)
    shared_totps = await TotpService.list_shared_with_me(user)
    flash_data = get_flashed_message(request)
    return templates.TemplateResponse(
        "totp/list.html",
        {"request": request, "totps": totps, "shared_totps": shared_totps, "user": user, "flash": flash_data}
    )


@router.post("/delete", response_class=RedirectResponse)
async def delete_items(request: Request, ids: str = Form(...), user=Depends(get_authenticated_user)):
    try:
        id_list = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item ids")

    deleted_count = 0
    for item_id in id_list:
        if await TotpService.delete(item_id, user):
            deleted_count += 1

    if len(id_list) == 1 and deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")

    if deleted_count:
        flash(request, f"Deleted {deleted_count} item(s).", "success")
    else:
        flash(request, "No items were deleted.", "error")

    return RedirectResponse(router.url_path_for("get_list"), status_code=status.HTTP_303_SEE_OTHER)


@router.get("/list-all")
async def totp_list(user=Depends(get_authenticated_user)):
    totps = await TotpService.list_all(user)
    return JSONResponse(content=[
        {"id": t["id"], "account": t["account"], "issuer": t["issuer"], "code": t["code"]}
        for t in totps
    ])


@router.get("/list-shared-with-me")
async def shared_totp_list(user=Depends(get_authenticated_user)):
    totps = await TotpService.list_shared_with_me(user)
    return JSONResponse(content=[
        {"id": t["id"], "account": t["account"], "owner_email": t["owner_email"], "issuer": t["issuer"], "code": t["code"]}
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
    return StreamingResponse(io.BytesIO(png_bytes), media_type="image/png",
                             headers={"Content-Disposition": 'inline; filename="totp_export.png"'})


@router.post("/import", response_class=RedirectResponse)
async def import_totps(request: Request, uri: str = Form(...), user=Depends(get_authenticated_user)):
    created_count, error_msg = await ImportExportService.import_totp_uris(uri, user)
    
    if error_msg:
        flash(request, error_msg, "error")
    else:
        flash(request, f"Imported {created_count} item(s).", "success")

    return RedirectResponse(router.url_path_for("get_list"), status_code=303)


@router.post("/share", response_class=RedirectResponse)
async def share_totp(request: Request, totp_ids: str = Form(...), email: str = Form(...),
                     user=Depends(get_authenticated_user)):
    try:
        id_list = [int(x) for x in totp_ids.split(",") if x.strip()]
    except ValueError:
        flash(request, "Invalid TOTP IDs.", "error")
        return RedirectResponse(router.url_path_for("get_list"), status_code=status.HTTP_303_SEE_OTHER)

    shared_count, message = await TotpService.share_totp(id_list, email.strip(), user)
    flash(request, message, "success" if shared_count > 0 else "error")
    return RedirectResponse(router.url_path_for("get_list"), status_code=status.HTTP_303_SEE_OTHER)


@router.get("/shared-users/{totp_id}", response_class=JSONResponse)
async def get_shared_users(totp_id: int, user=Depends(get_authenticated_user)):
    emails, error = await TotpService.get_shared_users(totp_id, user)
    if error:
        return JSONResponse({"message": error, "category": "error"}, status_code=400)
    return JSONResponse({"emails": emails})


@router.post("/unshare", response_class=JSONResponse)
async def unshare_totp(totp_id: int = Form(...), email: str = Form(...), user=Depends(get_authenticated_user)):
    success, message = await TotpService.unshare_totp(totp_id, email.strip(), user)
    if not success:
        return JSONResponse({"message": message, "category": "error"}, status_code=400)
    return JSONResponse({"message": message, "category": "success"})

@router.post("/update", response_class=JSONResponse)
async def update_totp(totp_id: int = Form(...), account: str = Form(...), user=Depends(get_authenticated_user)):
    account = account.strip()
    if not account:
        return JSONResponse( {"flash": {"message": "Account is required.", "category": "error"}}, status_code=400)
    success, message = await TotpService.update(totp_id, account, user)
    if not success:
        return JSONResponse({"flash": {"message": message, "category": "error"}}, status_code=400)
    return JSONResponse({"flash": {"message": message, "category": "success"}}, status_code=200)