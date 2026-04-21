"""Resend email service — password reset + weekly summary emails."""
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


async def send_weekly_summary_email(
    to_email: str,
    user_name: str,
    workout_summary: str,
    nutrition_summary: str,
    alex_note: str,
    app_url: str,
) -> None:
    """Send the weekly summary email from Alex. Runs Resend's sync SDK in a thread pool."""
    await asyncio.to_thread(
        _send_weekly_sync, to_email, user_name, workout_summary, nutrition_summary, alex_note, app_url
    )


def _send_weekly_sync(
    to_email: str,
    user_name: str,
    workout_summary: str,
    nutrition_summary: str,
    alex_note: str,
    app_url: str,
) -> None:
    import resend

    workout_html = "".join(
        f"<p style='margin:4px 0;'>{line}</p>"
        for line in workout_summary.splitlines()
        if line.strip()
    )
    resend.api_key = settings.resend_api_key
    resend.Emails.send({
        "from": settings.resend_from_email,
        "to": [to_email],
        "subject": "Your week with Alex 💪",
        "html": f"""
            <div style="font-family: sans-serif; max-width: 520px; margin: 0 auto; color: #111;">
                <h2 style="margin-bottom:4px;">Hey {user_name} 👋</h2>
                <p style="color:#555;">Here's your plan for the week ahead.</p>

                <h3 style="margin-top:24px; border-bottom:2px solid #000; padding-bottom:4px;">WORKOUTS</h3>
                {workout_html}

                <h3 style="margin-top:24px; border-bottom:2px solid #000; padding-bottom:4px;">NUTRITION THIS WEEK</h3>
                <p style="margin:4px 0;">{nutrition_summary}</p>

                <h3 style="margin-top:24px; border-bottom:2px solid #000; padding-bottom:4px;">ALEX SAYS</h3>
                <p style="font-style:italic; color:#333;">"{alex_note}"</p>

                <a href="{app_url}"
                   style="display:inline-block;margin-top:24px;padding:12px 28px;
                          background:#111;color:#fff;text-decoration:none;border-radius:6px;font-weight:bold;">
                   Open App →
                </a>
                <p style="margin-top:24px;color:#999;font-size:12px;">
                    You're receiving this because you have an Alex PT account.
                </p>
            </div>
        """,
    })
