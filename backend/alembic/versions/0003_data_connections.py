"""Tables for push ingest, per-project API keys, and panel data sources.

Revision ID: 0003_connections
Revises: 0002_panels
Create Date: 2026-10-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_connections"
down_revision: Union[str, None] = "0002_panels"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
    op.create_table(
        "ingest_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_ingest_snapshots_project_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("project_id", "kind", name="uq_ingest_snapshot_kind"),
    )
    op.create_table(
        "panel_data_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("panel_key", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
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
            name="fk_panel_data_sources_project_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("project_id", "panel_key", name="uq_panel_data_source"),
    )


def downgrade() -> None:
    op.drop_table("panel_data_sources")
    op.drop_table("ingest_snapshots")
    op.drop_table("project_api_keys")
