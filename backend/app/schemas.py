from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StrategyProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    business_direction: str = Field(min_length=1, max_length=120)
    primary_objective: str = Field(min_length=1, max_length=500)
    secondary_objectives: list[str] = []
    hard_constraints: dict = {}
    monitoring_config: dict = {"interval_minutes": 5}
    allowed_actions: list[str] = []
    notification_policy: dict = {"dedupe_minutes": 10}


class StrategyProfileRead(StrategyProfileCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version: int
    active: bool
    source_suggestion_id: str | None = None
    parent_profile_id: str | None = None
    activated_at: datetime | None = None
    retired_at: datetime | None = None
    created_at: datetime
    effective_at: datetime

class PendingConfirmationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    recommendation_id: str | None
    action_name: str
    action_params: dict
    preview_hash: str
    strategy_profile_version: int
    idempotency_key: str
    status: str
    expires_at: datetime
    created_at: datetime
    claimed_at: datetime | None
    executed_at: datetime | None


class ExecutionJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    confirmation_id: str
    action_name: str
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    result: dict

class LearningCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    strategy_profile_version: int
    recommendation_id: str | None
    confirmation_id: str | None
    execution_job_id: str | None
    action_name: str
    context: dict
    status: str
    created_at: datetime


class DecisionOutcomeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    metric_window: str
    metrics: dict
    observed_at: datetime


class StrategyEvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str | None
    strategy_profile_id: str | None = None
    suggestion_id: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    sample_size: int
    effect_size: float | None
    confidence: str
    verdict: str
    evidence: dict
    created_at: datetime


class StrategySuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    strategy_profile_version: int
    suggestion_type: str
    proposed_change: dict
    evidence: dict
    confidence: str
    status: str
    draft_profile_id: str | None = None
    activated_profile_id: str | None = None
    evaluation_id: str | None = None
    decided_at: datetime | None = None
    created_at: datetime

class MaterialExperimentCreate(BaseModel):
    analysis_id: str
    analysis_date: str
    material_id: str
    material_name: str = ""
    action_type: str
    title: str
    reason: str = ""
    baseline_metrics: dict = {}
    success_criteria: dict = {}
    stop_condition: str = ""


class MaterialExperimentRead(MaterialExperimentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    execution_job_id: str | None = None
    observation_started_at: datetime | None = None
    observation_ends_at: datetime | None = None
    result: dict = {}
    created_at: datetime
    updated_at: datetime

class OpsTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str = ""
    source_type: str = "manual"
    source_id: str | None = None
    owner: str = ""
    priority: str = "medium"
    due_at: datetime | None = None
    success_criteria: str = ""
    stop_condition: str = ""
    notify_feishu: bool = False


class OpsTaskUpdate(BaseModel):
    owner: str | None = None
    priority: str | None = None
    due_at: datetime | None = None
    status: str | None = None
    success_criteria: str | None = None
    stop_condition: str | None = None
    result: str | None = None


class OpsTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    source_type: str
    source_id: str | None
    owner: str
    priority: str
    due_at: datetime | None
    status: str
    success_criteria: str
    stop_condition: str
    result: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
