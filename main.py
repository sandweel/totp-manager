import uvicorn
import logging
import uuid
import os
from typing import Optional
from fastapi import FastAPI, Request, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import FileResponse, JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import templates, settings
from routes.auth import router as auth_router, get_current_user_if_exists, set_auth_cookies
from routes.totp import router as totp_router
from routes.api import router as api_router
from routes.sessions import router as sessions_router
from models import User

logging.basicConfig(
    filename="logs/error.log",
    level=logging.ERROR,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y/%m/%d %H:%M:%S"
)

app = (FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None
    )
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins] if cors_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set limiter for API router (must be before including router)
from routes.api import limiter as api_limiter
api_limiter.state = app.state.limiter

app.include_router(auth_router)
app.include_router(totp_router)
app.include_router(api_router)
app.include_router(sessions_router)

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Add request ID for tracing"""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    if settings.COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

@app.middleware("http")
async def proxy_headers_middleware(request: Request, call_next):
    """Handle proxy headers (X-Forwarded-For, etc.)"""
    proto = request.headers.get("x-forwarded-proto")
    if proto:
        request.scope["scheme"] = proto

    xff = request.headers.get("x-forwarded-for")
    if xff:
        real_ip = xff.split(",")[0].strip()
        client = request.scope.get("client")
        if client:
            request.scope["client"] = (real_ip, client[1])

    return await call_next(request)

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    allowlisted = (
        request.url.path.startswith("/auth")
        or request.url.path.startswith("/static")
        or request.url.path.startswith("/api")  # API endpoints use API key auth
        or request.url.path in ["/favicon.ico", "/health"]
    )
    if allowlisted:
        response = await call_next(request)
    else:
        access_cookie = request.cookies.get("access_token")
        refresh_cookie = request.cookies.get("refresh_token")
        if not access_cookie and not refresh_cookie:
            return RedirectResponse(url="/auth/login")
        response = await call_next(request)
    tokens = getattr(request.state, "new_tokens", None)
    if tokens:
        set_auth_cookies(response, tokens[0], tokens[1])
    return response

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded"""
    if request.url.path.startswith("/api"):
        return JSONResponse(
            content={"detail": "Rate limit exceeded. Please try again later."},
            status_code=429,
            headers={"Retry-After": str(exc.retry_after) if hasattr(exc, 'retry_after') else "60"}
        )
    return JSONResponse(
        content={"detail": "Rate limit exceeded. Please try again later."},
        status_code=429
    )

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    # API requests should return JSON, not HTML
    if request.url.path.startswith("/api"):
        request_id = getattr(request.state, "request_id", None)
        content = {"detail": exc.detail}
        if request_id:
            content["request_id"] = request_id
        return JSONResponse(
            content=content,
            status_code=exc.status_code
        )
    
    user = await get_current_user_if_exists(request)
    if exc.status_code == 404:
        return templates.TemplateResponse(
            "errors/404.html", {"request": request, "user": user}, status_code=404
        )
    if exc.status_code in {301, 302, 303, 307, 308}:
        location = exc.headers.get("Location", "/")
        return RedirectResponse(url=location, status_code=exc.status_code)
    return templates.TemplateResponse(
        "errors/generic.html", {"request": request, "user": user, "status_code": exc.status_code},
        status_code=exc.status_code
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # API requests should return JSON, not HTML
    if request.url.path.startswith("/api"):
        return JSONResponse(
            content={"detail": exc.errors()},
            status_code=422
        )
    
    user = await get_current_user_if_exists(request)
    return templates.TemplateResponse(
        "errors/422.html",
        {"request": request, "errors": exc.errors(), "user": user},
        status_code=422
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.exception(f"Unhandled error for request: {request.url}")
    # API requests should return JSON, not HTML
    if request.url.path.startswith("/api"):
        return JSONResponse(
            content={"detail": str(exc)},
            status_code=500
        )
    return templates.TemplateResponse(
        "errors/500.html",
        {"request": request},
        status_code=500
    )

@app.get("/favicon.ico")
async def favicon():
    return FileResponse("static/media/favicon/favicon.ico")

@app.get("/health", status_code=status.HTTP_200_OK)
@app.head("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return JSONResponse(content={"status": "ok"})

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, user: Optional[User] = Depends(get_current_user_if_exists)):
    # return templates.TemplateResponse("index.html", {"request": request, "user": user})
    return RedirectResponse(url="/totp/list")
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(settings.PORT or 8000), reload=True)
