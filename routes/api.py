from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from slowapi import Limiter
from slowapi.util import get_remote_address
from services.totp_service import TotpService
from services.auth import get_authenticated_user
from services.api_auth import get_user_from_api_key
from services.api_key_service import ApiKeyService
from services.import_export import build_qr_png
from models import User
import io

router = APIRouter(prefix="/api", tags=["api"])

# Rate limiter instance (will be set from main.py)
limiter = Limiter(key_func=get_remote_address)

# Pydantic models for API
class TOTPCreateRequest(BaseModel):
    account: str
    issuer: str
    secret: str

class TOTPUpdateRequest(BaseModel):
    account: str

class TOTPShareRequest(BaseModel):
    totp_ids: List[int]
    email: str

class TOTPDeleteRequest(BaseModel):
    ids: List[int]

class TOTPExportRequest(BaseModel):
    ids: List[int]

class TOTPImportRequest(BaseModel):
    uri: str

class ApiKeyCreateRequest(BaseModel):
    name: Optional[str] = None

# API endpoints for TOTP operations using API key
@router.get("/v1/totp/list")
@limiter.limit("30/minute")
async def api_list_totp(request: Request, user: User = Depends(get_user_from_api_key)):
    """Get list of all user's TOTP items"""
    totps = await TotpService.list_all(user)
    return JSONResponse(content=totps)

@router.get("/v1/totp/shared")
@limiter.limit("30/minute")
async def api_list_shared_totp(request: Request, user: User = Depends(get_user_from_api_key)):
    """Get list of TOTP items shared with user"""
    totps = await TotpService.list_shared_with_me(user)
    return JSONResponse(content=totps)

@router.post("/v1/totp/create")
@limiter.limit("10/minute")
async def api_create_totp(request: Request, body: TOTPCreateRequest, user: User = Depends(get_user_from_api_key)):
    """Create new TOTP item"""
    # Validation will be done in TotpService
    await TotpService.create(body.account, body.issuer, body.secret, user)
    return JSONResponse(content={"message": "TOTP created successfully"})

@router.post("/v1/totp/delete")
@limiter.limit("10/minute")
async def api_delete_totp(request: Request, body: TOTPDeleteRequest, user: User = Depends(get_user_from_api_key)):
    """Delete TOTP item(s) - accepts array of IDs (can be single or multiple)"""
    if not body.ids:
        raise HTTPException(status_code=400, detail="No IDs provided")

    deleted_count = 0
    for item_id in body.ids:
        if await TotpService.delete(item_id, user):
            deleted_count += 1

    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="No TOTP items found or deleted")

    if len(body.ids) == 1:
        return JSONResponse(content={"message": "TOTP deleted successfully", "deleted_count": deleted_count})
    else:
        return JSONResponse(content={"message": f"Deleted {deleted_count} item(s).", "deleted_count": deleted_count})

@router.put("/v1/totp/{totp_id}")
@limiter.limit("10/minute")
async def api_update_totp(request: Request, totp_id: int, body: TOTPUpdateRequest, user: User = Depends(get_user_from_api_key)):
    """Update TOTP item (account field only)"""
    success, message = await TotpService.update(totp_id, body.account, user)
    if not success:
        raise HTTPException(status_code=404, detail=message)
    return JSONResponse(content={"message": message})

@router.post("/v1/totp/share")
@limiter.limit("10/minute")
async def api_share_totp(request: Request, body: TOTPShareRequest, user: User = Depends(get_user_from_api_key)):
    """Share TOTP items with another user"""
    shared_count, message = await TotpService.share_totp(body.totp_ids, body.email, user)
    if shared_count == 0:
        raise HTTPException(status_code=400, detail=message)
    return JSONResponse(content={"message": message, "shared_count": shared_count})

@router.delete("/v1/totp/{totp_id}/share/{email}")
@limiter.limit("10/minute")
async def api_unshare_totp(request: Request, totp_id: int, email: str, user: User = Depends(get_user_from_api_key)):
    """Revoke TOTP item sharing"""
    success, message = await TotpService.unshare_totp(totp_id, email, user)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return JSONResponse(content={"message": message})

