from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import BACKEND_ROOT, get_settings


def test_upgrade_moves_per_panel_sources_onto_shared_connections(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "legacy.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    command.upgrade(config, "0003_connections")

    now = datetime.now(timezone.utc)
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO projects (slug, name, created_at) VALUES ('harbor', 'Harbor', :created_at)"),
            {"created_at": now},
        )
        project_id = conn.execute(text("SELECT id FROM projects WHERE slug = 'harbor'")).scalar_one()
        for key in ("system-health", "user-data", "sales-data"):
            conn.execute(
                text(
                    "INSERT INTO project_panels (project_id, panel_key, created_at) "
                    "VALUES (:project_id, :panel_key, :created_at)"
                ),
                {"project_id": project_id, "panel_key": key, "created_at": now},
            )
        conn.execute(
            text(
                "INSERT INTO panel_data_sources ("
                "project_id, panel_key, mode, url, expected_status, timeout_seconds, secret_ciphertext, created_at"
                ") VALUES (:project_id, 'system-health', 'http-health', :url, 204, 3, 'cipher', :created_at)"
            ),
            {"project_id": project_id, "url": "https://harbor.example/health", "created_at": now},
        )
        for key in ("user-data", "sales-data"):
            conn.execute(
                text(
                    "INSERT INTO panel_data_sources (project_id, panel_key, mode, created_at) "
                    "VALUES (:project_id, :panel_key, 'push', :created_at)"
                ),
                {"project_id": project_id, "panel_key": key, "created_at": now},
            )
        conn.execute(
            text(
                "INSERT INTO project_api_keys (project_id, key_hash, prefix, created_at) "
                "VALUES (:project_id, 'abc123', 'a1_oldprefix', :created_at)"
            ),
            {"project_id": project_id, "created_at": now},
        )
        conn.execute(
            text(
                "INSERT INTO ingest_snapshots (project_id, kind, schema_version, body, received_at) "
                "VALUES (:project_id, 'users', 1, :body, :received_at)"
            ),
            {"project_id": project_id, "body": '{"daily_active": 1}', "received_at": now},
        )
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        names = inspect(engine).get_table_names()
        assert "project_api_keys" not in names
        columns = {column["name"] for column in inspect(engine).get_columns("panel_data_sources")}
        assert "url" not in columns
        assert "secret_ciphertext" not in columns
        assert "connection_id" in columns

        connections = conn.execute(text("SELECT id, name, kind, url FROM connections ORDER BY id")).mappings().all()
        assert [(row["name"], row["kind"]) for row in connections] == [("Push", "push"), ("HTTP health", "http-health")]
        push_id = connections[0]["id"]
        http_id = connections[1]["id"]
        assert connections[1]["url"] == "https://harbor.example/health"

        panels = conn.execute(
            text("SELECT panel_key, mode, connection_id FROM panel_data_sources ORDER BY panel_key")
        ).mappings().all()
        by_panel = {row["panel_key"]: row for row in panels}
        assert by_panel["user-data"]["connection_id"] == push_id
        assert by_panel["sales-data"]["connection_id"] == push_id
        assert by_panel["system-health"]["connection_id"] == http_id
        assert by_panel["system-health"]["mode"] == "http-health"

        keys = conn.execute(text("SELECT connection_id, key_hash, prefix FROM connection_api_keys")).mappings().all()
        assert len(keys) == 1
        assert keys[0]["connection_id"] == push_id
        assert keys[0]["key_hash"] == "abc123"
        assert keys[0]["prefix"] == "a1_oldprefix"

        snapshot = conn.execute(text("SELECT connection_id, kind FROM ingest_snapshots")).mappings().one()
        assert snapshot["connection_id"] == push_id
        assert snapshot["kind"] == "users"
    engine.dispose()
