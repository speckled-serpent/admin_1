from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.services.auth import register_user


def _auth(client: TestClient, session_factory: sessionmaker[Session]) -> dict[str, str]:
    db = session_factory()
    try:
        register_user(db, "dev", "devpass")
    finally:
        db.close()
    logged_in = client.post("/api/auth/login", json={"username": "dev", "password": "devpass"})
    assert logged_in.status_code == 200
    return {"Authorization": f"Bearer {logged_in.json()['token']}"}


def test_project_routes_require_auth(client: TestClient) -> None:
    assert client.get("/api/projects").status_code == 401
    assert client.get("/api/panel-catalog").status_code == 401
    assert client.post("/api/projects", json={"name": "Lumen", "panels": ["logs"]}).status_code == 401


def test_create_rejects_missing_name_or_panels(client: TestClient, session_factory: sessionmaker[Session]) -> None:
    headers = _auth(client, session_factory)

    missing_name = client.post("/api/projects", headers=headers, json={"panels": ["logs"]})
    assert missing_name.status_code == 422

    blank_name = client.post("/api/projects", headers=headers, json={"name": "   ", "panels": ["logs"]})
    assert blank_name.status_code == 422
    assert blank_name.json()["detail"] == "Name is required"

    no_panels = client.post("/api/projects", headers=headers, json={"name": "Lumen", "panels": []})
    assert no_panels.status_code == 422

    unknown = client.post("/api/projects", headers=headers, json={"name": "Lumen", "panels": ["not-a-panel"]})
    assert unknown.status_code == 422
    assert unknown.json()["detail"] == "Unknown panel: not-a-panel"


def test_create_persists_panels_and_lists_them(client: TestClient, session_factory: sessionmaker[Session]) -> None:
    headers = _auth(client, session_factory)
    created = client.post(
        "/api/projects",
        headers=headers,
        json={"name": "Lumen", "panels": ["logistics", "system-health", "system-health"]},
    )
    assert created.status_code == 201
    assert created.json() == {
        "slug": "lumen",
        "name": "Lumen",
        "panels": ["system-health", "logistics"],
    }

    listed = client.get("/api/projects", headers=headers)
    assert listed.status_code == 200
    assert listed.json() == [created.json()]

    second = client.post("/api/projects", headers=headers, json={"name": "Lumen", "panels": ["logs"]})
    assert second.status_code == 201
    assert second.json()["slug"] == "lumen-2"
    assert second.json()["panels"] == ["logs"]

    catalog = client.get("/api/panel-catalog", headers=headers)
    assert catalog.status_code == 200
    keys = [item["key"] for item in catalog.json()]
    assert "system-health" in keys
    assert "user-data" in keys
    assert "sales-data" in keys
    assert "logistics" in keys
