import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import OpsTaskCreate, OpsTaskRead, OpsTaskUpdate
from app.services.ops_tasks import OpsTaskService

router = APIRouter(prefix="/api/ops-tasks", tags=["ops-tasks"])


@router.get("", response_model=list[OpsTaskRead])
def list_ops_tasks(db: Annotated[Session, Depends(get_db)]):
    return OpsTaskService(db).list()


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
