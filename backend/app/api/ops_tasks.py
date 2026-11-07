import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import OpsTaskCreate, OpsTaskRead, OpsTaskUpdate
from app.services.decision_loop import compute_task_verification
from app.services.ops_tasks import OpsTaskService

router = APIRouter(prefix="/api/ops-tasks", tags=["ops-tasks"])


def _task_read(task, reports: list[dict]) -> OpsTaskRead:
    task.context = task.context or {}
    read = OpsTaskRead.model_validate(task)
    verification = None
    if task.source_type == "live_watch":
        verification = compute_task_verification(task, reports)
    return read.model_copy(update={"verification": verification})


@router.get("", response_model=list[OpsTaskRead])
def list_ops_tasks(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    service = OpsTaskService(db)
    reports = request.app.state.live_watch_service.store.list_logs(limit=5000)
    return [_task_read(task, reports) for task in service.list()]


@router.post("", response_model=OpsTaskRead, status_code=201)
async def create_ops_task(
    payload: OpsTaskCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    item = OpsTaskService(db).create(payload)
    if payload.notify_feishu:
        notifier = getattr(request.app.state, "feishu_notifier", None)
        if notifier is not None:
            title, body = OpsTaskService.format_feishu(item)
            try:
                await asyncio.to_thread(notifier.send_alert, title, body)
            except Exception:  # noqa: BLE001, S110
                pass
    return item


@router.post("/from-live-watch/{report_id}", response_model=OpsTaskRead, status_code=201)
def create_task_from_live_watch(
    report_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    priority_index: int = Query(default=0, ge=0),
):
    report = request.app.state.live_watch_service.store.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Live watch report not found")
    service = OpsTaskService(db)
    try:
        task = service.create_from_live_watch(report, priority_index)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    reports = request.app.state.live_watch_service.store.list_logs(limit=5000)
    return _task_read(task, reports)


@router.patch("/{task_id}", response_model=OpsTaskRead)
def update_ops_task(
    task_id: str,
    payload: OpsTaskUpdate,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        return OpsTaskService(db).update(task_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
