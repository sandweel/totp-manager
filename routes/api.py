from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from services.totp_service import TotpService
from routes.auth import get_authenticated_user

router = APIRouter(prefix="/api", tags=["api"])
