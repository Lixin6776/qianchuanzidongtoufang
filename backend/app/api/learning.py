from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    LearningCase,
    StrategyEvaluation,
    StrategyProfile,
    StrategySuggestion,
)
from app.schemas import (
    LearningCaseRead,
    StrategyEvaluationRead,
    StrategySuggestionRead,
)
from app.services.evaluation import StrategyEvaluationService
from app.services.execution_feedback import ExecutionFeedbackService
from app.services.ops_outcome import compute_op_cases
from app.services.profiles import StrategyProfileService

router = APIRouter(prefix="/api/learning", tags=["learning"])


class SuggestionDecision(BaseModel):
    reason: str = ""


@router.get("/execution-cases")
def list_execution_cases(request: Request, db: Annotated[Session, Depends(get_db)]):
    logs = request.app.state.live_watch_service.store.list_analysis_logs(limit=20000)
    platform_cases = compute_op_cases(logs, limit=2000)
    return ExecutionFeedbackService(db).list_cases(platform_cases)


@router.get("/cases", response_model=list[LearningCaseRead])
def list_cases(db: Annotated[Session, Depends(get_db)]):
    return list(db.scalars(select(LearningCase).order_by(LearningCase.created_at.desc())))


@router.get("/cases/{case_id}", response_model=LearningCaseRead)
def get_case(case_id: str, db: Annotated[Session, Depends(get_db)]):
    case = db.get(LearningCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Learning case not found")
    return case


@router.get("/evaluations", response_model=list[StrategyEvaluationRead])
def list_evaluations(db: Annotated[Session, Depends(get_db)]):
    return list(
        db.scalars(select(StrategyEvaluation).order_by(StrategyEvaluation.created_at.desc()))
    )


@router.get("/suggestions", response_model=list[StrategySuggestionRead])
def list_suggestions(db: Annotated[Session, Depends(get_db)]):
    return list(
        db.scalars(select(StrategySuggestion).order_by(StrategySuggestion.created_at.desc()))
    )


@router.post("/suggestions/{suggestion_id}/accept", response_model=StrategySuggestionRead)
def accept_suggestion(
    suggestion_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    suggestion = db.get(StrategySuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    active = StrategyProfileService(db).get_active()
    draft = StrategyProfile(
        version=active.version + 1,
        name=f"{active.name} - learning draft",
        business_direction=active.business_direction,
        primary_objective=active.primary_objective,
        secondary_objectives=active.secondary_objectives,
        hard_constraints={
            **active.hard_constraints,
            "learning_adjustments": suggestion.proposed_change,
        },
        monitoring_config=active.monitoring_config,
        allowed_actions=active.allowed_actions,
        notification_policy=active.notification_policy,
        active=False,
        parent_profile_id=active.id,
        source_suggestion_id=suggestion.id,
    )
    db.add(draft)
    db.flush()
    suggestion.status = "accepted"
    suggestion.draft_profile_id = draft.id
    suggestion.decided_at = datetime.now(UTC)
    db.commit()
    db.refresh(suggestion)
    return suggestion


@router.post("/suggestions/{suggestion_id}/activate", response_model=StrategySuggestionRead)
def activate_suggestion(
    suggestion_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    suggestion = db.get(StrategySuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.status != "accepted" or not suggestion.draft_profile_id:
        raise HTTPException(status_code=409, detail="Suggestion has no accepted draft")
    draft = db.get(StrategyProfile, suggestion.draft_profile_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft profile not found")
    StrategyProfileService(db).activate(
        draft.id,
        source_suggestion_id=suggestion.id,
    )
    suggestion.status = "active"
    suggestion.activated_profile_id = draft.id
    suggestion.decided_at = datetime.now(UTC)
    db.commit()
    db.refresh(suggestion)
    return suggestion


@router.post(
    "/suggestions/{suggestion_id}/evaluate",
    response_model=StrategyEvaluationRead,
)
def evaluate_suggestion(
    suggestion_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    suggestion = db.get(StrategySuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.status not in {"active", "evaluated"} or not suggestion.activated_profile_id:
        raise HTTPException(status_code=409, detail="Suggestion has no active version to evaluate")
    profile = db.get(StrategyProfile, suggestion.activated_profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Activated profile not found")
    logs = request.app.state.live_watch_service.store.list_analysis_logs(limit=20000)
    evaluation = StrategyEvaluationService(db).evaluate_watch_window(
        suggestion_id=suggestion.id,
        strategy_profile_id=profile.id,
        effective_at=profile.activated_at or profile.effective_at,
        logs=logs,
    )
    suggestion.status = "evaluated"
    suggestion.evaluation_id = evaluation.id
    db.commit()
    return evaluation


@router.post("/suggestions/{suggestion_id}/rollback", response_model=StrategySuggestionRead)
def rollback_suggestion(
    suggestion_id: str,
    payload: SuggestionDecision,
    db: Annotated[Session, Depends(get_db)],
):
    suggestion = db.get(StrategySuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.status not in {"active", "evaluated"} or not suggestion.activated_profile_id:
        raise HTTPException(status_code=409, detail="Suggestion has no active version to roll back")
    active = db.get(StrategyProfile, suggestion.activated_profile_id)
    if active is None or not active.parent_profile_id:
        raise HTTPException(status_code=409, detail="Parent profile is unavailable")
    StrategyProfileService(db).activate(active.parent_profile_id)
    suggestion.status = "rolled_back"
    suggestion.decided_at = datetime.now(UTC)
    suggestion.evidence = {
        **suggestion.evidence,
        "rollback_reason": payload.reason,
    }
    db.commit()
    db.refresh(suggestion)
    return suggestion


@router.post("/suggestions/{suggestion_id}/keep", response_model=StrategySuggestionRead)
def keep_suggestion(
    suggestion_id: str,
    payload: SuggestionDecision,
    db: Annotated[Session, Depends(get_db)],
):
    suggestion = db.get(StrategySuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.status != "evaluated" or not suggestion.evaluation_id:
        raise HTTPException(status_code=409, detail="Suggestion has no evaluation to keep")
    evaluation = db.get(StrategyEvaluation, suggestion.evaluation_id)
    if evaluation is None or evaluation.verdict == "insufficient_data":
        raise HTTPException(status_code=409, detail="评估样本不足，不能保留策略")
    suggestion.status = "kept"
    suggestion.decided_at = datetime.now(UTC)
    suggestion.evidence = {
        **suggestion.evidence,
        "keep_reason": payload.reason,
    }
    db.commit()
    db.refresh(suggestion)
    return suggestion


@router.post("/suggestions/{suggestion_id}/reject", response_model=StrategySuggestionRead)
def reject_suggestion(
    suggestion_id: str,
    payload: SuggestionDecision,
    db: Annotated[Session, Depends(get_db)],
):
    suggestion = db.get(StrategySuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    suggestion.status = "rejected"
    suggestion.evidence = {**suggestion.evidence, "rejection_reason": payload.reason}
    db.commit()
    db.refresh(suggestion)
    return suggestion