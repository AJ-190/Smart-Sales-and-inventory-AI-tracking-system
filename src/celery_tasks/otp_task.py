from pydantic import BaseModel
from fastapi_mail import NameEmail, MessageSchema, MessageType
from typing import List
import random
import logging
from fastapi import status, HTTPException
from src.mail import mail
from src.db.redis import otp_verification
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


async def send_otp(email: str):
    from src.main import app

    if not app.state.redis:
        print(f"[OTP] Redis is unavailable. app.state type: {type(app.state)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OTP service is unavailable. Please try again later."
        )

    otp = str(random.randint(1000000, 9999999))
    name_email = NameEmail(name="", email=email)

    body = f"""<h1> Sales and Inventory Tracking System </h1>
            <h2> Hi, your account verification code is: {otp}
            this verification code is valid for 5 minutes.</h2>
            <p> Please don't share this code with anyone</p>
            """
    await otp_verification(app.state.redis, email, otp=otp, store=True)
    message = MessageSchema(
        subject="Account Verification",
        recipients=[name_email],
        body=body,
        subtype=MessageType.html
    )

    try:
        await mail.send_message(message)
    except Exception as e:
        logger.error("Failed to send OTP email to %s: %s", email, e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to send verification email. Please try again later."
        )
    return JSONResponse(status_code=status.HTTP_200_OK,
                        content={"msg": "OTP-verification code is sent"})


async def verify_otp(email: str, otp: str):
    from src.main import app

    if not app.state.redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OTP service is unavailable. Please try again later."
        )

    red_otp = await otp_verification(app.state.redis, email=email, store=False)

    if not red_otp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OTP code has expired or user not registered")
    if str(red_otp) != otp:
        return False
    await app.state.redis.delete(f"email:{email}")
    return True
