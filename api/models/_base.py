"""Database engine, session, and declarative base.

All model files import Base from here so they share a single MetaData instance.
"""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://brokeruser:brokerpass@localhost:5432/brokerdb",
)

_db_url = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1).replace(
    "postgresql+psycopg2://", "postgresql+psycopg://", 1
)

engine = create_engine(
    _db_url,
    echo=False,
    future=True,
    # Azure Postgres drops idle connections aggressively. pool_pre_ping makes
    # SQLAlchemy run a lightweight SELECT 1 on checkout and silently reconnect
    # if the connection was dropped — eliminates the transient OperationalError
    # 500s that were hitting the renewals endpoint first thing each morning.
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    # Recycle connections before Azure Postgres' idle timeout (default ~30 min).
    pool_recycle=1800,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

EMBEDDING_DIM = 512


def init_db():
    # Import all model modules so Base.metadata knows every table
    import api.models  # noqa: F401

    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
        if not existing:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
    Base.metadata.create_all(bind=engine)
