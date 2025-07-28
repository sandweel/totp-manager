from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
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
    password_reset_token_id = Column(String(512), nullable=True)
    password_reset_requested_at = Column(DateTime, nullable=True, default=None)

    totp_items = relationship("TOTPItem", back_populates="user")
    shared_totp_items = relationship("SharedTOTP", back_populates="shared_with_user")

class TOTPItem(Base):
    __tablename__ = "totp_items"

    id = Column(Integer, primary_key=True, index=True)
    issuer = Column(String(128), nullable=False)
    account = Column(String(128), nullable=False)
    encrypted_secret = Column(String(256), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="totp_items")
    shared_with = relationship("SharedTOTP", back_populates="totp_item")

class SharedTOTP(Base):
    __tablename__ = "shared_totp"

    id = Column(Integer, primary_key=True, index=True)
    totp_item_id = Column(Integer, ForeignKey("totp_items.id"), nullable=False)
    shared_with_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    encrypted_secret = Column(String(256), nullable=False)

    totp_item = relationship("TOTPItem", back_populates="shared_with")
    shared_with_user = relationship("User", back_populates="shared_totp_items")
