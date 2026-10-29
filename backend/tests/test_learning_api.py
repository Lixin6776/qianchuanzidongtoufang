from app.models import StrategySuggestion


def test_learning_suggestion_api_returns_proposed_only(client, profile, db_session):
    db_session.add(
        StrategySuggestion(
            id="s1",
            strategy_profile_version=profile.version,
            suggestion_type="threshold_adjustment",
            proposed_change={"roi_floor_delta": 0.1},
            evidence={"sample_size": 24},
            confidence="high",
            status="proposed",
        )
    )
    db_session.commit()
    response = client.get("/api/learning/suggestions")
    assert response.status_code == 200
    assert all(item["status"] == "proposed" for item in response.json())


def test_rejecting_suggestion_remembers_reason(client, profile, db_session):
    suggestion = StrategySuggestion(
        id="s2",
        strategy_profile_version=profile.version,
        suggestion_type="threshold_adjustment",
        proposed_change={"roi_floor_delta": 0.1},
        evidence={"sample_size": 24},
        confidence="high",
        status="proposed",
    )
    db_session.add(suggestion)
    db_session.commit()
    response = client.post("/api/learning/suggestions/s2/reject", json={"reason": "样本不足"})
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["evidence"]["rejection_reason"] == "样本不足"

def test_chat_can_include_learning_context(client, profile, db_session):
    from app.api.chat import get_llm_provider
    from app.main import app
    from app.services.llm.base import LLMMessage, LLMResponse

    captured: list[LLMMessage] = []

    class CapturingProvider:
        async def complete(self, messages, tools):
            captured.extend(messages)
            return LLMResponse(content='{"kind":"analysis","message":"已结合学习记录。"}')

    app.dependency_overrides[get_llm_provider] = lambda: CapturingProvider()
    response = client.post(
        "/api/chat",
        json={"message": "为什么需要学习记录", "include_learning_context": True},
    )
    assert response.status_code == 200
    assert any("learning_context" in message.content for message in captured)

def test_accept_suggestion_creates_inactive_draft_with_adjustment(client, profile, db_session):
    from app.models import StrategyProfile

    suggestion = StrategySuggestion(
        id="s3",
        strategy_profile_version=profile.version,
        suggestion_type="threshold_adjustment",
        proposed_change={"roi_floor_delta": 0.1},
        evidence={"sample_size": 24},
        confidence="high",
        status="proposed",
    )
    db_session.add(suggestion)
    db_session.commit()
    response = client.post("/api/learning/suggestions/s3/accept")
    assert response.status_code == 200
    draft = db_session.query(StrategyProfile).filter_by(version=profile.version + 1).one()
    assert draft.active is False
    assert draft.hard_constraints["learning_adjustments"] == {"roi_floor_delta": 0.1}


def test_suggestion_can_activate_and_rollback_to_parent_profile(client, profile, db_session):
    from app.models import StrategyProfile

    suggestion = StrategySuggestion(
        id="s4",
        strategy_profile_version=profile.version,
        suggestion_type="threshold_adjustment",
        proposed_change={"roi_floor_delta": 0.1},
        evidence={"sample_size": 24},
        confidence="high",
        status="proposed",
    )
    db_session.add(suggestion)
    db_session.commit()

    accepted = client.post("/api/learning/suggestions/s4/accept")
    assert accepted.status_code == 200
    draft_id = accepted.json()["draft_profile_id"]

    activated = client.post("/api/learning/suggestions/s4/activate")
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"
    draft = db_session.get(StrategyProfile, draft_id)
    assert draft.active is True
    assert draft.parent_profile_id == profile.id

    rolled_back = client.post(
        "/api/learning/suggestions/s4/rollback",
        json={"reason": "新版本观察期 ROI 下降"},
    )
    assert rolled_back.status_code == 200
    assert rolled_back.json()["status"] == "rolled_back"
    db_session.expire_all()
    active = db_session.query(StrategyProfile).filter_by(active=True).one()
    assert active.id == profile.id
    assert db_session.get(StrategySuggestion, "s4").evidence["rollback_reason"] == "新版本观察期 ROI 下降"


def test_evaluate_endpoint_marks_insufficient_and_blocks_keep(client, profile, db_session, monkeypatch):
    from app.main import app
    from app.models import StrategyEvaluation, StrategySuggestion

    suggestion = StrategySuggestion(
        id="s5",
        strategy_profile_version=profile.version,
        suggestion_type="threshold_adjustment",
        proposed_change={"roi_floor_delta": 0.1},
        evidence={"sample_size": 24},
        confidence="high",
        status="proposed",
    )
    db_session.add(suggestion)
    db_session.commit()
    client.post("/api/learning/suggestions/s5/accept")
    client.post("/api/learning/suggestions/s5/activate")
    monkeypatch.setattr(
        app.state.live_watch_service.store,
        "list_analysis_logs",
        lambda limit=20000: [],
    )

    evaluated = client.post("/api/learning/suggestions/s5/evaluate")
    assert evaluated.status_code == 200
    assert evaluated.json()["verdict"] == "insufficient_data"
    db_session.expire_all()
    stored = db_session.get(StrategySuggestion, "s5")
    assert stored.status == "evaluated"
    assert stored.evaluation_id is not None
    assert db_session.get(StrategyEvaluation, stored.evaluation_id) is not None

    kept = client.post("/api/learning/suggestions/s5/keep", json={"reason": "观察期数据不足"})
    assert kept.status_code == 409
    assert "样本不足" in kept.json()["detail"]


def test_keep_requires_actionable_evaluation(client, profile, db_session):
    from app.models import StrategyEvaluation, StrategySuggestion

    suggestion = StrategySuggestion(
        id="s6",
        strategy_profile_version=profile.version,
        suggestion_type="threshold_adjustment",
        proposed_change={"roi_floor_delta": 0.1},
        evidence={"sample_size": 24},
        confidence="high",
        status="evaluated",
        evaluation_id="eval-ok",
    )
    evaluation = StrategyEvaluation(
        id="eval-ok",
        sample_size=24,
        effect_size=0.3,
        confidence="high",
        verdict="positive",
        evidence={"observation_only": True},
    )
    db_session.add_all([suggestion, evaluation])
    db_session.commit()

    kept = client.post("/api/learning/suggestions/s6/keep", json={"reason": "观察期正向"})
    assert kept.status_code == 200
    assert kept.json()["status"] == "kept"
