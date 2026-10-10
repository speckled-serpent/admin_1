"""Sales data set to Fake reads the charges fixture through the real create and settings routes."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import IngestSnapshot, ProjectSource
from app.services.auth import register_user

AS_OF = "2026-10-10T12:00:00+00:00"


def _auth(client: TestClient, session_factory: sessionmaker[Session]) -> dict[str, str]:
    db = session_factory()
    try:
        register_user(db, "dev", "devpass")
    finally:
        db.close()
    logged_in = client.post("/api/auth/login", json={"username": "dev", "password": "devpass"})
    assert logged_in.status_code == 200
    return {"Authorization": f"Bearer {logged_in.json()['token']}"}


def _assert_fixture(body: dict[str, object]) -> None:
    assert body["currency"] == "usd"
    assert body["gross_amount"] == 15900
    assert body["refunded_amount"] == 1700
    assert body["net_amount"] == 14200
    assert body["succeeded_count"] == 6
    assert body["charge_count"] == 8
    charges = body["charges"]
    assert isinstance(charges, list)
    assert charges[0]["id"] == "ch_acme_1008"


def test_create_with_fake_sales_shows_fixture_revenue(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    headers = _auth(client, session_factory)
    created = client.post(
        "/api/projects",
        headers=headers,
        json={
            "name": "Harbor",
            "panels": ["logs", "sales-data"],
            "sources": [
                {"panel": "logs", "mode": "fake", "connection": None},
                {"panel": "sales-data", "mode": "fake", "connection": None},
            ],
        },
    )
    assert created.status_code == 201

    revenue = client.get("/api/projects/harbor/revenue", headers=headers)
    assert revenue.status_code == 200
    body = revenue.json()
    assert body["project"] == {"slug": "harbor", "name": "Harbor"}
    _assert_fixture(body)

    db = session_factory()
    try:
        assert db.query(ProjectSource).count() == 0
    finally:
        db.close()


def test_settings_fake_shows_fixture_and_push_does_not(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    headers = _auth(client, session_factory)
    created = client.post(
        "/api/projects",
        headers=headers,
        json={"name": "Harbor", "panels": ["sales-data"]},
    )
    assert created.status_code == 201

    initial = client.get("/api/projects/harbor/revenue", headers=headers)
    assert initial.status_code == 200
    _assert_fixture(initial.json())

    pushed = client.put(
        "/api/projects/harbor/panels/sales-data/settings",
        headers=headers,
        json={"mode": "push", "new_connection": {"name": "Billing", "kind": "push"}},
    )
    assert pushed.status_code == 200
    assert pushed.json()["mode"] == "push"
    hidden = client.get("/api/projects/harbor/revenue", headers=headers)
    assert hidden.status_code == 404

    connection_id = pushed.json()["connection_id"]
    issued = client.post(f"/api/projects/harbor/connections/{connection_id}/api-key", headers=headers)
    assert issued.status_code == 201
    ingested = client.post(
        "/api/ingest/harbor",
        headers={"Authorization": f"Bearer {issued.json()['key']}"},
        json={
            "schema_version": 1,
            "revenue": {
                "currency": "usd",
                "gross_amount": 500,
                "refunded_amount": 100,
                "net_amount": 400,
                "as_of": AS_OF,
            },
        },
    )
    assert ingested.status_code == 200
    still_hidden = client.get("/api/projects/harbor/revenue", headers=headers)
    assert still_hidden.status_code == 404

    db = session_factory()
    try:
        snapshot = db.scalar(select(IngestSnapshot).where(IngestSnapshot.kind == "revenue"))
        assert snapshot is not None
        assert db.query(ProjectSource).count() == 0
    finally:
        db.close()

    restored = client.put(
        "/api/projects/harbor/panels/sales-data/settings",
        headers=headers,
        json={"mode": "fake"},
    )
    assert restored.status_code == 200
    assert restored.json()["mode"] == "fake"
    shown = client.get("/api/projects/harbor/revenue", headers=headers)
    assert shown.status_code == 200
    _assert_fixture(shown.json())


def test_project_without_sales_panel_has_no_revenue(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    headers = _auth(client, session_factory)
    created = client.post("/api/projects", headers=headers, json={"name": "Lumen", "panels": ["logs"]})
    assert created.status_code == 201
    missing = client.get("/api/projects/lumen/revenue", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "No revenue source is configured for this project"
