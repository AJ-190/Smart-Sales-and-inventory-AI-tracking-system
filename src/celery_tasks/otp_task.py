import smtplib
from email.mime.text import MIMEText
import random
import logging
import asyncio
import time
from fastapi import status, HTTPException
from src.config import get_settings
from src.db.redis import otp_verification
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


def _build_otp_html(otp: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Account Verification</title>
</head>
<body style="margin:0; padding:0; background:#f4f6f9; font-family:Arial, Helvetica, sans-serif; -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;">
<tr><td align="center" style="padding:32px 16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px; background:#ffffff; border-radius:12px; overflow:hidden; border:1px solid #e0e0e0;">
  <tr>
    <td style="background:linear-gradient(135deg,#1a3a6b 0%,#2a5298 100%); padding:32px 28px; text-align:center;">
      <p style="color:#a8c4e8; font-size:11px; letter-spacing:1.2px; margin:0 0 8px; text-transform:uppercase;">Sales &amp; Inventory Tracking System</p>
      <h1 style="color:#ffffff; font-size:20px; font-weight:600; margin:0;">Account Verification</h1>
    </td>
  </tr>
  <tr>
    <td style="padding:32px 28px; text-align:center;">
      <p style="font-size:14px; color:#555555; margin:0 0 20px; line-height:1.6;">
        Use the verification code below to complete your sign-up. This code is valid for <strong>5 minutes</strong>.
      </p>
      <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto 24px;">
        <tr>
          <td style="background:#f7f9fc; border:2px dashed #1a3a6b; border-radius:10px; padding:16px 36px;">
            <span style="font-size:32px; font-weight:700; color:#1a3a6b; letter-spacing:6px; font-family:'Courier New', monospace;">{otp}</span>
          </td>
        </tr>
      </table>
      <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
        <tr>
          <td style="background:#fff8e6; border:1px solid #f5d97a; border-radius:8px; padding:12px 16px; text-align:left;">
            <p style="font-size:13px; color:#8a6d00; margin:0; line-height:1.5;">
              &#9888;&#65039; <strong>Security tip:</strong> Never share this code with anyone. Our team will never ask for it.
            </p>
          </td>
        </tr>
      </table>
    </td>
  </tr>
  <tr>
    <td style="padding:0 28px 28px; text-align:center;">
      <p style="font-size:12px; color:#aaaaaa; margin:0; line-height:1.5;">
        This is an automated message from the Sales &amp; Inventory Tracking System.<br>
        If you did not request this code, you can safely ignore this email.
      </p>
    </td>
  </tr>
</table>
</td></tr>
</table>
</body>
</html>"""


SMTP_TIMEOUT = 30


def _send_otp_email_sync(to_email: str, otp: str) -> bool:
    settings = get_settings()
    subject = "Account Verification"
    html_body = _build_otp_html(otp)

    message = MIMEText(html_body, "html")
    message["From"] = f"{settings.SUPER_ADMIN_NAME} <{settings.SUPER_ADMIN_EMAIL}>"
    message["To"] = to_email
    message["Subject"] = subject

    for attempt in range(3):
        try:
            server = smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT, timeout=SMTP_TIMEOUT)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.SUPER_ADMIN_EMAIL, settings.SUPER_ADMIN_APP_PASSWORD)
            server.sendmail(
                from_addr=settings.SUPER_ADMIN_EMAIL,
                to_addrs=to_email,
                msg=message.as_string(),
            )
            server.quit()
            return True
        except Exception as e:
            logger.warning("OTP email attempt %d/3 failed for %s: %s", attempt + 1, to_email, e)
    logger.error("All 3 OTP email attempts failed for %s", to_email)
    return False


async def send_otp(email: str):
    from src.main import app

    if not app.state.redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OTP service is unavailable. Please try again later.",
        )

    otp = str(random.randint(1000000, 9999999))
    await otp_verification(app.state.redis, email, otp=otp, store=True)

    try:
        sent = await asyncio.to_thread(_send_otp_email_sync, email, otp)
    except Exception as e:
        logger.error("OTP email thread error for %s: %s", email, e)
        sent = False

    if not sent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to send verification email. Please try again later.",
        )

    return JSONResponse(status_code=status.HTTP_200_OK, content={"msg": "OTP-verification code is sent"})


async def verify_otp(email: str, otp: str):
    from src.main import app

    if not app.state.redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OTP service is unavailable. Please try again later.",
        )

    red_otp = await otp_verification(app.state.redis, email=email, store=False)

    if not red_otp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OTP code has expired or user not registered")
    if str(red_otp) != otp:
        return False
    await app.state.redis.delete(f"email:{email}")
    return True
