import pytest

from app.models import DecisionOutcome, LearningCase
from app.services.evaluation import StrategyEvaluationService


@pytest.fixture
def low_sample_cases(db_session):
    cases = []
    for index in range(3):
        case = LearningCase(
            id=f"case-{index}",
            strategy_profile_version=1,
            action_name="pause_plan",
            context={},
            status="observed",
        )
        outcome = DecisionOutcome(
            id=f"outcome-{index}",
            case_id=case.id,
            metric_window="30m",
            metrics={"roi_delta": 0.2},
        )
        db_session.add_all([case, outcome])
        cases.append(case)
    db_session.commit()
    return cases


def test_small_sample_never_has_high_confidence(db_session, low_sample_cases):
    service = StrategyEvaluationService(db_session)
    evaluation = service.evaluate([case.id for case in low_sample_cases])
    assert evaluation.sample_size < 5
    assert evaluation.confidence == "low"
    assert evaluation.verdict == "insufficient_data"

def test_watch_window_evaluation_requires_both_windows(db_session):
    from datetime import UTC, datetime, timedelta

    from app.services.evaluation import StrategyEvaluationService

    activation = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)
    logs = []
    for i in range(24):
        pre = activation - timedelta(minutes=30 - i)
        post = activation + timedelta(minutes=i + 1)
        logs.append({"source": "cdp", "created_at": pre.isoformat(), "roi": 1.5, "gpm": 2000 + i, "spend": 1000 + i, "roi_target": 2.5})
        logs.append({"source": "cdp", "created_at": post.isoformat(), "roi": 2.0, "gpm": 2200 + i, "spend": 1200 + i, "roi_target": 2.5})

    result = StrategyEvaluationService(db_session).evaluate_watch_window(
        suggestion_id="s1",
        strategy_profile_id="p1",
        effective_at=activation,
        logs=logs,
    )
    assert result.suggestion_id == "s1"
    assert result.strategy_profile_id == "p1"
    assert result.sample_size >= 20
    assert result.verdict == "positive"
    assert result.effect_size == 0.5
    assert result.evidence["observation_only"] is True


def test_watch_window_evaluation_marks_insufficient_sample(db_session):
    from datetime import UTC, datetime

    from app.services.evaluation import StrategyEvaluationService

    activation = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)
    result = StrategyEvaluationService(db_session).evaluate_watch_window(
        suggestion_id="s2",
        strategy_profile_id="p2",
        effective_at=activation,
        logs=[{"source": "cdp", "created_at": activation.isoformat(), "roi": 2.0}],
    )
    assert result.verdict == "insufficient_data"
    assert result.confidence == "low"
