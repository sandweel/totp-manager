from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy.future import select
import pyotp

from config import async_session, fernet, TOTPItem

router = APIRouter(prefix="/api", tags=["api"])

@router.get("/totp")
async def api_totp_list():
    async with async_session() as session:
        result = await session.execute(select(TOTPItem))
        items = result.scalars().all()

    totp_data = []
    for i in items:
        try:
            secret = fernet.decrypt(i.encrypted_secret.encode()).decode()
            totp = pyotp.TOTP(secret)
            current_code = totp.now()
        except Exception:
            current_code = "Error"
        totp_data.append({"id": i.id, "code": current_code})

    return JSONResponse(content=totp_data)
