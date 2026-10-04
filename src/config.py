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
    SYNC_DATABASE_URL: str = os.getenv("SYNC_DATABASE_URL", "")
    SAILUP_API_URL: str = os.getenv(
        "SAILUP_API_URL", "https://api.sailup.io/v1/sms/"
    )
    SAILUP_API_KEY: str = os.getenv("SAILUP_API_KEY", "")
    # Must be registered in the Sailup dashboard or the send is rejected.
    SAILUP_SENDER_ID: str = os.getenv("SAILUP_SENDER_ID", "")
    ACCESS_TOKEN_TIME: int = 60
    SUPER_ADMIN_EMAIL: str = os.getenv("SUPER_ADMIN_EMAIL", "")
    SUPER_ADMIN_APP_PASSWORD: str = os.getenv("SUPER_ADMIN_APP_PASSWORD", "")
    SUPER_ADMIN_NAME: str = os.getenv("SUPER_ADMIN_NAME", "")
    REFRESH_TOKEN_TIME: int = 7 * 24 * 60
    API_AUTH_KEY: Optional[str] = os.getenv("API_AUTH_KEY") or os.getenv("API_auth_key", "")
    # extra="ignore" so a stale or renamed env var in a deploy dashboard cannot
    # stop the whole API from booting.
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }
    MAIL_USERNAME: str = os.getenv("SUPER_ADMIN_EMAIL", "")
    MAIL_PASSWORD: str = os.getenv("SUPER_ADMIN_APP_PASSWORD", "")
    MAIL_FROM:str = os.getenv("SUPER_ADMIN_EMAIL", "")
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    MAIL_PORT:int = 587
    MAIL_SERVER: str = os.getenv("MAIL_SERVER", "")
    MAIL_STARTTLS:bool = True
    MAIL_SSL_TLS:bool = False
    USE_CREDENTIALS:bool = True
    VALIDATE_CERTS:bool = True
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    BREVO_API_KEY: str = os.getenv("BREVO_API_KEY", "")
    BREVO_API_URL: str = os.getenv(
        "BREVO_API_URL", "https://api.brevo.com/v3/smtp/email"
    )
    REQUEST_LIMIT_EXPIRY: int = 60
    REQUEST_LIMIT: int = 5
    WS_TICKET_TTL: int = 300

    @property
    def sms_configured(self) -> bool:
        """True when Sailup has an API key. Without one every send fails."""
        return bool(self.SAILUP_API_KEY.strip() and self.SAILUP_SENDER_ID.strip())


def get_settings():
    return Settings()
