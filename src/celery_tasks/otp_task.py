from pydantic import BaseModel
from fastapi_mail import NameEmail, MessageSchema, MessageType
from typing import List
import random
from fastapi import status, HTTPException
from src.mail import mail
from src.db.redis import otp_verification
from starlette.responses import JSONResponse

    
async def send_otp(email: str):
    from src.main import app
            
    otp = str(random.randint(1000000, 9999999))
    name_email = NameEmail(name="", email=email)
    
    body = f"""<h1> Your verification code is:{otp}"""
    await otp_verification(app.state.redis, email, otp=otp, store=True)
    message = MessageSchema(
        subject="Account Verification",
        recipients=[name_email],
        body=body,
        subtype=MessageType.html
    )
        
    await mail.send_message(message)
    return JSONResponse(status_code=status.HTTP_200_OK, 
                        content={"msg": "OTP-verification code is sent"})
    
async def verify_otp(email: str, otp: str):
    from src.main import app
    
    red_otp = await otp_verification(app.state.redis, email=email, store=False)
    
    if not red_otp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OTP code has expired or user not registered")
    if str(red_otp) != otp:
        return False
    await app.state.redis.delete(f"email:{email}")
    return True