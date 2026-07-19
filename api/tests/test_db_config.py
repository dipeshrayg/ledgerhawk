"""The DATABASE_URL -> engine config split (app.db.engine_kwargs) is what
makes the Postgres migration path real rather than aspirational: this
verifies the branching logic directly, without needing a live Postgres
server to prove it works.
"""
from app.db import engine_kwargs


def test_sqlite_url_gets_thread_check_disabled_no_pool_args():
    kwargs = engine_kwargs("sqlite:///./ledgerhawk.db")
    assert kwargs == {"connect_args": {"check_same_thread": False}}


def test_postgres_url_gets_connection_pool_args():
    kwargs = engine_kwargs("postgresql://user:pass@host:5432/ledgerhawk")
    assert kwargs["pool_size"] == 10
    assert kwargs["max_overflow"] == 20
    assert kwargs["pool_pre_ping"] is True
    assert "connect_args" not in kwargs


def test_mysql_url_also_gets_pool_args_not_sqlite_branch():
    kwargs = engine_kwargs("mysql+pymysql://user:pass@host/ledgerhawk")
    assert "pool_size" in kwargs
