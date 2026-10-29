"""strategy lifecycle and execution feedback

Revision ID: 0003_strategy_execution_loop
Revises: 0002_learning_tables
Create Date: 2026-10-29
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_strategy_execution_loop"
down_revision: str | None = "0002_learning_tables"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _columns(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    profile_columns = {
        "source_suggestion_id": sa.String(length=36),
        "parent_profile_id": sa.String(length=36),
        "activated_at": sa.DateTime(timezone=True),
        "retired_at": sa.DateTime(timezone=True),
    }
    for name, kind in profile_columns.items():
        if name not in _columns("strategy_profiles"):
            op.add_column("strategy_profiles", sa.Column(name, kind, nullable=True))

    suggestion_columns = {
        "draft_profile_id": sa.String(length=36),
        "activated_profile_id": sa.String(length=36),
        "evaluation_id": sa.String(length=36),
        "decided_at": sa.DateTime(timezone=True),
    }
    for name, kind in suggestion_columns.items():
        if name not in _columns("strategy_suggestions"):
            op.add_column("strategy_suggestions", sa.Column(name, kind, nullable=True))

    evaluation_columns = {
        "strategy_profile_id": sa.String(length=36),
        "suggestion_id": sa.String(length=36),
        "window_start": sa.DateTime(timezone=True),
        "window_end": sa.DateTime(timezone=True),
    }
    for name, kind in evaluation_columns.items():
        if name not in _columns("strategy_evaluations"):
            op.add_column("strategy_evaluations", sa.Column(name, kind, nullable=True))


def downgrade() -> None:
    pass
