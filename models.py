from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from config import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(256), unique=True, index=True, nullable=False)
    hashed_password = Column(String(256), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    encrypted_dek = Column(String(512), nullable=False)

    totp_items = relationship("TOTPItem", back_populates="user")

class TOTPItem(Base):
    __tablename__ = "totp_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    encrypted_secret = Column(String(256), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="totp_items")
