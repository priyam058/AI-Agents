"""Resend email service — used for password reset emails."""
import asyncio

from app.core.config import settings


async def send_password_reset_email(to_email: str, reset_url: str, user_name: str) -> None:
    """Send a password reset email. Runs Resend's sync SDK in a thread pool."""
    await asyncio.to_thread(_send_sync, to_email, reset_url, user_name)


def _send_sync(to_email: str, reset_url: str, user_name: str) -> None:
    import resend
    resend.api_key = settings.resend_api_key
    resend.Emails.send({
        "from": settings.resend_from_email,
        "to": [to_email],
        "subject": "Reset your Alex PT password",
        "html": f"""
            <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
                <h2>Password Reset</h2>
                <p>Hi {user_name},</p>
                <p>Click the button below to reset your password. This link expires in 1 hour.</p>
                <a href="{reset_url}"
                   style="display:inline-block;padding:12px 24px;background:#000;color:#fff;
                          text-decoration:none;border-radius:6px;margin:16px 0;">
                   Reset Password
                </a>
                <p style="color:#666;font-size:13px;">
                    If you didn't request this, you can safely ignore this email.
                </p>
            </div>
        """,
    })
