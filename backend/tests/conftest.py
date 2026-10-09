"""Offline test setup. Outbound sockets are refused for the whole suite."""

from __future__ import annotations

import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import app.database as database
from app.config import get_settings
from app.database import Base, get_db, make_engine
from app.main import app

_ALLOWED_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _host_of(address: object) -> object:
    if isinstance(address, tuple) and address:
        return address[0]
    return address


class _GuardedSocket(socket.socket):
    def connect(self, address: object) -> None:  # type: ignore[override]
        host = _host_of(address)
        if host not in _ALLOWED_HOSTS:
            raise RuntimeError(f"Outbound network is disabled in tests ({address!r})")
        super().connect(address)  # type: ignore[arg-type]

    def connect_ex(self, address: object) -> int:  # type: ignore[override]
        host = _host_of(address)
        if host not in _ALLOWED_HOSTS:
            raise RuntimeError(f"Outbound network is disabled in tests ({address!r})")
        return super().connect_ex(address)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _offline_and_isolated(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(socket, "socket", _GuardedSocket)
    get_settings.cache_clear()
    database._engine = None
    database._session_factory = None
    yield
    get_settings.cache_clear()
    database._engine = None
    database._session_factory = None
    app.dependency_overrides.clear()


@pytest.fixture
def session_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker[Session]]:
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    engine = make_engine(url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield factory
    engine.dispose()


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
