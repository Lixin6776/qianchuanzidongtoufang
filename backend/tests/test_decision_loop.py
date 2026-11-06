from datetime import UTC, datetime, timedelta

from app.schemas import OpsTaskCreate
from app.services.decision_loop import build_live_watch_task, compute_task_verification
from app.services.ops_tasks import OpsTaskService
from app.services.watch_log_store import SqliteWatchLogStore

NOW = datetime(2026, 11, 6, 8, 0, tzinfo=UTC)
SESSION = datetime(2026, 11, 6, 7, 0, tzinfo=UTC)


def _report(*, captured_at=NOW, roi=2.0, roi_target=2.5, adjustment="先收缩低效素材，10～20 分钟后复核 ROI"):
    return {
        "id": "watch-1",
        "created_at": captured_at.isoformat(),
        "captured_at": captured_at.isoformat(),
        "live_started_at": SESSION.isoformat(),
        "live_room_id": "room-1",
        "room_name": "直播间 A",
        "session_status": "active",
        "source": "cdp",
        "level": "watch",
        "roi": roi,
        "roi_target": roi_target,
        "spend": 10000.0,
        "gmv": 20000.0,
        "gpm": 2000.0,
        "spend_delta": 500.0,
        "online_viewers": 50,
        "average_online_viewers": 45.0,
        "online_samples": 8,
        "problems": ["综合营销 ROI 未达标：当前 2.00，目标 2.50"],
        "adjustments": [adjustment],
        "data_quality": {
            "status": "good",
            "label": "可信",
            "freshness": "fresh",
            "session_confirmed": True,
        },
    }


def _verification_report(minutes, *, roi, quality="good"):
    item = _report(captured_at=NOW + timedelta(minutes=minutes), roi=roi)
    item["data_quality"] = {**item["data_quality"], "status": quality}
    item["id"] = f"watch-{minutes}"
    return item


def test_build_live_watch_task_persists_action_baseline_and_guardrails():
    payload = build_live_watch_task(_report(), now=NOW)

    assert isinstance(payload, OpsTaskCreate)
    assert payload.source_type == "live_watch"
    assert payload.source_id == "watch-1"
    assert "收缩低效素材" in payload.title
    assert "10 分钟" in payload.success_criteria
    assert "数据质量" in payload.stop_condition
    assert payload.due_at == NOW + timedelta(minutes=10)
    assert payload.context["focus_metric"] == "roi"
    assert payload.context["baseline"]["roi"] == 2.0
    assert payload.context["verification_windows_minutes"] == [10, 30]


def test_create_from_live_watch_is_idempotent(db_session):
    service = OpsTaskService(db_session)

    first = service.create_from_live_watch(_report())
    second = service.create_from_live_watch(_report())

    assert first.id == second.id
    assert first.source_type == "live_watch"


def test_verification_compares_10_and_30_minute_reports():
    payload = build_live_watch_task(_report(), now=NOW)
    task = OpsTaskService.create_model(payload)
    task.created_at = NOW
    task.context = payload.context

    result = compute_task_verification(
        task,
        [_verification_report(10, roi=2.15), _verification_report(30, roi=2.2)],
        now=NOW + timedelta(minutes=31),
    )

    assert result["status"] == "ready"
    assert result["window_10m"]["delta"] == 0.15
    assert result["window_30m"]["delta"] == 0.2
    assert result["suggested_verdict"] == "success"
    assert "保留" in result["message"]


def test_verification_skips_reports_with_untrusted_data_quality():
    payload = build_live_watch_task(_report(), now=NOW)
    task = OpsTaskService.create_model(payload)
    task.created_at = NOW
    task.context = payload.context

    result = compute_task_verification(
        task,
        [_verification_report(10, roi=2.2, quality="stale")],
        now=NOW + timedelta(minutes=12),
    )

    assert result["status"] == "insufficient_data"
    assert result["suggested_verdict"] == "insufficient_data"
    assert result["window_10m"] is None

def test_api_creates_one_task_from_current_report_and_returns_pending_verification(
    client, tmp_path
):
    store = SqliteWatchLogStore(tmp_path / "decision-loop.sqlite3", tmp_path / "none.json")
    store.append(_report())
    client.app.state.live_watch_service.store = store

    first = client.post("/api/ops-tasks/from-live-watch/watch-1")
    second = client.post("/api/ops-tasks/from-live-watch/watch-1")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["source_type"] == "live_watch"
    assert first.json()["context"]["baseline"]["roi"] == 2.0
    assert first.json()["verification"]["status"] == "pending"

    listed = client.get("/api/ops-tasks")
    assert listed.status_code == 200
    assert any(item["id"] == first.json()["id"] for item in listed.json())
