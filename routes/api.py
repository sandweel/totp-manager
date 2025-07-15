from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from services.totp_service import TotpService
from routes.auth import get_authenticated_user

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/totp")
async def api_totp_list(user=Depends(get_authenticated_user)):
    totps = await TotpService.list_all(user)
    return JSONResponse(content=[
        {"id": t["id"], "name": t["name"], "code": t["code"]}
        for t in totps
    ])