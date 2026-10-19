# -*- coding: utf-8 -*-
"""操作净效应 API。"""

from fastapi import APIRouter, Request

from app.services.ops_outcome import (
    AssetSnapshotStore,
    compute_asset_overview,
    compute_ops_outcome,
)

router = APIRouter(prefix="/api/ops-outcome", tags=["ops-outcome"])


@router.get("")
def ops_outcome(request: Request, limit: int = 1500) -> dict:
    """算《操作反馈表》：哪些操作被数据正向反馈（观察性相关，非因果）。"""
    logs = request.app.state.live_watch_service.store.list_logs(limit=limit)
    return compute_ops_outcome(logs)


@router.get("/snapshots")
def ops_outcome_snapshots() -> list[dict]:
    """数据资产的历史快照（每天一份）。"""
    return AssetSnapshotStore().list()


@router.get("/overview")
def ops_outcome_overview(request: Request) -> dict:
    """数据资产概览：资产有多厚、结论几条、最近 24h 数据健不健康。"""
    state = request.app.state
    logs = state.live_watch_service.store.list_logs(limit=20000)
    reviews = 0
    analyses = 0
    try:
        reviews = len(state.live_review_store.list_reviews())
    except Exception:  # noqa: BLE001
        pass
    try:
        analyses = len(state.material_analysis_store.list_analyses())
    except Exception:  # noqa: BLE001
        pass
    return compute_asset_overview(logs, reviews=reviews, analyses=analyses)
