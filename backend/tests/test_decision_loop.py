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
    assert "ROI 回到目标" in payload.title
    assert payload.context["action_title"] == "收缩低效消耗，争取 ROI 回到目标"
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
    store.append(_multi_priority_report())
    client.app.state.live_watch_service.store = store

    first = client.post("/api/ops-tasks/from-live-watch/watch-1")
    second = client.post("/api/ops-tasks/from-live-watch/watch-1")
    p2 = client.post("/api/ops-tasks/from-live-watch/watch-1?priority_index=1")

    assert first.status_code == 201
    assert second.status_code == 201
    assert p2.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert p2.json()["id"] != first.json()["id"]
    assert p2.json()["context"]["priority_index"] == 1
    assert p2.json()["context"]["focus_metric"] == "gpm"
    assert first.json()["source_type"] == "live_watch"
    assert first.json()["context"]["baseline"]["roi"] == 2.0
    assert first.json()["verification"]["status"] == "pending"

    listed = client.get("/api/ops-tasks")
    assert listed.status_code == 200
    assert any(item["id"] == first.json()["id"] for item in listed.json())

def _multi_priority_report():
    report = _report()
    report.update(
        {
            "gpm": 3000.0,
            "cpm": 85.0,
            "spend_split": {"basic_spend": 60.0, "assist_spend": 40.0},
            "priority_actions": [
                {
                    "rank": 1,
                    "severity": "high",
                    "problem": "综合营销 ROI 未达标",
                    "action": "综合营销 ROI：先收缩低效素材",
                    "action_title": "收缩低效消耗，争取 ROI 回到目标",
                    "steps": ["收缩素材", "复核 ROI", "继续下降则回滚"],
                    "success_criteria": "ROI 改善 0.10",
                    "stop_condition": "ROI 继续下降时停止",
                    "verify_minutes": 10,
                },
                {
                    "rank": 2,
                    "severity": "medium",
                    "problem": "GPM 低于账户基线",
                    "action": "承接：检查话术并复核 GPM",
                    "action_title": "先修承接，再考虑加量",
                    "steps": ["检查话术", "复核 GPM", "承接未稳前不加量"],
                    "success_criteria": "GPM 提升 5%",
                    "stop_condition": "GPM 继续下降时停止",
                    "verify_minutes": 10,
                },
                {
                    "rank": 3,
                    "severity": "medium",
                    "problem": "追投占比偏高",
                    "action": "追投：下调追投预算",
                    "action_title": "下调追投占比，把量让给基础计划",
                    "steps": ["下调追投", "观察基础消耗", "复核占比"],
                    "success_criteria": "追投占比下降",
                    "stop_condition": "ROI 恶化时停止",
                    "verify_minutes": 10,
                },
            ],
        }
    )
    return report


def test_each_priority_builds_task_with_its_own_focus_metric():
    report = _multi_priority_report()

    gpm_task = build_live_watch_task(report, now=NOW, priority_index=1)
    assist_task = build_live_watch_task(report, now=NOW, priority_index=2)

    assert gpm_task.title == "执行：先修承接，再考虑加量"
    assert gpm_task.context["focus_metric"] == "gpm"
    assert gpm_task.context["priority_index"] == 1
    assert assist_task.title == "执行：下调追投占比，把量让给基础计划"
    assert assist_task.context["focus_metric"] == "assist_share"
    assert assist_task.context["priority_index"] == 2


def test_create_from_live_watch_is_idempotent_per_priority(db_session):
    service = OpsTaskService(db_session)
    report = _multi_priority_report()

    first = service.create_from_live_watch(report, priority_index=0)
    second = service.create_from_live_watch(report, priority_index=1)
    first_again = service.create_from_live_watch(report, priority_index=0)

    assert first.id != second.id
    assert first.id == first_again.id
    assert first.context["priority_index"] == 0
    assert second.context["priority_index"] == 1
