"""Alembic environment.

- DB connection comes from the SAME app settings as the runtime (no hardcoded
  credentials) — works locally and in the ECS migrate task.
- The Alembic version table lives in the `shared` schema (shared infrastructure).
- Chicken-and-egg: the `shared` schema must exist before Alembic can write
  alembic_version into it, so online mode creates it (idempotent) first.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import create_engine, pool, text
from alembic import context

# Make the `app` package importable (WORKDIR /app in the image; backend/ locally).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings  # noqa: E402
from app.base import Base  # noqa: E402
from app import models  # noqa: E402,F401  (registers shared spine on Base.metadata)
from app import models_staffing  # noqa: E402,F401  (registers staffing tables)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# NOTE: do NOT push the URL through config.set_main_option / ConfigParser — the
# generated DB password can contain '%', which ConfigParser misreads as
# interpolation syntax. We build the engine directly from settings.database_url
# (exactly as the running app does), bypassing ConfigParser entirely.

target_metadata = Base.metadata

# alembic_version table lives in the shared schema.
VERSION_SCHEMA = "shared"


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        version_table_schema=VERSION_SCHEMA,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Build the engine straight from the app's URL (no ConfigParser).
    connectable = create_engine(settings.database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        # Ensure the shared schema exists BEFORE Alembic stamps alembic_version
        # into it (idempotent; the first migration also creates all four).
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{VERSION_SCHEMA}"'))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=VERSION_SCHEMA,
            include_schemas=True,  # reflect shared/staffing/... so existing tables aren't re-proposed
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
