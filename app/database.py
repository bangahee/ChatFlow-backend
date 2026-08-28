from collections.abc import Generator

from fastapi import Request
from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


def create_db_engine(database_url: str) -> Engine:
    """Create an engine configured for the selected database backend."""
    url = make_url(database_url)
    engine_kwargs: dict[str, object] = {"pool_pre_ping": True}

    if url.get_backend_name() == "sqlite":
        engine_kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_engine(database_url, **engine_kwargs)

    if url.get_backend_name() == "sqlite":

        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create the request-scoped SQLAlchemy session factory."""
    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )


def create_schema(engine: Engine) -> None:
    """Create the schema and apply the supported SQLite compatibility upgrade."""
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_user_admin_column(engine)


def _ensure_user_admin_column(engine: Engine) -> None:
    """Add the persisted admin role to legacy SQLite databases exactly once."""
    if engine.dialect.name != "sqlite":
        return

    user_columns = {
        column["name"] for column in inspect(engine).get_columns("users")
    }
    if "is_admin" in user_columns:
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE users "
                "ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"
            )
        )


def get_db(request: Request) -> Generator[Session, None, None]:
    """Yield a database session tied to the current FastAPI application."""
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    with session_factory() as session:
        yield session
