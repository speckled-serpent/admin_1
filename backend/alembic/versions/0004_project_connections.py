"""Move per-panel credentials onto shared project connections.

Revision ID: 0004_project_connections
Revises: 0003_connections
Create Date: 2026-10-10

"""

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_project_connections"
down_revision: Union[str, None] = "0003_connections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("expected_status", sa.Integer(), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("secret_ciphertext", sa.Text(), nullable=True),
        sa.Column("last_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_connections_project_id",
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "connection_api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["connections.id"],
            name="fk_connection_api_keys_connection_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("key_hash", name="uq_connection_api_keys_key_hash"),
    )
    with op.batch_alter_table("ingest_snapshots") as batch:
        batch.add_column(sa.Column("connection_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_ingest_snapshots_connection_id",
            "connections",
            ["connection_id"],
            ["id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("panel_data_sources") as batch:
        batch.add_column(sa.Column("connection_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_panel_data_sources_connection_id",
            "connections",
            ["connection_id"],
            ["id"],
            ondelete="SET NULL",
        )
    _copy_legacy_sources()
    with op.batch_alter_table("ingest_snapshots") as batch:
        batch.alter_column("connection_id", existing_type=sa.Integer(), nullable=False)
        batch.drop_constraint("uq_ingest_snapshot_kind", type_="unique")
        batch.create_unique_constraint("uq_ingest_snapshot_connection_kind", ["connection_id", "kind"])
    with op.batch_alter_table("panel_data_sources") as batch:
        batch.drop_column("url")
        batch.drop_column("expected_status")
        batch.drop_column("timeout_seconds")
        batch.drop_column("secret_ciphertext")
    op.drop_table("project_api_keys")


def downgrade() -> None:
    op.create_table(
        "project_api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_api_keys_project_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("key_hash", name="uq_project_api_keys_key_hash"),
    )
    with op.batch_alter_table("panel_data_sources") as batch:
        batch.add_column(sa.Column("url", sa.Text(), nullable=True))
        batch.add_column(sa.Column("expected_status", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("timeout_seconds", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("secret_ciphertext", sa.Text(), nullable=True))
    _restore_legacy_sources()
    with op.batch_alter_table("ingest_snapshots") as batch:
        batch.drop_constraint("uq_ingest_snapshot_connection_kind", type_="unique")
        batch.drop_constraint("fk_ingest_snapshots_connection_id", type_="foreignkey")
        batch.drop_column("connection_id")
        batch.create_unique_constraint("uq_ingest_snapshot_kind", ["project_id", "kind"])
    with op.batch_alter_table("panel_data_sources") as batch:
        batch.drop_constraint("fk_panel_data_sources_connection_id", type_="foreignkey")
        batch.drop_column("connection_id")
    op.drop_table("connection_api_keys")
    op.drop_table("connections")


def _copy_legacy_sources() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    projects = bind.execute(sa.text("SELECT id FROM projects")).scalars().all()
    for project_id in projects:
        push_id = _ensure_push_connection(bind, project_id, now)
        http_rows = bind.execute(
            sa.text(
                "SELECT id, url, expected_status, timeout_seconds, secret_ciphertext, created_at "
                "FROM panel_data_sources WHERE project_id = :project_id AND mode = 'http-health'"
            ),
            {"project_id": project_id},
        ).mappings()
        for row in http_rows:
            http_id = _insert_connection(
                bind,
                project_id=project_id,
                name="HTTP health",
                kind="http-health",
                url=row["url"],
                expected_status=row["expected_status"],
                timeout_seconds=row["timeout_seconds"],
                secret_ciphertext=row["secret_ciphertext"],
                created_at=row["created_at"] or now,
            )
            bind.execute(
                sa.text("UPDATE panel_data_sources SET connection_id = :connection_id WHERE id = :id"),
                {"connection_id": http_id, "id": row["id"]},
            )
        if push_id is None:
            continue
        bind.execute(
            sa.text(
                "UPDATE panel_data_sources SET connection_id = :connection_id "
                "WHERE project_id = :project_id AND mode = 'push'"
            ),
            {"connection_id": push_id, "project_id": project_id},
        )
        bind.execute(
            sa.text("UPDATE ingest_snapshots SET connection_id = :connection_id WHERE project_id = :project_id"),
            {"connection_id": push_id, "project_id": project_id},
        )


def _ensure_push_connection(bind: sa.Connection, project_id: int, now: datetime) -> int | None:
    push_panels = bind.execute(
        sa.text("SELECT id FROM panel_data_sources WHERE project_id = :project_id AND mode = 'push'"),
        {"project_id": project_id},
    ).first()
    keys = bind.execute(
        sa.text(
            "SELECT key_hash, prefix, created_at, revoked_at FROM project_api_keys WHERE project_id = :project_id"
        ),
        {"project_id": project_id},
    ).mappings().all()
    snapshots = bind.execute(
        sa.text("SELECT id FROM ingest_snapshots WHERE project_id = :project_id"),
        {"project_id": project_id},
    ).first()
    if push_panels is None and not keys and snapshots is None:
        return None
    created = bind.execute(
        sa.text(
            "SELECT created_at FROM panel_data_sources WHERE project_id = :project_id AND mode = 'push' LIMIT 1"
        ),
        {"project_id": project_id},
    ).scalar()
    push_id = _insert_connection(
        bind,
        project_id=project_id,
        name="Push",
        kind="push",
        url=None,
        expected_status=None,
        timeout_seconds=None,
        secret_ciphertext=None,
        created_at=created or now,
    )
    for key in keys:
        bind.execute(
            sa.text(
                "INSERT INTO connection_api_keys (connection_id, key_hash, prefix, created_at, revoked_at) "
                "VALUES (:connection_id, :key_hash, :prefix, :created_at, :revoked_at)"
            ),
            {
                "connection_id": push_id,
                "key_hash": key["key_hash"],
                "prefix": key["prefix"],
                "created_at": key["created_at"],
                "revoked_at": key["revoked_at"],
            },
        )
    return push_id


def _insert_connection(
    bind: sa.Connection,
    *,
    project_id: int,
    name: str,
    kind: str,
    url: str | None,
    expected_status: int | None,
    timeout_seconds: int | None,
    secret_ciphertext: str | None,
    created_at: datetime,
) -> int:
    result = bind.execute(
        sa.text(
            "INSERT INTO connections ("
            "project_id, name, kind, url, expected_status, timeout_seconds, secret_ciphertext, created_at"
            ") VALUES ("
            ":project_id, :name, :kind, :url, :expected_status, :timeout_seconds, :secret_ciphertext, :created_at"
            ")"
        ),
        {
            "project_id": project_id,
            "name": name,
            "kind": kind,
            "url": url,
            "expected_status": expected_status,
            "timeout_seconds": timeout_seconds,
            "secret_ciphertext": secret_ciphertext,
            "created_at": created_at,
        },
    )
    connection_id = result.lastrowid
    if connection_id is None:
        raise RuntimeError("Could not create a connection row")
    return int(connection_id)


def _restore_legacy_sources() -> None:
    bind = op.get_bind()
    connections = bind.execute(
        sa.text(
            "SELECT id, project_id, kind, url, expected_status, timeout_seconds, secret_ciphertext FROM connections"
        )
    ).mappings()
    for connection in connections:
        if connection["kind"] == "http-health":
            bind.execute(
                sa.text(
                    "UPDATE panel_data_sources SET url = :url, expected_status = :expected_status, "
                    "timeout_seconds = :timeout_seconds, secret_ciphertext = :secret_ciphertext "
                    "WHERE connection_id = :connection_id"
                ),
                {
                    "url": connection["url"],
                    "expected_status": connection["expected_status"],
                    "timeout_seconds": connection["timeout_seconds"],
                    "secret_ciphertext": connection["secret_ciphertext"],
                    "connection_id": connection["id"],
                },
            )
            continue
        if connection["kind"] != "push":
            continue
        keys = bind.execute(
            sa.text(
                "SELECT key_hash, prefix, created_at, revoked_at FROM connection_api_keys "
                "WHERE connection_id = :connection_id"
            ),
            {"connection_id": connection["id"]},
        ).mappings()
        for key in keys:
            bind.execute(
                sa.text(
                    "INSERT INTO project_api_keys (project_id, key_hash, prefix, created_at, revoked_at) "
                    "VALUES (:project_id, :key_hash, :prefix, :created_at, :revoked_at)"
                ),
                {
                    "project_id": connection["project_id"],
                    "key_hash": key["key_hash"],
                    "prefix": key["prefix"],
                    "created_at": key["created_at"],
                    "revoked_at": key["revoked_at"],
                },
            )
    bind.execute(
        sa.text(
            "DELETE FROM ingest_snapshots WHERE id NOT IN ("
            "SELECT MIN(id) FROM ingest_snapshots GROUP BY project_id, kind)"
        )
    )
