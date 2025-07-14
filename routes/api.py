from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from services.totp_service import TotpService
from routes.auth import get_current_user  # или из вашего файла deps.py

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/totp")
async def api_totp_list(current_user=Depends(get_current_user)):
    totps = await TotpService.list_all(current_user)
    return JSONResponse(content=[
        {"id": t["id"], "name": t["name"], "code": t["code"]}
        for t in totps
    ])
