import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from config import engine, Base, templates, settings
from routes.auth import router as auth_router
from routes.totp import router as totp_router
from routes.api import router as api_router

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(auth_router)
app.include_router(totp_router)
app.include_router(api_router)

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
#    if request.url.path.startswith("/auth") or request.url.path.startswith("/static") or request.url.path in ["/", "/openapi.json", "/docs", "/docs/oauth2-redirect"]:
    if request.url.path.startswith("/auth") or request.url.path.startswith("/static"):
        return await call_next(request)
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/auth/login")
    try:
        return await call_next(request)
    except:
        return RedirectResponse(url="/auth/login")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(settings.PORT or 8000), reload=True)
