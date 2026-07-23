import asyncio
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.core.config import get_settings
from app.db.base import Base
from app.db.url import to_asyncpg_url
from app import models  # noqa: F401  (importing the package registers all models on Base.metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

DATABASE_URL = to_asyncpg_url(get_settings().database_url)

# Independent Alembic history: this service owns its own version table in its own schema,
# never the Host's or another hosted app's.
VERSION_TABLE_SCHEMA = "ha_dashboard"


def include_object(  # noqa: ANN001
    object, name, type_, reflected, compare_to  # noqa: A002
) -> bool:
    """Excludes the `host` schema from autogenerate entirely.

    If this service later adds a read-only cross-schema mapping onto `host.users` (the
    `HostUser` pattern — see event-creator's `app/models/host_user.py`), that model shares
    `Base.metadata` with everything else here so `ForeignKey("host.users.id")` can resolve.
    Without this filter, `alembic revision --autogenerate` would see `host.users` as "in our
    metadata but let's diff it against the live DB" and could propose ALTER/DROP statements
    against a table this repo has no business migrating.
    """
    return getattr(object, "schema", None) != "host"


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=VERSION_TABLE_SCHEMA,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=VERSION_TABLE_SCHEMA,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(
        DATABASE_URL, poolclass=pool.NullPool, connect_args={"statement_cache_size": 0}
    )

    async with connectable.connect() as connection:
        # Alembic creates its own alembic_version tracking table in VERSION_TABLE_SCHEMA before
        # running any migration (including 0001, which is the migration that creates that schema)
        # - against a database where ha_dashboard doesn't exist yet at all (a fresh throwaway CI
        # Postgres, or a brand-new Supabase instance), _ensure_version_table fails with
        # InvalidSchemaNameError before upgrade() ever runs. Bootstrap it here instead,
        # idempotently, mirroring doc-library's own identical fix
        # (doc-library/migrations/env.py) for the same problem.
        #
        # Must commit before handing off to do_run_migrations: a bare execute() here leaves this
        # connection in an open transaction, which flips Alembic's _in_external_transaction check
        # to True and makes it skip managing (and committing) its own transaction entirely,
        # assuming the caller owns it - but nothing then commits it either, so
        # connection.close() (via this `async with` block exiting) silently rolls back the
        # schema/role creation, the migration's own DDL, and the alembic_version bookkeeping row,
        # while `alembic upgrade head` still exits 0.
        await connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {VERSION_TABLE_SCHEMA}"))
        await connection.commit()

        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
