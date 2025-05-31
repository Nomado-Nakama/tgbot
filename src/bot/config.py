from pydantic import BaseSettings, PostgresDsn


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: PostgresDsn = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/tgbot_nakama"
    )
    QDRANT_URL: str = "http://localhost:6333"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()  # singleton
