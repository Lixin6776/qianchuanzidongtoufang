# -*- coding: utf-8 -*-
"""操作净效应 API。"""

import csv
import io

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.services.ops_outcome import (
    AssetSnapshotStore,
    compute_asset_overview,
    compute_op_cases,
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


@router.get("/cases")
def ops_outcome_cases(request: Request, limit: int = 200) -> list[dict]:
    """操作流水：每一笔操作 + 前后的边际 ROI（可追溯）。"""
    logs = request.app.state.live_watch_service.store.list_logs(limit=20000)
    return compute_op_cases(logs, limit=limit)


@router.get("/cases.csv")
def ops_outcome_cases_csv(request: Request, limit: int = 2000) -> StreamingResponse:
    """导出操作流水 CSV（备份 / 换电脑 / 发人）。"""
    logs = request.app.state.live_watch_service.store.list_logs(limit=20000)
    rows = compute_op_cases(logs, limit=limit)
    buffer = io.StringIO()
    buffer.write("\ufeff")  # Excel 识别 UTF-8
    writer = csv.writer(buffer)
    writer.writerow(
        ["时间", "操作", "素材名", "素材ID", "任务名", "操作前边际ROI", "10分后ROI", "20分后ROI", "10分Δ", "20分Δ", "判定", "原始记录"]
    )
    verdict_map = {"positive": "正向", "negative": "负向", "flat": "持平", "unknown": "无数据"}
    for row in rows:
        writer.writerow(
            [
                row["at"],
                row["operation"],
                row.get("material_name", ""),
                row.get("material_id", ""),
                row.get("task_name", ""),
                row["before_roi"],
                row["after_10m_roi"],
                row["after_20m_roi"],
                row["delta_10m"],
                row["delta_20m"],
                verdict_map.get(row["verdict"], row["verdict"]),
                row["summary"],
            ]
        )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=ops-cases.csv"},
    )
