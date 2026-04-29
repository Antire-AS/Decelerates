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

    Sets statement_timeout=60s via connect_args so ALTER TABLE fails fast
    if the old container revision holds table locks. This prevents deploy
    hangs — the container crashes, Azure restarts it, and the next attempt
    either succeeds (old revision released locks) or the columns already
    exist (IF NOT EXISTS in migration DDL).
    """
    section = config.get_section(config.config_ini_section, {})
    # Neon's PgBouncer pooler rejects statement_timeout as a startup parameter.
    _connect_args = (
        {} if "neon.tech" in _db_url
        else {"options": "-c statement_timeout=60000 -c lock_timeout=30000"}
    )
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=_connect_args,
    )
    with connectable.connect() as connection:
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
