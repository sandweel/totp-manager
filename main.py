import uvicorn
import logging
from typing import Optional
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import FileResponse
from config import templates, settings
from routes.auth import router as auth_router, get_current_user_if_exists, set_auth_cookies_in_response_if_needed
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

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(auth_router)
app.include_router(totp_router)
app.include_router(api_router)
app.include_router(sessions_router)

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    response = await call_next(request)
    set_auth_cookies_in_response_if_needed(request, response)
    return response

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException, user: Optional[User] = Depends(get_current_user_if_exists)):
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
    user = await get_current_user_if_exists(request)
    return templates.TemplateResponse(
        "errors/422.html",
        {"request": request, "errors": exc.errors(), "user": user},
        status_code=422
    )
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.exception(f"Unhandled error for request: {request.url}")
    return templates.TemplateResponse(
        "errors/500.html",
        {"request": request},
        status_code=500
    )

@app.get("/favicon.ico")
async def favicon():
    return FileResponse("static/media/favicon/favicon.ico")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, user: Optional[User] = Depends(get_current_user_if_exists)):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(settings.PORT or 8000), reload=True)
