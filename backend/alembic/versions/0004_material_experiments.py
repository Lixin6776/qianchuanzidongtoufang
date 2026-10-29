"""material experiment loop

Revision ID: 0004_material_experiments
Revises: 0003_strategy_execution_loop
Create Date: 2026-10-29
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_material_experiments"
down_revision: str | None = "0003_strategy_execution_loop"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "material_experiments" in tables:
        return
    op.create_table(
        "material_experiments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("analysis_id", sa.String(length=36), nullable=False),
        sa.Column("analysis_date", sa.String(length=10), nullable=False),
        sa.Column("material_id", sa.String(length=80), nullable=False),
        sa.Column("material_name", sa.String(length=240), nullable=False),
        sa.Column("action_type", sa.String(length=48), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("baseline_metrics", sa.JSON(), nullable=False),
        sa.Column("success_criteria", sa.JSON(), nullable=False),
        sa.Column("stop_condition", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("execution_job_id", sa.String(length=36), nullable=True),
        sa.Column("observation_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observation_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_material_experiments_analysis_id", "material_experiments", ["analysis_id"])
    op.create_index("ix_material_experiments_material_id", "material_experiments", ["material_id"])


def downgrade() -> None:
    op.drop_table("material_experiments")
