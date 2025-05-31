from logging.config import fileConfig
import sys
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# -------------------------------------------------
# 1. Make sure project root is on sys.path
#    (alembic is executed from the repo root, so `src` is already importable
#     if you used a proper package, but this is bullet-proof.)
# -------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# 2. Now we can import the app settings
from src.bot.config import settings  # noqa: E402

# -------------------------------------------------
# 3. Build a *sync* URL for Alembic
#    Replace `+asyncpg` with `+psycopg` (or drop the driver part entirely).
# -------------------------------------------------
sync_url = str(settings.POSTGRES_URL).replace("+asyncpg", "+psycopg")

# 4. Drop it into Alembic’s config **early**
config = context.config
config.set_main_option("sqlalchemy.url", sync_url)

# -------------------------------------------------
# usual Alembic boilerplate below …
# -------------------------------------------------
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


# -------------------------------------------------
def run_migrations_offline() -> None:
    context.configure(
        url=sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
