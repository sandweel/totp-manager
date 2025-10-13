from typing import Optional, Tuple
from datetime import datetime
import httpx
from config import settings, templates, http_client


class EmailService:
    @staticmethod
    async def send_confirmation_email(email: str, confirmation_token: str) -> Tuple[bool, Optional[str]]:
        """
        Send email confirmation
        Returns: (success, error_message)
        """
        try:
            link = f"{settings.FRONTEND_URL}/auth/confirm?token={confirmation_token}"
            html_content = templates.get_template("email/confirmation_email.html").render(
                link=link, 
                year=datetime.now().year
            )
            
            await http_client.post(
                f"https://api.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages",
                auth=("api", settings.MAILGUN_API_KEY),
                data={
                    "from": f"no-reply@{settings.MAILGUN_DOMAIN}",
                    "to": [email],
                    "subject": "Confirm your account",
                    "html": html_content
                }
            )
            return True, None
        except Exception as e:
            return False, f"Failed to send confirmation email: {str(e)}"

    @staticmethod
    async def send_password_reset_email(email: str, reset_token: str) -> Tuple[bool, Optional[str]]:
        """
        Send password reset email
        Returns: (success, error_message)
        """
        try:
            link = f"{settings.FRONTEND_URL}/auth/reset-password/confirm?token={reset_token}"
            html_content = templates.get_template("email/reset_password_email.html").render(
                link=link, 
                year=datetime.now().year
            )
            
            await http_client.post(
                f"https://api.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages",
                auth=("api", settings.MAILGUN_API_KEY),
                data={
                    "from": f"no-reply@{settings.MAILGUN_DOMAIN}",
                    "to": [email],
                    "subject": "Reset your password",
                    "html": html_content
                }
            )
            return True, None
        except Exception as e:
            return False, f"Failed to send reset email: {str(e)}"
