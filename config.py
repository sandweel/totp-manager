import os
import base64
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from fastapi.templating import Jinja2Templates
from sqlalchemy import Column, Integer, String, text

load_dotenv()

class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL")
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

settings = Settings()

try:
    fernet = Fernet(settings.ENCRYPTION_KEY)
except ValueError:
    raw = base64.b64decode(settings.ENCRYPTION_KEY)
    fernet = Fernet(base64.urlsafe_b64encode(raw))

engine = create_async_engine(settings.DATABASE_URL, future=True, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

templates = Jinja2Templates(directory="templates")

class TOTPItem(Base):
    __tablename__ = "totp_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    encrypted_secret = Column(String(256), nullable=False)

