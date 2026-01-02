from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Index, Text
from sqlalchemy.orm import relationship
from datetime import datetime
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
    sessions = relationship("Session", back_populates="user")
    api_keys = relationship("ApiKey", back_populates="user")

class TOTPItem(Base):
    __tablename__ = "totp_items"

    id = Column(Integer, primary_key=True, index=True)
    issuer = Column(String(128), nullable=False)
    account = Column(String(128), nullable=False)
    encrypted_secret = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="totp_items")
    shared_with = relationship("SharedTOTP", back_populates="totp_item")

class SharedTOTP(Base):
    __tablename__ = "shared_totp"

    id = Column(Integer, primary_key=True, index=True)
    totp_item_id = Column(Integer, ForeignKey("totp_items.id"), nullable=False)
    shared_with_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    encrypted_secret = Column(Text, nullable=False)

    totp_item = relationship("TOTPItem", back_populates="shared_with")
    shared_with_user = relationship("User", back_populates="shared_totp_items")

class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    refresh_token_hash = Column(String(128), nullable=False)
    refresh_token_expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ip = Column(String(45), nullable=True)
    user_agent = Column(String(256), nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    replaced_by_session_id = Column(String(36), nullable=True)
    parent_session_id = Column(String(36), nullable=True)

    user = relationship("User", back_populates="sessions")

Index("ix_sessions_user_active", Session.user_id, Session.revoked_at)

class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    key_hash = Column(String(128), unique=True, index=True, nullable=False)
    name = Column(String(128), nullable=True)  # Опциональное имя для ключа (например, "Android App")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="api_keys")

Index("ix_api_keys_user_active", ApiKey.user_id, ApiKey.revoked_at)
