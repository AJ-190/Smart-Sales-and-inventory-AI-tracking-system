import os
from typing import Optional
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    SMS_API_KEY: str = Field(default=os.getenv("SMS_KEY", ""), validation_alias="SMS_KEY")
    SMS_USERNAME: str = os.getenv("SMS_USERNAME", "sandbox")
    SMS_SENDER_ID: str = os.getenv("SMS_SENDER_ID", "")
    SMS_API_URL: str = os.getenv("SMS_API_URL", "https://api.sandbox.africastalking.com/version1/messaging")
    ACCESS_TOKEN_TIME: int = 60
    SUPER_ADMIN_EMAIL: str = os.getenv("SUPER_ADMIN_EMAIL", "")
    SUPER_ADMIN_APP_PASSWORD: str = os.getenv("SUPER_ADMIN_APP_PASSWORD", "")
    SUPER_ADMIN_NAME: str = os.getenv("SUPER_ADMIN_NAME", "")
    REFRESH_TOKEN_TIME: int = 7 * 24 * 60
    API_AUTH_KEY: Optional[str] = os.getenv("API_auth_key", "")
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
    MAIL_USERNAME: str = os.getenv("SUPER_ADMIN_EMAIL", "")
    MAIL_PASSWORD: str = os.getenv("SUPER_ADMIN_APP_PASSWORD", "")
    MAIL_FROM:str = os.getenv("SUPER_ADMIN_EMAIL", "")
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    MAIL_PORT:int = 587
    MAIL_SERVER: str = os.getenv("MAIL_SERVER", "")
    MAIL_STARTTLS:bool = True
    MAIL_SSL_TLS:bool = False
    USE_CREDENTIALS:bool = True
    VALIDATE_CERTS:bool = False
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    REQUEST_LIMIT_EXPIRY: int = 60
    REQUEST_LIMIT: int = 5
    

def get_settings():
    return Settings()
