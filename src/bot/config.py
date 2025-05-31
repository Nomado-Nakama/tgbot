from pathlib import Path

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings

project_root_path = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    BOT_TOKEN: str
    POSTGRES_URL: PostgresDsn = "postgresql://postgres:postgres@localhost:5432/tgbot_nakama"
    QDRANT_URL: str = "http://localhost:6333"

    ADMINS: str

    RUNNING_ENV: str = "LOCAL"
    WEBHOOK_HOST: str = "http://localhost"
    WEBAPP_HOST: str = "localhost"
    WEBAPP_PORT: str = "5001"

    FULL_CONTENT_GOOGLE_DOCS_URL: str
    GOOGLE_SERVICE_ACCOUNT_BASE64: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings(_env_file=project_root_path / ".env")
