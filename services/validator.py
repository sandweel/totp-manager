import re
from typing import Optional
from config import settings
from constants import AppConstants
from utils import is_valid_base32, sanitize_input

_email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def validate_email(email: str) -> Optional[str]:
    email = (email or "").strip()
    if not _email_re.match(email):
        return "Invalid email address"
    allowed = getattr(settings, "ALLOWED_EMAIL_DOMAINS", []) or []
    if allowed:
        try:
            domain = email.split("@", 1)[1].lower()
        except IndexError:
            return "Invalid email address"
        if domain not in allowed:
            return f"Registration with this email domain is not allowed."
    return None

def validate_password(password: str) -> Optional[str]:
    if len(password) < AppConstants.MIN_PASSWORD_LENGTH:
        return f"Password must be at least {AppConstants.MIN_PASSWORD_LENGTH} characters long"
    if not re.search(r"\d", password):
        return "Password must contain at least one digit"
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter"
    if not re.search(r"[!@#$%^&*(),._?\":{}|<>]", password):
        return "Password must contain at least one special character"
    return None

def validate_totp(account: str, issuer: str, secret: str) -> Optional[str]:
    account = sanitize_input(account)
    issuer = sanitize_input(issuer)
    secret = sanitize_input(secret)
    
    if not account:
        return "Account is required."
    if len(account) > AppConstants.MAX_ACCOUNT_LENGTH:
        return f"Account is too long (max {AppConstants.MAX_ACCOUNT_LENGTH} characters)."
    
    if not issuer:
        return "Issuer is required."
    if len(issuer) > AppConstants.MAX_ISSUER_LENGTH:
        return f"Issuer is too long (max {AppConstants.MAX_ISSUER_LENGTH} characters)."

    if not secret:
        return "Secret is required."
    
    if not is_valid_base32(secret):
        return "Secret must be a valid Base32 string."

    return None
