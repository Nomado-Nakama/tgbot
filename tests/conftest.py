import asyncio

import pytest
from testcontainers.postgres import PostgresContainer

from src.bot.db import init_pool


@pytest.fixture(scope="session", autouse=True)
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def _pg_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        await init_pool(postgres_url=pg.get_connection_url())  # re-init pool with container URL
        yield
