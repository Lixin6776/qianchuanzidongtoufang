import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StrategyEvaluation, StrategyProfile, StrategySuggestion


class SuggestionEngine:
    def __init__(self, session: Session | None = None) -> None:
        self.session = session

    def propose(
        self,
        evaluation: StrategyEvaluation,
        matches: list,
        profile: StrategyProfile,
    ) -> StrategySuggestion | None:
        if evaluation.confidence == "low" or evaluation.sample_size < 20:
            return None
        if evaluation.verdict not in {"beneficial", "harmful"}:
            return None
        effect = float(evaluation.effect_size or 0)
        if evaluation.verdict == "beneficial":
            suggestion_type = "threshold_adjustment"
            proposed_change = {
                "primary_objective": profile.primary_objective,
                "roi_floor_delta": round(max(effect * 0.25, 0.05), 2),
            }
        else:
            suggestion_type = "action_priority"
            proposed_change = {
                "primary_objective": profile.primary_objective,
                "de_prioritize_action": "pause_plan",
            }
        suggestion = StrategySuggestion(
            id=str(uuid.uuid4()),
            strategy_profile_version=profile.version,
            suggestion_type=suggestion_type,
            proposed_change=proposed_change,
            evidence={
                "sample_size": evaluation.sample_size,
                "effect_size": evaluation.effect_size,
                "confidence": evaluation.confidence,
                "counterexamples": evaluation.evidence.get("counterexamples", 0),
                "similar_cases": len(matches),
            },
            confidence=evaluation.confidence,
            status="proposed",
            created_at=datetime.now(UTC),
        )
        if self.session is not None:
            self.session.add(suggestion)
            self.session.commit()
            self.session.refresh(suggestion)
        return suggestion
    def propose_from_outcome(
        self,
        outcome: dict,
        profile: StrategyProfile,
    ) -> list[StrategySuggestion]:
        """把操作净效应转换成可进入生命周期管理的策略建议。"""
        if self.session is None:
            return []
        existing = list(
            self.session.scalars(
                select(StrategySuggestion).where(
                    StrategySuggestion.strategy_profile_version == profile.version
                )
            )
        )
        blocked = {
            (item.evidence or {}).get("operation")
            for item in existing
            if (item.evidence or {}).get("source") == "ops_outcome"
            and item.status in {"proposed", "accepted", "active", "evaluated", "kept"}
        }
        created: list[StrategySuggestion] = []
        for row in outcome.get("operations", []):
            operation = str(row.get("operation") or "")
            verdict = str(row.get("verdict") or "")
            sample_size = int(row.get("n") or 0)
            if not operation or sample_size < 20:
                continue
            if verdict in {"positive", "beneficial"}:
                direction = "prefer"
            elif verdict in {"negative", "harmful"}:
                direction = "de_prioritize"
            else:
                continue
            if operation in blocked:
                continue
            effect = float(row.get("net_effect") or 0)
            evaluation = StrategyEvaluation(
                id=str(uuid.uuid4()),
                case_id=None,
                strategy_profile_id=profile.id,
                sample_size=sample_size,
                effect_size=round(effect, 4),
                confidence="high",
                verdict=verdict,
                evidence={
                    "source": "ops_outcome",
                    "operation": operation,
                    "median_delta": row.get("median_delta"),
                    "positive_rate": row.get("positive_rate"),
                    "observation_only": True,
                },
                created_at=datetime.now(UTC),
            )
            self.session.add(evaluation)
            self.session.flush()
            suggestion = StrategySuggestion(
                id=str(uuid.uuid4()),
                strategy_profile_version=profile.version,
                suggestion_type="action_priority",
                proposed_change={
                    "operation": operation,
                    "direction": direction,
                    "sample_size": sample_size,
                    "net_effect": round(effect, 4),
                },
                evidence={
                    "source": "ops_outcome",
                    "operation": operation,
                    "sample_size": sample_size,
                    "effect_size": round(effect, 4),
                    "counterexamples": None,
                    "evaluation_id": evaluation.id,
                    "observation_only": True,
                },
                confidence="high",
                status="proposed",
                created_at=datetime.now(UTC),
            )
            self.session.add(suggestion)
            created.append(suggestion)
            blocked.add(operation)
        self.session.commit()
        for item in created:
            self.session.refresh(item)
        return created
