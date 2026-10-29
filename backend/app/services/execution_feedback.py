from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DecisionOutcome, ExecutionJob, LearningCase

_ACTION_HINTS = {
    "pause_plan": ("暂停",),
    "enable_plan": ("开启",),
    "update_plan_budget": ("预算", "加追投", "降追投"),
    "update_plan_bid": ("出价",),
    "update_plan_roi": ("ROI目标",),
    "bind_existing_material": ("加素材",),
    "unbind_existing_material": ("删素材",),
    "create_plan": ("新建",),
    "copy_plan": ("新建",),
}


def _timestamp(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _action_matches(action_name: str, operation: str) -> bool:
    hints = _ACTION_HINTS.get(action_name, ())
    return not hints or any(hint in operation for hint in hints)


def _best_platform_case(job: ExecutionJob, platform_cases: list[dict]) -> tuple[dict | None, str]:
    job_at = _timestamp(job.created_at.isoformat())
    if job_at is None:
        return None, "unlinked"
    best: dict | None = None
    best_gap = 16 * 60
    for case in platform_cases:
        case_at = _timestamp(str(case.get("at") or "").replace(" ", "T"))
        if case_at is None or not _action_matches(job.action_name, str(case.get("operation") or "")):
            continue
        gap = abs((case_at - job_at).total_seconds())
        if gap < best_gap:
            best, best_gap = case, gap
    if best is None:
        return None, "unlinked"
    exact = (
        best.get("execution_job_id") == job.id
        or best.get("confirmation_id") == job.confirmation_id
    )
    return best, "linked" if exact else "candidate"


class ExecutionFeedbackService:
    """把工具执行任务、学习案例和平台操作流水放在同一张回执里。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_cases(self, platform_cases: list[dict] | None = None) -> list[dict]:
        platform_cases = platform_cases or []
        jobs = list(
            self.session.scalars(
                select(ExecutionJob).order_by(ExecutionJob.created_at.desc())
            )
        )
        cases = list(self.session.scalars(select(LearningCase)))
        case_by_job = {case.execution_job_id: case for case in cases if case.execution_job_id}
        outcomes = list(self.session.scalars(select(DecisionOutcome)))
        outcomes_by_case: dict[str, list[DecisionOutcome]] = {}
        for outcome in outcomes:
            outcomes_by_case.setdefault(outcome.case_id, []).append(outcome)

        rows: list[dict] = []
        for job in jobs:
            case = case_by_job.get(job.id)
            outcomes_for_case = outcomes_by_case.get(case.id, []) if case else []
            outcome = outcomes_for_case[0] if outcomes_for_case else None
            linked, link_status = _best_platform_case(job, platform_cases)
            before = (job.result or {}).get("before") or (case.context.get("before") if case else {})
            after = (job.result or {}).get("after") or (case.context.get("after") if case else {})
            rows.append(
                {
                    "source": "execution",
                    "execution_job_id": job.id,
                    "confirmation_id": job.confirmation_id,
                    "action_name": job.action_name,
                    "status": job.status,
                    "created_at": job.created_at.isoformat(),
                    "before": before or {},
                    "after": after or {},
                    "error": job.error,
                    "learning_case_id": case.id if case else None,
                    "outcome": outcome.metrics if outcome else None,
                    "platform_log_status": "待回流",
                    "link_status": link_status,
                    "linked_operation": (
                        {
                            "at": linked.get("at"),
                            "operation": linked.get("operation"),
                            "verdict": linked.get("verdict"),
                            "delta_10m": linked.get("delta_10m"),
                        }
                        if linked
                        else None
                    ),
                }
            )
        return rows
