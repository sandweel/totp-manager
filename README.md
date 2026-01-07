# 🔐 TOTP Manager

A secure service for managing and sharing TOTP (2FA) secrets.  
Built with **FastAPI**, **SQLAlchemy (async)**, **MySQL/MariaDB**, **Fernet encryption**, and **TailwindCSS** for styling.

## 🛠 Functionality

- 🔑 **User Authentication**
  - Registration and login with email verification
  - Secure password hashing (bcrypt)
  - Session management with access & refresh tokens
  - Automatic token refresh via HttpOnly cookies
  - Option to restrict registration to specific email domains

- 🔐 **TOTP Management**
  - Add, update, and delete TOTP entries
  - Secrets encrypted per user (using a DEK encrypted with a master key)
  - Real-time one-time password (OTP) generation
  - Export raw TOTP secrets
  - Import/export via **Google Authenticator migration URIs**
  - Generate **QR codes** for easy setup

- 👥 **Sharing**
  - Share TOTP entries with other registered users
  - Shared secrets are re-encrypted with the recipient’s key
  - View who has access to each shared TOTP
  - Revoke access at any time

---
### ⚙️ Setup and Run (Local)

### 1. Clone the repository
```sh
git clone https://github.com/sandweel/totp-manager.git
cd totp-manager
```
### 2. Backend: create virtual environment & install dependencies
Backend: create virtual environment & install dependencies
```sh
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
### 3. Frontend: build Tailwind CSS
Backend: create virtual environment & install dependencies
```sh
cd tailwindcss
npm install
npm run build
```
For development with live reload
```sh
npm run watch
```
### 4. Configure environment
Copy `.env_example` → `.env` and update the values according to your setup:

```ini
# Database connection string (async MySQL)
DATABASE_URL=mysql+asyncmy://<username>:<password>@<host>:<port>/<database>

# Encryption key (Base64 string, 32 bytes before encoding → ~44 characters after base64)
# Used for encrypting sensitive data with Fernet
ENCRYPTION_KEY=

# Secret key (random string, at least 32 bytes recommended, 64+ better)
# Used for signing JWT tokens and other HMAC operations
SECRET_KEY=

# URL of the frontend application (used in email templates)
FRONTEND_URL=http://localhost:8000

# Allowed email domains for registration (comma-separated).
# Example: test1.com,test2.com or leave empty to allow any domain
ALLOWED_EMAIL_DOMAINS=

# Application port (default: 8000)
PORT=

# Access token lifetime in minutes (short-lived JWT used in the browser)
ACCESS_TOKEN_EXPIRE_MINUTES=5

# Refresh token lifetime in days (long-lived token to renew access tokens)
REFRESH_TOKEN_EXPIRE_DAYS=30

# Cookie security
# true  → cookies only over HTTPS (recommended for production)
# false → cookies also work over HTTP (useful for local development)
COOKIE_SECURE=false

# Mailgun API credentials (for sending emails)
MAILGUN_API_KEY=
MAILGUN_DOMAIN=

### Number of Gunicorn workers. Used only when running the app via Docker Compose.
GUNICORN_WORKERS=
```
### 5. Apply initial migration
```sh
alembic revision --autogenerate -m "initial migration"
alembic upgrade head
```
### 6. Download the latest MaxMind GeoIP City database (GeoLite2-City.mmdb)
##### From the official [website](https://dev.maxmind.com/geoip/geoip2/geolite2/) or third-party repositories

```sh
wget https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-City.mmdb -O data/GeoLite2-City.mmdb
```

### 7. Run the service
```sh
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
The app will be available at:
👉 http://localhost:8000

# Docker Compose
```sh
docker compose up -d
```
> **Note**:
> Make sure to prepare **.env** before starting docker or docker compose
