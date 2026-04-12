import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ── Alembic config object ────────────────────────────────────────────────────
config = context.config

# Set up Python logging from the ini file (skip when config_file_name is None,
# e.g. when called programmatically from api/main.py).
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Target metadata — read from our SQLAlchemy models ────────────────────────
from api.db import Base  # noqa: E402  (import after sys.path is set)

target_metadata = Base.metadata

# ── Database URL ──────────────────────────────────────────────────────────────
# env.py always wins over the placeholder in alembic.ini.
_raw_url = os.getenv(
    "DATABASE_URL",
    "postgresql://tharusan@localhost:5432/brokerdb",
)
# Normalise to psycopg3 driver — mirrors the logic in api/db.py.
_db_url = (
    _raw_url
    .replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    .replace("postgresql://", "postgresql+psycopg://", 1)
)
config.set_main_option("sqlalchemy.url", _db_url)


# ── Migration runners ─────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL to stdout)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection.

    Sets a 30s lock_timeout so ALTER TABLE statements fail fast if the
    old container revision is still holding locks, instead of hanging
    until the startup probe kills the container.
    """
    from sqlalchemy import text

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # Fail fast on lock conflicts instead of hanging forever.
        # lock_timeout covers explicit LOCK TABLE; statement_timeout covers
        # DDL (ALTER TABLE) which implicitly acquires ACCESS EXCLUSIVE lock.
        connection.execute(text("SET lock_timeout = '30s'"))
        connection.execute(text("SET statement_timeout = '60s'"))
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
