# Application constants
import os
from dotenv import load_dotenv

load_dotenv()

class AppConstants:
    # Password validation
    MIN_PASSWORD_LENGTH = 10
    
    # TOTP validation
    MAX_ACCOUNT_LENGTH = 32
    MAX_ISSUER_LENGTH = 32
    
    # Session management
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
    
    # Rate limiting
    PASSWORD_RESET_COOLDOWN_MINUTES = 1
    
    # Email
    EMAIL_CONFIRMATION_EXPIRE_HOURS = 24
    PASSWORD_RESET_EXPIRE_HOURS = 1
