import uvicorn
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.status import HTTP_404_NOT_FOUND, HTTP_422_UNPROCESSABLE_ENTITY

from config import templates, settings
from routes.auth import router as auth_router, get_current_user_if_exists
from routes.totp import router as totp_router
from routes.api import router as api_router
from models import User
from typing import Optional
from starlette.middleware.sessions import SessionMiddleware


app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(auth_router)
app.include_router(totp_router)
app.include_router(api_router)

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
#    if request.url.path.startswith("/auth") or request.url.path.startswith("/static") or request.url.path in ["/", "/openapi.json", "/docs", "/docs/oauth2-redirect"]:
    if request.url.path.startswith("/auth") or request.url.path.startswith("/static") or request.url.path.startswith("/docs") or request.url.path == "/openapi.json":
        return await call_next(request)
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/auth/login")
    try:
        return await call_next(request)
    except:
        return RedirectResponse(url="/auth/login")

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException, user: Optional[User] = Depends(get_current_user_if_exists)):
    user = await get_current_user_if_exists(request)
    if exc.status_code == HTTP_404_NOT_FOUND:
        return templates.TemplateResponse("errors/404.html", {"request": request, "user": user}, status_code=404)
    raise exc


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    user = await get_current_user_if_exists(request)
    return templates.TemplateResponse("errors/422.html", {
        "request": request,
        "errors": exc.errors(),
        "user": user,
    }, status_code=HTTP_422_UNPROCESSABLE_ENTITY)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, user: Optional[User] = Depends(get_current_user_if_exists)):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(settings.PORT or 8000), reload=True)
