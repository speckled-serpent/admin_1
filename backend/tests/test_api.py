from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.main import app as fastapi_app
from app.models import AuthSession
from app.security import hash_token
from app.seed import seed
from app.services.auth import register_user, user_for_token


def _seed(session_factory: sessionmaker[Session]) -> None:
    db = session_factory()
    try:
        seed(db, get_settings())
    finally:
        db.close()


def test_telemetry_is_disabled() -> None:
    assert fastapi_app._telemetry["tracing"] is False
    assert fastapi_app._telemetry["metrics"] is False
    assert fastapi_app._telemetry["logs"] is False
    assert fastapi_app._telemetry["operation_spans"] is False
    assert fastapi_app._telemetry["auto_configure"] is False


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _bind_revenue_fixture(session_factory: sessionmaker[Session]) -> None:
    """Attach the charges fixture to a project the default seed does not create."""
    from app.models import Project, ProjectPanel, ProjectSource
    from app.services.revenue import KIND_REVENUE

    db = session_factory()
    try:
        project = Project(slug="harbor", name="Harbor")
        db.add(project)
        db.flush()
        db.add(
            ProjectSource(
                project_id=project.id,
                kind=KIND_REVENUE,
                adapter_key="fixture.revenue",
                fixture_path="fixtures/acme_notes_charges.json",
            )
        )
        db.add(ProjectPanel(project_id=project.id, panel_key="sales-data"))
        db.commit()
    finally:
        db.close()


def test_login_and_revenue_for_bound_fixture(client: TestClient, session_factory: sessionmaker[Session]) -> None:
    _seed(session_factory)
    denied = client.get("/api/projects/harbor/revenue")
    assert denied.status_code == 401

    bad = client.post("/api/auth/login", json={"username": "dev", "password": "nope"})
    assert bad.status_code == 401

    logged_in = client.post("/api/auth/login", json={"username": "dev", "password": "devpass"})
    assert logged_in.status_code == 200
    token = logged_in.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json() == {"username": "dev"}

    projects = client.get("/api/projects", headers=headers)
    assert projects.status_code == 200
    assert projects.json() == []

    _bind_revenue_fixture(session_factory)
    revenue = client.get("/api/projects/harbor/revenue", headers=headers)
    assert revenue.status_code == 200
    body = revenue.json()
    assert body["project"] == {"slug": "harbor", "name": "Harbor"}
    assert body["currency"] == "usd"
    assert body["gross_amount"] == 15900
    assert body["refunded_amount"] == 1700
    assert body["net_amount"] == 14200
    assert body["succeeded_count"] == 6
    assert body["charge_count"] == 8
    assert body["charges"][0]["id"] == "ch_acme_1008"

    missing = client.get("/api/projects/lumen/revenue", headers=headers)
    assert missing.status_code == 404

    logged_out = client.post("/api/auth/logout", headers=headers)
    assert logged_out.status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_seed_is_idempotent(session_factory: sessionmaker[Session]) -> None:
    _seed(session_factory)
    _seed(session_factory)
    db = session_factory()
    try:
        from app.models import Project, ProjectPanel, ProjectSource, User

        assert db.query(User).count() == 1
        assert db.query(Project).count() == 0
        assert db.query(ProjectSource).count() == 0
        assert db.query(ProjectPanel).count() == 0
    finally:
        db.close()


def test_expired_session_is_rejected(session_factory: sessionmaker[Session]) -> None:
    db = session_factory()
    try:
        user = register_user(db, "dev", "devpass")
        db.add(
            AuthSession(
                token_hash=hash_token("stale-token"),
                user_id=user.id,
                expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        )
        db.commit()
        assert user_for_token(db, "stale-token") is None
        assert user_for_token(db, "stale-token") is None
    finally:
        db.close()
