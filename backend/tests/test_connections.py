import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.connectors.http import HttpResponse, HttpTransportError, get_http_client
from app.crypto import decrypt_secret
from app.errors import InvalidPayload
from app.ingest_schema import validate_ingest
from app.main import app
from app.models import IngestSnapshot, PanelDataSource, Project, ProjectApiKey, ProjectPanel
from app.security import hash_token
from app.services.auth import register_user
from app.services.connections import poll_due_http_health

TEST_FERNET_KEY = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
AS_OF = "2026-10-10T12:00:00+00:00"


class FakeHttp:
    def __init__(self, status_code: int = 200, error: Exception | None = None) -> None:
        self.status_code = status_code
        self.error = error
        self.calls: list[tuple[str, float, dict[str, str] | None]] = []

    def get(self, url: str, timeout: float, headers: dict[str, str] | None = None) -> HttpResponse:
        self.calls.append((url, timeout, headers))
        if self.error is not None:
            raise self.error
        return HttpResponse(status_code=self.status_code, elapsed_ms=12)


def _auth(client: TestClient, session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setenv("CONNECTOR_MASTER_KEY", TEST_FERNET_KEY)
    from app.config import get_settings

    get_settings.cache_clear()
    db = session_factory()
    try:
        register_user(db, "dev", "devpass")
    finally:
        db.close()
    logged_in = client.post("/api/auth/login", json={"username": "dev", "password": "devpass"})
    assert logged_in.status_code == 200
    return {"Authorization": f"Bearer {logged_in.json()['token']}"}


def _good_payload() -> dict:
    return {
        "schema_version": 1,
        "health": {"status": "up", "checked_at": AS_OF, "latency_ms": 20},
        "users": {"daily_active": 4, "new": 1, "monthly_returning": 3, "as_of": AS_OF},
        "revenue": {
            "currency": "usd",
            "gross_amount": 500,
            "refunded_amount": 100,
            "net_amount": 400,
            "as_of": AS_OF,
        },
        "costs": {"currency": "usd", "amount": 80, "as_of": AS_OF},
    }


def test_ingest_schema_accepts_a_full_payload_and_rejects_bad_and_partial_sections() -> None:
    accepted = validate_ingest(_good_payload())
    assert set(accepted) == {"health", "users", "revenue", "costs"}

    health_only = validate_ingest({"schema_version": 1, "health": _good_payload()["health"]})
    assert set(health_only) == {"health"}

    with pytest.raises(InvalidPayload):
        validate_ingest({"schema_version": 2, "health": _good_payload()["health"]})
    with pytest.raises(InvalidPayload):
        validate_ingest({"schema_version": 1})
    with pytest.raises(InvalidPayload):
        validate_ingest({"schema_version": 1, "health": {"status": "up", "checked_at": AS_OF}})
    with pytest.raises(InvalidPayload):
        validate_ingest(
            {
                "schema_version": 1,
                "revenue": {
                    "currency": "usd",
                    "gross_amount": 500,
                    "refunded_amount": 100,
                    "net_amount": 999,
                    "as_of": AS_OF,
                },
            }
        )
    with pytest.raises(InvalidPayload):
        validate_ingest({"schema_version": 1, "notes": {"status": "up"}})


def test_api_key_is_stored_as_a_hash_and_ingest_checks_it(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = _auth(client, session_factory, monkeypatch)
    created = client.post(
        "/api/projects",
        headers=headers,
        json={"name": "Harbor", "panels": ["system-health", "user-data", "sales-data"]},
    )
    assert created.status_code == 201
    client.put(
        "/api/projects/harbor/panels/system-health/data-source",
        headers=headers,
        json={"mode": "push"},
    )
    client.put(
        "/api/projects/harbor/panels/user-data/data-source",
        headers=headers,
        json={"mode": "push"},
    )

    denied = client.post("/api/ingest/harbor", json=_good_payload())
    assert denied.status_code == 401

    session_as_key = client.post("/api/ingest/harbor", headers=headers, json=_good_payload())
    assert session_as_key.status_code == 401

    issued = client.post("/api/projects/harbor/api-key", headers=headers)
    assert issued.status_code == 201
    plaintext = issued.json()["key"]
    assert plaintext.startswith("a1_")
    assert issued.json()["prefix"] == plaintext[:12]

    db = session_factory()
    try:
        stored = db.query(ProjectApiKey).one()
        assert stored.key_hash == hash_token(plaintext)
        assert plaintext not in stored.key_hash
        assert plaintext not in stored.prefix
        dumped = json.dumps(
            {
                "hash": stored.key_hash,
                "prefix": stored.prefix,
            }
        )
        assert plaintext not in dumped
    finally:
        db.close()

    listed = client.get("/api/projects/harbor/data-sources", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["api_key"]["prefix"] == plaintext[:12]
    assert plaintext not in listed.text

    duplicate = client.post("/api/projects/harbor/api-key", headers=headers)
    assert duplicate.status_code == 422

    ingested = client.post(
        "/api/ingest/harbor",
        headers={"Authorization": f"Bearer {plaintext}"},
        json=_good_payload(),
    )
    assert ingested.status_code == 200
    assert set(ingested.json()["accepted"]) == {"health", "users", "revenue", "costs"}

    other = client.post("/api/projects", headers=headers, json={"name": "Orbit", "panels": ["logs"]})
    assert other.status_code == 201
    wrong_project = client.post(
        "/api/ingest/orbit",
        headers={"Authorization": f"Bearer {plaintext}"},
        json=_good_payload(),
    )
    assert wrong_project.status_code == 401

    rotated = client.post("/api/projects/harbor/api-key/rotate", headers=headers)
    assert rotated.status_code == 201
    new_key = rotated.json()["key"]
    assert new_key != plaintext
    stale = client.post(
        "/api/ingest/harbor",
        headers={"Authorization": f"Bearer {plaintext}"},
        json=_good_payload(),
    )
    assert stale.status_code == 401
    fresh = client.post(
        "/api/ingest/harbor",
        headers={"Authorization": f"Bearer {new_key}"},
        json={"schema_version": 1, "health": _good_payload()["health"]},
    )
    assert fresh.status_code == 200
    assert fresh.json()["accepted"] == ["health"]

    revoked = client.delete("/api/projects/harbor/api-key", headers=headers)
    assert revoked.status_code == 204
    after_revoke = client.post(
        "/api/ingest/harbor",
        headers={"Authorization": f"Bearer {new_key}"},
        json=_good_payload(),
    )
    assert after_revoke.status_code == 401


def test_ingest_writes_only_valid_sections(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = _auth(client, session_factory, monkeypatch)
    client.post("/api/projects", headers=headers, json={"name": "Lumen", "panels": ["system-health", "user-data"]})
    client.put(
        "/api/projects/lumen/panels/system-health/data-source",
        headers=headers,
        json={"mode": "push"},
    )
    issued = client.post("/api/projects/lumen/api-key", headers=headers)
    key = issued.json()["key"]
    key_headers = {"Authorization": f"Bearer {key}"}

    bad = client.post(
        "/api/ingest/lumen",
        headers=key_headers,
        json={"schema_version": 1, "health": {"status": "sideways", "checked_at": AS_OF, "latency_ms": 1}},
    )
    assert bad.status_code == 422

    partial = client.post(
        "/api/ingest/lumen",
        headers=key_headers,
        json={"schema_version": 1, "users": {"daily_active": 1, "as_of": AS_OF}},
    )
    assert partial.status_code == 422

    ok = client.post(
        "/api/ingest/lumen",
        headers=key_headers,
        json={"schema_version": 1, "health": _good_payload()["health"]},
    )
    assert ok.status_code == 200

    db = session_factory()
    try:
        rows = list(db.scalars(select(IngestSnapshot)))
        assert [row.kind for row in rows] == ["health"]
        assert json.loads(rows[0].body)["status"] == "up"
        panel = db.scalar(select(PanelDataSource).where(PanelDataSource.panel_key == "system-health"))
        assert panel is not None
        assert panel.last_status == "up"
        assert panel.last_received_at is not None
        users = db.scalar(select(PanelDataSource).where(PanelDataSource.panel_key == "user-data"))
        assert users is not None
        assert users.last_received_at is None
    finally:
        db.close()

    sources = client.get("/api/projects/lumen/data-sources", headers=headers)
    health = next(item for item in sources.json()["panels"] if item["panel_key"] == "system-health")
    assert health["last_status"] == "up"
    assert health["last_received_at"] is not None
    assert health["allowed_modes"] == ["fake", "push", "http-health"]
    logs_missing = [item for item in sources.json()["panels"] if item["panel_key"] == "logs"]
    assert logs_missing == []


def test_http_health_connector_uses_the_injected_client(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = _auth(client, session_factory, monkeypatch)
    client.post("/api/projects", headers=headers, json={"name": "Harbor", "panels": ["system-health", "logs"]})
    saved = client.put(
        "/api/projects/harbor/panels/system-health/data-source",
        headers=headers,
        json={
            "mode": "http-health",
            "url": "https://harbor.example/health",
            "expected_status": 204,
            "timeout_seconds": 3,
            "secret": "harbor-token",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["has_secret"] is True
    assert "harbor-token" not in saved.text

    db = session_factory()
    try:
        row = db.scalar(select(PanelDataSource).where(PanelDataSource.panel_key == "system-health"))
        assert row is not None
        assert row.secret_ciphertext is not None
        assert "harbor-token" not in row.secret_ciphertext
        assert decrypt_secret(row.secret_ciphertext) == "harbor-token"
    finally:
        db.close()

    logs = client.put(
        "/api/projects/harbor/panels/logs/data-source",
        headers=headers,
        json={"mode": "http-health", "url": "https://harbor.example/health", "expected_status": 200, "timeout_seconds": 3},
    )
    assert logs.status_code == 422

    fake = FakeHttp(status_code=204)
    app.dependency_overrides[get_http_client] = lambda: fake
    checked = client.post("/api/projects/harbor/panels/system-health/test-connection", headers=headers)
    assert checked.status_code == 200
    assert checked.json()["ok"] is True
    assert checked.json()["last_status"] == "up"
    assert fake.calls == [
        ("https://harbor.example/health", 3.0, {"Authorization": "Bearer harbor-token"}),
    ]

    fake.status_code = 500
    missed = client.post("/api/projects/harbor/panels/system-health/test-connection", headers=headers)
    assert missed.status_code == 200
    assert missed.json()["ok"] is False
    assert missed.json()["last_status"] == "down"

    fake.error = HttpTransportError("Could not reach the health check URL")
    failed = client.post("/api/projects/harbor/panels/system-health/test-connection", headers=headers)
    assert failed.json()["last_status"] == "down"
    app.dependency_overrides.pop(get_http_client, None)

    db = session_factory()
    try:
        project = db.scalar(select(Project).where(Project.slug == "harbor"))
        assert project is not None
        now = datetime.now(timezone.utc)
        quiet = FakeHttp(status_code=204)
        assert poll_due_http_health(db, quiet, now) == []
        assert quiet.calls == []
        row = db.scalar(select(PanelDataSource).where(PanelDataSource.panel_key == "system-health"))
        assert row is not None
        row.last_received_at = now - timedelta(seconds=301)
        db.commit()
        again = FakeHttp(status_code=204)
        checked_ids = poll_due_http_health(db, again, now)
        assert checked_ids == [row.id]
        assert again.calls[0][0] == "https://harbor.example/health"
    finally:
        db.close()


def test_delete_project_removes_keys_snapshots_and_sources(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = _auth(client, session_factory, monkeypatch)
    client.post("/api/projects", headers=headers, json={"name": "Harbor", "panels": ["system-health"]})
    client.put(
        "/api/projects/harbor/panels/system-health/data-source",
        headers=headers,
        json={"mode": "push"},
    )
    issued = client.post("/api/projects/harbor/api-key", headers=headers)
    client.post(
        "/api/ingest/harbor",
        headers={"Authorization": f"Bearer {issued.json()['key']}"},
        json={"schema_version": 1, "health": _good_payload()["health"]},
    )
    deleted = client.delete("/api/projects/harbor", headers=headers)
    assert deleted.status_code == 204
    db = session_factory()
    try:
        assert db.query(Project).count() == 0
        assert db.query(ProjectPanel).count() == 0
        assert db.query(ProjectApiKey).count() == 0
        assert db.query(IngestSnapshot).count() == 0
        assert db.query(PanelDataSource).count() == 0
    finally:
        db.close()
