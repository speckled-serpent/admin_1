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
from app.models import Connection, ConnectionApiKey, IngestSnapshot, PanelDataSource, Project, ProjectPanel
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


def _assign(client: TestClient, headers: dict[str, str], slug: str, panel: str, body: dict) -> dict:
    saved = client.put(f"/api/projects/{slug}/panels/{panel}/settings", headers=headers, json=body)
    assert saved.status_code == 200, saved.text
    return saved.json()


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
    health = _assign(
        client,
        headers,
        "harbor",
        "system-health",
        {"mode": "push", "new_connection": {"name": "App", "kind": "push"}},
    )
    connection_id = health["connection_id"]
    _assign(client, headers, "harbor", "user-data", {"mode": "push", "connection_id": connection_id})

    denied = client.post("/api/ingest/harbor", json=_good_payload())
    assert denied.status_code == 401

    session_as_key = client.post("/api/ingest/harbor", headers=headers, json=_good_payload())
    assert session_as_key.status_code == 401

    issued = client.post(f"/api/projects/harbor/connections/{connection_id}/api-key", headers=headers)
    assert issued.status_code == 201
    plaintext = issued.json()["key"]
    assert plaintext.startswith("a1_")
    assert issued.json()["prefix"] == plaintext[:12]

    db = session_factory()
    try:
        stored = db.query(ConnectionApiKey).one()
        assert stored.key_hash == hash_token(plaintext)
        assert plaintext not in stored.key_hash
        assert plaintext not in stored.prefix
        dumped = json.dumps({"hash": stored.key_hash, "prefix": stored.prefix})
        assert plaintext not in dumped
    finally:
        db.close()

    listed = client.get("/api/projects/harbor/panels/system-health/settings", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["connections"][0]["api_key"]["prefix"] == plaintext[:12]
    assert plaintext not in listed.text

    duplicate = client.post(f"/api/projects/harbor/connections/{connection_id}/api-key", headers=headers)
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

    rotated = client.post(f"/api/projects/harbor/connections/{connection_id}/api-key/rotate", headers=headers)
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

    revoked = client.delete(f"/api/projects/harbor/connections/{connection_id}/api-key", headers=headers)
    assert revoked.status_code == 204
    after_revoke = client.post(
        "/api/ingest/harbor",
        headers={"Authorization": f"Bearer {new_key}"},
        json=_good_payload(),
    )
    assert after_revoke.status_code == 401


def test_shared_connection_routes_sections_by_panel_type(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = _auth(client, session_factory, monkeypatch)
    created = client.post(
        "/api/projects",
        headers=headers,
        json={
            "name": "Harbor",
            "panels": ["system-health", "user-data", "sales-data"],
            "connections": [
                {"key": "app", "name": "App server", "kind": "push"},
                {"key": "billing", "name": "Billing", "kind": "push"},
            ],
            "sources": [
                {"panel": "system-health", "mode": "push", "connection": "app"},
                {"panel": "user-data", "mode": "push", "connection": "app"},
                {"panel": "sales-data", "mode": "push", "connection": "billing"},
            ],
        },
    )
    assert created.status_code == 201

    db = session_factory()
    try:
        connections = list(db.scalars(select(Connection).order_by(Connection.id)))
        assert [row.name for row in connections] == ["App server", "Billing"]
        app_id, billing_id = connections[0].id, connections[1].id
    finally:
        db.close()

    app_key = client.post(f"/api/projects/harbor/connections/{app_id}/api-key", headers=headers).json()["key"]
    billing_key = client.post(f"/api/projects/harbor/connections/{billing_id}/api-key", headers=headers).json()["key"]

    ingested = client.post(
        "/api/ingest/harbor",
        headers={"Authorization": f"Bearer {app_key}"},
        json=_good_payload(),
    )
    assert ingested.status_code == 200

    db = session_factory()
    try:
        health = db.scalar(select(PanelDataSource).where(PanelDataSource.panel_key == "system-health"))
        users = db.scalar(select(PanelDataSource).where(PanelDataSource.panel_key == "user-data"))
        sales = db.scalar(select(PanelDataSource).where(PanelDataSource.panel_key == "sales-data"))
        assert health is not None and users is not None and sales is not None
        assert health.connection_id == users.connection_id == app_id
        assert sales.connection_id == billing_id
        assert health.last_status == "up"
        assert users.last_received_at is not None
        assert sales.last_received_at is None
        app_kinds = {
            row.kind
            for row in db.scalars(select(IngestSnapshot).where(IngestSnapshot.connection_id == app_id))
        }
        assert app_kinds == {"health", "users", "revenue", "costs"}
        assert list(db.scalars(select(IngestSnapshot).where(IngestSnapshot.connection_id == billing_id))) == []
    finally:
        db.close()

    sales_payload = {
        "schema_version": 1,
        "health": {"status": "down", "checked_at": AS_OF, "latency_ms": 9},
        "revenue": _good_payload()["revenue"],
    }
    billed = client.post(
        "/api/ingest/harbor",
        headers={"Authorization": f"Bearer {billing_key}"},
        json=sales_payload,
    )
    assert billed.status_code == 200

    db = session_factory()
    try:
        health = db.scalar(select(PanelDataSource).where(PanelDataSource.panel_key == "system-health"))
        sales = db.scalar(select(PanelDataSource).where(PanelDataSource.panel_key == "sales-data"))
        assert health is not None and sales is not None
        assert health.last_status == "up"
        assert sales.last_received_at is not None
        billing_health = db.scalar(
            select(IngestSnapshot).where(
                IngestSnapshot.connection_id == billing_id,
                IngestSnapshot.kind == "health",
            )
        )
        assert billing_health is not None
        assert json.loads(billing_health.body)["status"] == "down"
    finally:
        db.close()


def test_ingest_writes_only_valid_sections(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = _auth(client, session_factory, monkeypatch)
    client.post("/api/projects", headers=headers, json={"name": "Lumen", "panels": ["system-health", "user-data"]})
    settings = _assign(
        client,
        headers,
        "lumen",
        "system-health",
        {"mode": "push", "new_connection": {"name": "App", "kind": "push"}},
    )
    issued = client.post(f"/api/projects/lumen/connections/{settings['connection_id']}/api-key", headers=headers)
    key_headers = {"Authorization": f"Bearer {issued.json()['key']}"}

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

    sources = client.get("/api/projects/lumen/panels/system-health/settings", headers=headers)
    assert sources.json()["last_status"] == "up"
    assert sources.json()["last_received_at"] is not None
    assert sources.json()["allowed_modes"] == ["fake", "push", "http-health"]
    logs = client.get("/api/projects/lumen/panels/logs/settings", headers=headers)
    assert logs.status_code == 422


def test_http_health_connector_uses_the_injected_client(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = _auth(client, session_factory, monkeypatch)
    client.post("/api/projects", headers=headers, json={"name": "Harbor", "panels": ["system-health", "logs"]})
    saved = _assign(
        client,
        headers,
        "harbor",
        "system-health",
        {
            "mode": "http-health",
            "new_connection": {
                "name": "Harbor probe",
                "kind": "http-health",
                "url": "https://harbor.example/health",
                "expected_status": 204,
                "timeout_seconds": 3,
                "secret": "harbor-token",
            },
        },
    )
    assert saved["connections"][0]["has_secret"] is True
    assert "harbor-token" not in json.dumps(saved)

    db = session_factory()
    try:
        row = db.scalar(select(Connection).where(Connection.kind == "http-health"))
        assert row is not None
        assert row.secret_ciphertext is not None
        assert "harbor-token" not in row.secret_ciphertext
        assert decrypt_secret(row.secret_ciphertext) == "harbor-token"
    finally:
        db.close()

    logs = client.put(
        "/api/projects/harbor/panels/logs/settings",
        headers=headers,
        json={
            "mode": "http-health",
            "new_connection": {
                "name": "Logs probe",
                "kind": "http-health",
                "url": "https://harbor.example/health",
                "expected_status": 200,
                "timeout_seconds": 3,
            },
        },
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
        connection = db.scalar(select(Connection).where(Connection.kind == "http-health"))
        assert connection is not None
        connection.last_received_at = now - timedelta(seconds=301)
        db.commit()
        again = FakeHttp(status_code=204)
        checked_ids = poll_due_http_health(db, again, now)
        assert checked_ids == [connection.id]
        assert again.calls[0][0] == "https://harbor.example/health"
    finally:
        db.close()


def test_delete_panel_keeps_the_shared_connection(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = _auth(client, session_factory, monkeypatch)
    client.post(
        "/api/projects",
        headers=headers,
        json={"name": "Harbor", "panels": ["system-health", "user-data"]},
    )
    settings = _assign(
        client,
        headers,
        "harbor",
        "system-health",
        {"mode": "push", "new_connection": {"name": "App", "kind": "push"}},
    )
    connection_id = settings["connection_id"]
    _assign(client, headers, "harbor", "user-data", {"mode": "push", "connection_id": connection_id})
    removed = client.delete("/api/projects/harbor/panels/system-health", headers=headers)
    assert removed.status_code == 204
    listed = client.get("/api/projects", headers=headers)
    assert listed.json()[0]["panels"] == ["user-data"]

    db = session_factory()
    try:
        assert db.query(Connection).count() == 1
        assert db.query(ProjectPanel).count() == 1
        users = db.scalar(select(PanelDataSource).where(PanelDataSource.panel_key == "user-data"))
        assert users is not None
        assert users.connection_id == connection_id
        assert db.scalar(select(PanelDataSource).where(PanelDataSource.panel_key == "system-health")) is None
    finally:
        db.close()


def test_delete_project_removes_keys_snapshots_and_sources(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = _auth(client, session_factory, monkeypatch)
    client.post("/api/projects", headers=headers, json={"name": "Harbor", "panels": ["system-health"]})
    settings = _assign(
        client,
        headers,
        "harbor",
        "system-health",
        {"mode": "push", "new_connection": {"name": "App", "kind": "push"}},
    )
    issued = client.post(
        f"/api/projects/harbor/connections/{settings['connection_id']}/api-key",
        headers=headers,
    )
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
        assert db.query(Connection).count() == 0
        assert db.query(ConnectionApiKey).count() == 0
        assert db.query(IngestSnapshot).count() == 0
        assert db.query(PanelDataSource).count() == 0
    finally:
        db.close()
