import os
import base64
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from fastapi.templating import Jinja2Templates
import httpx

load_dotenv()

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY")
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "5"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
    ACCESS_TOKEN_COOKIE_NAME: str = os.getenv("ACCESS_TOKEN_COOKIE_NAME", "access_token")
    REFRESH_TOKEN_COOKIE_NAME: str = os.getenv("REFRESH_TOKEN_COOKIE_NAME", "refresh_token")
    CSRF_REFRESH_COOKIE_NAME: str = os.getenv("CSRF_REFRESH_COOKIE_NAME", "csrf_refresh")
    REFRESH_TOKEN_PEPPER: str = os.getenv("REFRESH_TOKEN_PEPPER", "")
    MAILGUN_API_KEY: str = os.getenv("MAILGUN_API_KEY")
    MAILGUN_DOMAIN: str = os.getenv("MAILGUN_DOMAIN")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:8000")
    PORT: str = os.getenv("PORT", "8000")

settings = Settings()

try:
    master_fernet = Fernet(settings.ENCRYPTION_KEY)
except ValueError:
    raw = base64.b64decode(settings.ENCRYPTION_KEY)
    master_fernet = Fernet(base64.urlsafe_b64encode(raw))

engine = create_async_engine(settings.DATABASE_URL, future=True, echo=False, pool_pre_ping=True, pool_recycle=3600)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

templates = Jinja2Templates(directory="templates")

http_client = httpx.AsyncClient()
