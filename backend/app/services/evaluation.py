import statistics
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DecisionOutcome, StrategyEvaluation


class StrategyEvaluationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def evaluate(self, case_ids: list[str]) -> StrategyEvaluation:
        outcomes = list(
            self.session.scalars(
                select(DecisionOutcome).where(DecisionOutcome.case_id.in_(case_ids))
            )
        )
        deltas = [float(outcome.metrics.get("roi_delta", 0)) for outcome in outcomes]
        sample_size = len(deltas)
        mean_delta = statistics.mean(deltas) if deltas else 0
        median_delta = statistics.median(deltas) if deltas else 0
        variance = statistics.pvariance(deltas) if len(deltas) > 1 else 0
        counterexamples = sum(1 for value in deltas if value < 0)
        success_rate = sum(1 for value in deltas if value > 0) / sample_size if sample_size else 0

        if sample_size < 5:
            confidence = "low"
            verdict = "insufficient_data"
        else:
            confidence = "medium" if sample_size < 20 else "high"
            if mean_delta > 0.05:
                verdict = "beneficial"
            elif mean_delta < -0.05:
                verdict = "harmful"
            else:
                verdict = "neutral"

        evaluation = StrategyEvaluation(
            id=str(uuid.uuid4()),
            case_id=case_ids[0] if case_ids else None,
            sample_size=sample_size,
            effect_size=round(mean_delta, 10),
            confidence=confidence,
            verdict=verdict,
            evidence={
                "mean_roi_delta": round(mean_delta, 10),
                "median_roi_delta": round(median_delta, 10),
                "variance": round(variance, 10),
                "success_rate": round(success_rate, 10),
                "counterexamples": counterexamples,
                "case_ids": case_ids,
            },
            created_at=datetime.now(UTC),
        )
        self.session.add(evaluation)
        self.session.commit()
        self.session.refresh(evaluation)
        return evaluation

    def evaluate_watch_window(
        self,
        *,
        suggestion_id: str,
        strategy_profile_id: str,
        effective_at: datetime,
        logs: list[dict],
    ) -> StrategyEvaluation:
        """比较策略激活前后 60 分钟；只做观察，不宣称因果。"""
        if effective_at.tzinfo is None:
            effective_at = effective_at.replace(tzinfo=UTC)
        pre_start = effective_at - timedelta(minutes=60)
        post_end = effective_at + timedelta(minutes=60)

        def parse_at(value) -> datetime | None:
            try:
                parsed = datetime.fromisoformat(str(value))
            except (TypeError, ValueError):
                return None
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

        pre: list[dict] = []
        post: list[dict] = []
        for item in logs:
            if item.get("source") != "cdp":
                continue
            at = parse_at(item.get("created_at"))
            if at is None or item.get("roi") is None:
                continue
            if pre_start <= at < effective_at:
                pre.append(item)
            elif effective_at < at <= post_end:
                post.append(item)

        def median(items: list[dict], key: str) -> float | None:
            values = [float(item[key]) for item in items if item.get(key) is not None]
            return round(statistics.median(values), 4) if values else None

        sample_size = min(len(pre), len(post))
        pre_roi = median(pre, "roi")
        post_roi = median(post, "roi")
        effect_size = (
            round(post_roi - pre_roi, 4)
            if pre_roi is not None and post_roi is not None
            else None
        )
        if sample_size < 20 or effect_size is None:
            confidence = "low"
            verdict = "insufficient_data"
        else:
            confidence = "high"
            verdict = (
                "positive"
                if effect_size > 0.1
                else "negative"
                if effect_size < -0.1
                else "neutral"
            )

        target_values = [
            float(item["roi_target"])
            for item in pre + post
            if item.get("roi_target") is not None
        ]
        target_rate = None
        if target_values and pre_roi is not None and post_roi is not None:
            target = statistics.median(target_values)
            target_rate = {
                "before": round(sum(float(i["roi"]) >= target for i in pre) / len(pre), 4)
                if pre
                else None,
                "after": round(sum(float(i["roi"]) >= target for i in post) / len(post), 4)
                if post
                else None,
                "target": round(target, 4),
            }

        evaluation = StrategyEvaluation(
            id=str(uuid.uuid4()),
            case_id=None,
            strategy_profile_id=strategy_profile_id,
            suggestion_id=suggestion_id,
            window_start=pre_start,
            window_end=post_end,
            sample_size=sample_size,
            effect_size=effect_size,
            confidence=confidence,
            verdict=verdict,
            evidence={
                "pre": {
                    "n": len(pre),
                    "roi_median": pre_roi,
                    "gpm_median": median(pre, "gpm"),
                    "spend_median": median(pre, "spend"),
                },
                "post": {
                    "n": len(post),
                    "roi_median": post_roi,
                    "gpm_median": median(post, "gpm"),
                    "spend_median": median(post, "spend"),
                },
                "roi_target_rate": target_rate,
                "observation_only": True,
                "note": "观察性相关，不是因果；样本不足时不给方向。",
            },
            created_at=datetime.now(UTC),
        )
        self.session.add(evaluation)
        self.session.commit()
        self.session.refresh(evaluation)
        return evaluation
