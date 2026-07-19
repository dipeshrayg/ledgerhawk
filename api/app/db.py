import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Swappable for real deployments: SQLite is a single-file, single-writer
# store -- fine for the demo and for a single local instance, but the
# ceiling under concurrent write load. Setting DATABASE_URL (e.g. to a
# Postgres DSN) is the only change needed to move past it, because every
# query in this codebase goes through SQLAlchemy's engine/session, never
# raw sqlite3 calls. See docs/ARCHITECTURE.md#scaling for the full plan
# (pooling, read replicas, background workers) this one line unlocks.
DB_PATH = Path(__file__).resolve().parents[1] / "ledgerhawk.db"


def engine_kwargs(database_url: str) -> dict:
    """Connection args for `database_url`. Split out from engine creation so
    the SQLite-vs-real-database branching is unit-testable without needing
    an actual Postgres server -- see tests/test_db_config.py."""
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    # Pool settings only make sense for a real client/server database --
    # SQLite's "engine" is a file handle, not a connection pool.
    return {"pool_size": 10, "max_overflow": 20, "pool_pre_ping": True}


DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
engine = create_engine(DATABASE_URL, **engine_kwargs(DATABASE_URL))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
