from contextlib import asynccontextmanager

import asyncpg
from loguru import logger

from src.bot.config import settings

_pool: asyncpg.Pool | None = None


async def init_pool(postgres_url: str = settings.POSTGRES_URL):
    global _pool
    if _pool is None:
        logger.info("Connecting to Postgres …")
        _pool = await asyncpg.create_pool(str(postgres_url), min_size=2, max_size=10)
        logger.success("Postgres connection pool ready")


@asynccontextmanager
async def get_conn():
    if _pool is None:
        await init_pool()
    async with _pool.acquire() as conn:
        yield conn


async def fetchrow(sql: str, *args):
    async with get_conn() as conn:
        return await conn.fetchrow(sql, *args)


async def fetch(sql: str, *args):
    async with get_conn() as conn:
        return await conn.fetch(sql, *args)


async def execute(sql: str, *args):
    async with get_conn() as conn:
        return await conn.execute(sql, *args)
