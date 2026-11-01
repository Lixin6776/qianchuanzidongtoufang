import pytest

from app.models import StrategyEvaluation
from app.services.suggestions import SuggestionEngine


@pytest.fixture
def low_confidence_evaluation():
    return StrategyEvaluation(
        id="eval-low",
        sample_size=3,
        effect_size=0.2,
        confidence="low",
        verdict="insufficient_data",
        evidence={"counterexamples": 1},
    )


@pytest.fixture
def strong_evaluation():
    return StrategyEvaluation(
        id="eval-strong",
        sample_size=24,
        effect_size=0.4,
        confidence="high",
        verdict="beneficial",
        evidence={"counterexamples": 3, "case_ids": ["a", "b"]},
    )


def test_low_confidence_does_not_create_suggestion(low_confidence_evaluation, profile):
    suggestion = SuggestionEngine().propose(low_confidence_evaluation, [], profile)
    assert suggestion is None


def test_strong_evidence_creates_proposed_change(strong_evaluation, profile):
    suggestion = SuggestionEngine().propose(strong_evaluation, [], profile)
    assert suggestion is not None
    assert suggestion.status == "proposed"
    assert suggestion.proposed_change
    assert suggestion.evidence["sample_size"] >= 20

def test_operation_outcome_generates_evaluation_and_suggestion(db_session, profile):
    from app.models import StrategyEvaluation, StrategySuggestion

    result = SuggestionEngine(db_session).propose_from_outcome(
        {
            "operations": [
                {
                    "operation": "一键起量",
                    "n": 29,
                    "median_delta": 0.53,
                    "net_effect": 0.51,
                    "positive_rate": 0.76,
                    "verdict": "positive",
                },
                {
                    "operation": "抢首屏",
                    "n": 6,
                    "net_effect": -0.2,
                    "verdict": "insufficient",
                },
            ]
        },
        profile,
    )

    assert len(result) == 1
    suggestion = result[0]
    assert suggestion.status == "proposed"
    assert suggestion.evidence["source"] == "ops_outcome"
    assert suggestion.evidence["operation"] == "一键起量"
    assert suggestion.proposed_change["direction"] == "prefer"
    evaluation = db_session.get(StrategyEvaluation, suggestion.evidence["evaluation_id"])
    assert evaluation is not None
    assert evaluation.verdict == "positive"
    assert evaluation.effect_size == 0.51
    assert db_session.query(StrategySuggestion).count() == 1
