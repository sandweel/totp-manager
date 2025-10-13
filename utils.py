import re
import secrets
import string
from typing import Optional
from cryptography.fernet import Fernet


def generate_fernet_key() -> bytes:
    """Generate a new Fernet encryption key"""
    return Fernet.generate_key()


def is_valid_base32(secret: str) -> bool:
    """Check if string is valid Base32"""
    secret_clean = secret.strip().replace(" ", "")
    base32_pattern = re.compile(r'^[A-Z2-7]{16,}={0,6}$', re.IGNORECASE)
    return bool(base32_pattern.match(secret_clean))


def sanitize_input(text: str, max_length: Optional[int] = None) -> str:
    """Sanitize user input"""
    if not text:
        return ""
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    # Limit length if specified
    if max_length:
        text = text[:max_length]
    
    return text
