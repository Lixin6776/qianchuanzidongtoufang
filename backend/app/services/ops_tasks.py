from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OpsTask
from app.schemas import OpsTaskCreate, OpsTaskUpdate


class OpsTaskService:
    VALID_STATUSES: ClassVar[set[str]] = {"open", "in_progress", "done", "dismissed"}

    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[OpsTask]:
        return list(
            self.session.scalars(select(OpsTask).order_by(OpsTask.updated_at.desc()))
        )

    def create(self, payload: OpsTaskCreate) -> OpsTask:
        item = OpsTask(
            **payload.model_dump(exclude={"notify_feishu"}),
            status="open",
            result="",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item

    def get(self, task_id: str) -> OpsTask:
        item = self.session.get(OpsTask, task_id)
        if item is None:
            raise LookupError("Ops task not found")
        return item

    def update(self, task_id: str, payload: OpsTaskUpdate) -> OpsTask:
        item = self.get(task_id)
        changes = payload.model_dump(exclude_unset=True)
        if "status" in changes and changes["status"] not in self.VALID_STATUSES:
            raise ValueError("Invalid ops task status")
        for key, value in changes.items():
            setattr(item, key, value)
        item.updated_at = datetime.now(UTC)
        if changes.get("status") == "done":
            item.completed_at = datetime.now(UTC)
        elif changes.get("status") in {"open", "in_progress"}:
            item.completed_at = None
        self.session.commit()
        self.session.refresh(item)
        return item

    @staticmethod
    def format_feishu(item: OpsTask) -> tuple[str, str]:
        due = item.due_at.astimezone().strftime("%Y-%m-%d %H:%M") if item.due_at else "未设置"
        body = (
            f"- 负责人：{item.owner or '未分配'}\n"
            f"- 优先级：{item.priority}\n"
            f"- 截止时间：{due}\n"
            f"- 成功标准：{item.success_criteria or '未填写'}\n"
            f"- 止损条件：{item.stop_condition or '未填写'}\n"
            f"- 任务说明：{item.description or '无'}"
        )
        return (f"运营任务：{item.title}", body)
