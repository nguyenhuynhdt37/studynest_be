# app/core/settings.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    DATABASE_ASYNC_URL: str = ""

    # google key
    GOOGLE_API_KEY: str = ""

    # JWT
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"

    # Mail
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""
    MAIL_PORT: int = 587
    MAIL_SERVER: str = ""
    MAIL_TLS: bool = True
    MAIL_SSL: bool = False

    TENANT_ID: str = ""
    CLIENT_ID: str = ""
    CLIENT_SECRET: str = ""
    GRAPH_BASE: str = ""

    GOOGLE_ROOT_FOLDER_ID: str = ""
    GOOGLE_CREDENTIALS_PATH: str = ""
    GOOGLE_API_KEY_CHAT: str = ""
    GOOGLE_API_CLIENT_ID_LOGIN_GOOGLE: str = ""
    GOOGLE_API_SECRET_ID_LOGIN_GOOGLE: str = ""

    HF_TOKEN: str = ""

    PISTON_URL: str = ""

    # PayPal
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: str = ""
    PAYPAL_BASE_URL: str = ""
    # PAYPAL_WEBHOOK_ID: str = ""

    FRONTEND_URL: str = ""
    BACKEND_URL: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"  # tránh crash nếu .env có key dư


settings = Settings()
