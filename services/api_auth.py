from fastapi import HTTPException, status, Header
from typing import Optional
from models import User
from services.api_key_service import ApiKeyService


async def get_user_from_api_key(authorization: Optional[str] = Header(None)) -> User:
    """
    Dependency for API key authentication (Bearer token)
    Usage: user: User = Depends(get_user_from_api_key)
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header"
        )
    
    # Check Bearer token format
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Use: Bearer <api_key>"
        )
    
    api_key = parts[1]
    user = await ApiKeyService.validate_api_key(api_key)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return user

