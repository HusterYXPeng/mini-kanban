"""SQLite engine setup and table creation."""

import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DEFAULT_DATABASE_URL = "sqlite:///./kanban.db"


class Base(DeclarativeBase):
    pass


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def make_engine(database_url: str) -> Engine:
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        # TestClient and request handlers run in a different thread than startup.
        connect_args["check_same_thread"] = False
    engine = create_engine(database_url, connect_args=connect_args)
    if database_url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db(engine: Engine) -> None:
    """Create tables that are not already present. Existing tables are left as-is."""
    # Import registers Column and Card on Base.metadata.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
