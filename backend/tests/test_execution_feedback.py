from datetime import UTC, datetime

from app.models import DecisionOutcome, ExecutionJob, LearningCase
from app.services.execution_feedback import ExecutionFeedbackService


def test_execution_feedback_contains_job_and_candidate_platform_link(db_session):
    job = ExecutionJob(
        id="j1",
        confirmation_id="c1",
        action_name="pause_plan",
        status="succeeded",
        created_at=datetime(2026, 10, 29, 10, 0, tzinfo=UTC),
        started_at=datetime(2026, 10, 29, 10, 0, tzinfo=UTC),
        finished_at=datetime(2026, 10, 29, 10, 1, tzinfo=UTC),
        result={"before": {"status": "active"}, "after": {"status": "paused"}},
    )
    case = LearningCase(
        id="case-1",
        strategy_profile_version=1,
        execution_job_id="j1",
        confirmation_id="c1",
        action_name="pause_plan",
        context={"before": {"status": "active"}, "after": {"status": "paused"}},
    )
    outcome = DecisionOutcome(
        id="outcome-1",
        case_id="case-1",
        metric_window="30m",
        metrics={"roi_delta": -0.2},
    )
    db_session.add_all([job, case, outcome])
    db_session.commit()

    rows = ExecutionFeedbackService(db_session).list_cases(
        [
            {
                "at": "2026-10-29 10:04",
                "operation": "暂停追投",
                "verdict": "negative",
                "delta_10m": -0.2,
            }
        ]
    )

    assert len(rows) == 1
    assert rows[0]["execution_job_id"] == "j1"
    assert rows[0]["confirmation_id"] == "c1"
    assert rows[0]["status"] == "succeeded"
    assert rows[0]["link_status"] == "candidate"
    assert rows[0]["linked_operation"]["operation"] == "暂停追投"
    assert rows[0]["outcome"]["roi_delta"] == -0.2


def test_failed_execution_is_returned_without_fake_outcome(db_session):
    job = ExecutionJob(
        id="j2",
        confirmation_id="c2",
        action_name="update_plan_budget",
        status="failed",
        created_at=datetime(2026, 10, 29, 10, 0, tzinfo=UTC),
        result={},
    )
    db_session.add(job)
    db_session.commit()

    rows = ExecutionFeedbackService(db_session).list_cases([])
    assert rows[0]["status"] == "failed"
    assert rows[0]["outcome"] is None
    assert rows[0]["link_status"] == "unlinked"
