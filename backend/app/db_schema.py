from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

_RUNTIME_COLUMNS = {
    "strategy_profiles": {
        "source_suggestion_id": "VARCHAR(36)",
        "parent_profile_id": "VARCHAR(36)",
        "activated_at": "DATETIME",
        "retired_at": "DATETIME",
    },
    "strategy_suggestions": {
        "draft_profile_id": "VARCHAR(36)",
        "activated_profile_id": "VARCHAR(36)",
        "evaluation_id": "VARCHAR(36)",
        "decided_at": "DATETIME",
    },
    "strategy_evaluations": {
        "strategy_profile_id": "VARCHAR(36)",
        "suggestion_id": "VARCHAR(36)",
        "window_start": "DATETIME",
        "window_end": "DATETIME",
    },
}


def ensure_runtime_schema(engine: Engine) -> None:
    """为已有本地数据库补齐新增列；新库由 create_all 直接创建完整表。"""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _RUNTIME_COLUMNS.items():
            if table not in tables:
                continue
            existing = {item["name"] for item in inspect(engine).get_columns(table)}
            for name, kind in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {kind}"))
