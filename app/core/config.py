from dotenv import load_dotenv
load_dotenv()
import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_TIME: int = 60
    SUPER_ADMIN_EMAIL: str = os.getenv("SUPER_ADMIN_EMAIL")
    SUPER_ADMIN_APP_PASSWORD: str = os.getenv("SUPER_ADMIN_APP_PASSWORD")
    SUPER_ADMIN_NAME: str = os.getenv("SUPER_ADMIN_NAME")
    
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
settings = Settings()

