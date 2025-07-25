import re
from typing import Optional

def validate_password(password: str) -> Optional[str]:
    if len(password) < 10:
        return "Password must be at least 10 characters long"
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
    if not account.strip():
        return "Account is required."
    if len(account) > 32:
        return "Account is too long (max 32 characters)."
    if not issuer.strip():
        return "Issuer is required."
    if len(issuer) > 32:
        return "Issuer is too long (max 32 characters)."

    if not secret.strip():
        return "Secret is required."
    secret_clean = secret.strip().replace(" ", "")
    base32_pattern = re.compile(r'^[A-Z2-7]{16,64}={0,6}$', re.IGNORECASE)
    if not base32_pattern.match(secret_clean):
        return "Secret must be a valid Base32 string."

    return None
