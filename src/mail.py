from fastapi_mail import FastMail, ConnectionConfig
from src.config import get_settings


connection = ConnectionConfig(
    MAIL_USERNAME = get_settings().MAIL_USERNAME,
    MAIL_PASSWORD = get_settings().MAIL_PASSWORD,
    MAIL_FROM = get_settings().MAIL_FROM,
    MAIL_PORT = get_settings().MAIL_PORT,
    MAIL_SERVER = get_settings().MAIL_SERVER,
    MAIL_STARTTLS = get_settings().MAIL_STARTTLS,
    MAIL_SSL_TLS = get_settings().MAIL_SSL_TLS,
    USE_CREDENTIALS = get_settings().USE_CREDENTIALS,
    VALIDATE_CERTS = get_settings().VALIDATE_CERTS
)

mail = FastMail()