"""Store the panels selected for each project.

Revision ID: 0002_panels
Revises: 0001_core
Create Date: 2026-10-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_panels"
down_revision: Union[str, None] = "0001_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_panels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("panel_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_panels_project_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("project_id", "panel_key", name="uq_project_panel_key"),
    )


def downgrade() -> None:
    op.drop_table("project_panels")
