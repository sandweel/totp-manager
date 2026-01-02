from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from slowapi import Limiter
from slowapi.util import get_remote_address
from services.totp_service import TotpService
from services.auth import get_authenticated_user
from services.api_auth import get_user_from_api_key
from services.api_key_service import ApiKeyService
from models import User

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

@router.delete("/v1/totp/{totp_id}")
@limiter.limit("10/minute")
async def api_delete_totp(request: Request, totp_id: int, user: User = Depends(get_user_from_api_key)):
    """Delete TOTP item"""
    success = await TotpService.delete(totp_id, user)
    if not success:
        raise HTTPException(status_code=404, detail="TOTP item not found")
    return JSONResponse(content={"message": "TOTP deleted successfully"})

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

# API endpoints for API key management (require web authentication)
@router.post("/v1/api-keys", dependencies=[Depends(get_authenticated_user)])
async def api_create_api_key(request: ApiKeyCreateRequest, user: User = Depends(get_authenticated_user)):
    """Create new API key (web interface only)"""
    plain_key, api_key_obj = await ApiKeyService.create_api_key(user, request.name)
    return JSONResponse(content={
        "api_key": plain_key,  # Show only once!
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
    """Отозвать все API ключи пользователя"""
    count = await ApiKeyService.revoke_all_api_keys(user)
    return JSONResponse(content={"message": f"Revoked {count} API key(s)"})