@router.get("/v1/totp/{totp_id}/shared-users")
@limiter.limit("30/minute")
async def api_get_shared_users(request: Request, totp_id: int, user: User = Depends(get_user_from_api_key)):
    """Get list of users with whom TOTP is shared"""
    emails, error = await TotpService.get_shared_users(totp_id, user)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return JSONResponse(content={"emails": emails})

@router.post("/v1/totp/export")
@limiter.limit("10/minute")
async def api_export_totp_qr(request: Request, body: TOTPExportRequest, user: User = Depends(get_user_from_api_key)):
    """Export TOTP items as QR code PNG"""
    if not body.ids:
        raise HTTPException(status_code=400, detail="No IDs provided")

    raw_items = await TotpService.export_raw(user, body.ids)
    if not raw_items:
        raise HTTPException(status_code=404, detail="No TOTP items found")

    png_bytes = build_qr_png(raw_items)
    return StreamingResponse(
        io.BytesIO(png_bytes),
        media_type="image/png",
        headers={"Content-Disposition": 'inline; filename="totp_export.png"'}
    )

@router.post("/v1/totp/export-uri")
@limiter.limit("10/minute")
async def api_export_totp_uri(request: Request, body: TOTPExportRequest, user: User = Depends(get_user_from_api_key)):
    """Export TOTP items as Google Authenticator migration URI"""
    if not body.ids:
        raise HTTPException(status_code=400, detail="No IDs provided")

    raw_items = await TotpService.export_raw(user, body.ids)
    if not raw_items:
        raise HTTPException(status_code=404, detail="No TOTP items found")

    from services.import_export import build_migration_uri
    uri = build_migration_uri(raw_items)
    return JSONResponse(content={"uri": uri})

@router.post("/v1/totp/import")
@limiter.limit("10/minute")
async def api_import_totp(request: Request, body: TOTPImportRequest, user: User = Depends(get_user_from_api_key)):
    """Import TOTP items from Google Authenticator migration URI"""
    from services.import_export_service import ImportExportService
    count, error = await ImportExportService.import_totp_uris(body.uri, user)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return JSONResponse(content={"message": f"Imported {count} item(s).", "count": count})

# API endpoints for API key management (require web authentication)
@router.post("/v1/api-keys", dependencies=[Depends(get_authenticated_user)])
async def api_create_api_key(request: ApiKeyCreateRequest, user: User = Depends(get_authenticated_user)):
    """Create new API key (web interface only)"""
    plain_key, api_key_obj = await ApiKeyService.create_api_key(user, request.name)
    return JSONResponse(content={
        "api_key": plain_key,
        "id": api_key_obj.id,
        "name": api_key_obj.name,
        "created_at": api_key_obj.created_at.isoformat()
    })

@router.get("/v1/api-keys", dependencies=[Depends(get_authenticated_user)])
async def api_list_api_keys(user: User = Depends(get_authenticated_user)):
    """Get list of all user's API keys"""
    keys = await ApiKeyService.list_user_api_keys(user)
    return JSONResponse(content=keys)

@router.delete("/v1/api-keys/{key_id}", dependencies=[Depends(get_authenticated_user)])
async def api_revoke_api_key(key_id: int, user: User = Depends(get_authenticated_user)):
    """Revoke API key"""
    success = await ApiKeyService.revoke_api_key(key_id, user)
    if not success:
        raise HTTPException(status_code=404, detail="API key not found")
    return JSONResponse(content={"message": "API key revoked successfully"})

@router.post("/v1/api-keys/revoke-all", dependencies=[Depends(get_authenticated_user)])
async def api_revoke_all_api_keys(user: User = Depends(get_authenticated_user)):
    """Revoke all API keys"""
    count = await ApiKeyService.revoke_all_api_keys(user)
    return JSONResponse(content={"message": f"Revoked {count} API key(s)"})
