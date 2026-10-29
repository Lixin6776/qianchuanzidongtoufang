"""operations task center

Revision ID: 0005_ops_tasks
Revises: 0004_material_experiments
Create Date: 2026-10-29
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_ops_tasks"
down_revision: str | None = "0004_material_experiments"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    if "ops_tasks" in set(sa.inspect(op.get_bind()).get_table_names()):
        return
    op.create_table(
        "ops_tasks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("owner", sa.String(length=120), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("success_criteria", sa.Text(), nullable=False),
        sa.Column("stop_condition", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ops_tasks_source_id", "ops_tasks", ["source_id"])


def downgrade() -> None:
    op.drop_table("ops_tasks")
