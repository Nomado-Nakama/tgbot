from pathlib import Path

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings

project_root_path = Path(__file__).parent.parent


class Settings(BaseSettings):
    BOT_TOKEN: str
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_URL: PostgresDsn = "postgresql://postgres:postgres@localhost:5432/tgbot_nakama"
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: str = "6333"
    ENABLE_VECTOR_SEARCH: bool = False

    ADMINS: str

    RUNNING_ENV: str = "LOCAL"
    WEBHOOK_HOST: str = "http://localhost"
    WEBHOOK_PATH: str = "/webhook"
    WEBAPP_HOST: str = "localhost"
    WEBAPP_PORT: str = "5001"
    WEBHOOK_SECRET: str

    FULL_CONTENT_GOOGLE_DOCS_URL: str
    GOOGLE_SERVICE_ACCOUNT_BASE64: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings(_env_file=project_root_path / ".env")
