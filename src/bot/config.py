from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import PostgresDsn

project_root_path = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: PostgresDsn = (
        "postgresql://postgres:postgres@localhost:5432/tgbot_nakama"
    )
    QDRANT_URL: str = "http://localhost:6333"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings(_env_file=project_root_path / ".env")
