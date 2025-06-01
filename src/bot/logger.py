import os
import sys
from pathlib import Path

from loguru import logger

from src.bot.config import project_root_path

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_PATH = Path(os.getenv("LOG_PATH", "logs"))
LOG_PATH.mkdir(exist_ok=True)

logger.remove()  # drop default
logger.add(
    project_root_path / LOG_PATH / "bot_{time:YYYYMMDD}.log",
    rotation="10 MB",
    retention=3,
    level=LOG_LEVEL,
    enqueue=True,
)
logger.add(sys.stdout, level=LOG_LEVEL, enqueue=True)
