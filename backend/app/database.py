"""SQLite engine and session factory. Paths resolve against the backend root."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def resolve_sqlite_url(url: str, backend_root: Path) -> str:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    raw_path = url[len(prefix) :]
    if raw_path == ":memory:" or raw_path.startswith("file:"):
        return url
    path = Path(raw_path)
    if not path.is_absolute():
        path = (backend_root / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def make_engine(url: str | None = None) -> Engine:
    settings = get_settings()
    resolved = resolve_sqlite_url(url or settings.database_url, settings.backend_root)
    engine = create_engine(
        resolved,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_conn, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _session_factory
    if _engine is None:
        _engine = make_engine()
        _session_factory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


def get_db() -> Iterator[Session]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
