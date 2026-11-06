from datetime import UTC, datetime, timedelta

from app.services.analytics import ComputedMetrics
from app.services.live_watch import build_watch_report
from app.services.monitor import MonitorEvent

START = datetime(2026, 10, 11, 6, 0, tzinfo=UTC)
OLD = START - timedelta(days=1)


def _event(*, started=START, freshness="fresh", roi=1.8, gpm=2000.0):
    return MonitorEvent(
        captured_at=START + timedelta(minutes=15),
        freshness=freshness,
        banner="",
        level="normal",
        reason="指标正常",
        profile_version=1,
        metrics=ComputedMetrics(
            roi=roi,
            gpm=gpm,
            spend=10000.0,
            gmv=18000.0,
            orders=50,
            online_viewers=30,
            views=5000,
            exposure_count=100000,
        ),
        plan_status="active",
        plan_budget=0.0,
        source="cdp",
        spend_delta=120.0,
        minutes_since_previous=5.0,
        live_started_at=started,
    )


def _history_rows():
    return [
        {
            "source": "cdp",
            "created_at": (START - timedelta(minutes=5)).isoformat(),
            "captured_at": (START - timedelta(minutes=5)).isoformat(),
            "live_started_at": START.isoformat(),
            "session_status": "active",
            "online_viewers": 20,
        },
        {
            "source": "cdp",
            "created_at": START.isoformat(),
            "captured_at": START.isoformat(),
            "live_started_at": START.isoformat(),
            "session_status": "active",
            "online_viewers": 40,
        },
        {
            "source": "cdp",
            "created_at": (OLD + timedelta(minutes=5)).isoformat(),
            "captured_at": (OLD + timedelta(minutes=5)).isoformat(),
            "live_started_at": OLD.isoformat(),
            "session_status": "ended",
            "online_viewers": 1000,
        },
    ]


def test_average_online_uses_only_current_session_samples():
    report = build_watch_report(_event(), _history_rows(), 2.8, [])

    quality = report["data_quality"]
    assert report["average_online_viewers"] == 30.0
    assert report["online_samples"] == 3
    assert quality["session_confirmed"] is True
    assert quality["status"] == "good"
    assert "平均在线人数（本场）" in report["report_markdown"]
    assert "30（n=3）" in report["report_markdown"]
    assert "1000" not in report["report_markdown"]


def test_average_online_is_not_fabricated_without_session_start():
    report = build_watch_report(_event(started=None), [], 2.8, [])

    quality = report["data_quality"]
    assert report["average_online_viewers"] is None
    assert report["online_samples"] == 0
    assert quality["session_confirmed"] is False
    assert quality["status"] == "unconfirmed"
    assert any("场次" in issue for issue in quality["issues"])


def test_stale_snapshot_is_explicitly_downgraded():
    report = build_watch_report(_event(freshness="stale"), _history_rows(), 2.8, [])

    quality = report["data_quality"]
    assert quality["freshness"] == "stale"
    assert quality["status"] == "stale"
    assert any("新鲜度" in issue for issue in quality["issues"])


def test_missing_core_fields_are_listed_in_quality_metadata():
    report = build_watch_report(_event(roi=None, gpm=None), _history_rows(), 2.8, [])

    quality = report["data_quality"]
    assert quality["status"] == "partial"
    assert "综合营销 ROI" in quality["missing_fields"]
    assert "GPM" in quality["missing_fields"]
    assert quality["fields_present"] < quality["fields_total"]

def test_confirmed_session_without_samples_is_partial_not_unconfirmed():
    event = _event().model_copy(update={"plan_status": "ended"})
    report = build_watch_report(event, [], 2.8, [], online_history=[])

    quality = report["data_quality"]
    assert quality["session_confirmed"] is True
    assert quality["status"] == "partial"
    assert "本场暂无有效样本" in report["report_markdown"]
    assert "场次未确认" not in report["report_markdown"]

def test_average_online_rejects_same_start_time_from_another_room():
    event = _event()
    event.metrics.room_name = "直播间 A"
    event.metrics.live_room_id = "room-a"
    history = [
        {
            "source": "cdp",
            "captured_at": START.isoformat(),
            "live_started_at": START.isoformat(),
            "session_status": "active",
            "room_name": "直播间 B",
            "live_room_id": "room-b",
            "online_viewers": 1000,
        },
        {
            "source": "cdp",
            "captured_at": START.isoformat(),
            "live_started_at": START.isoformat(),
            "session_status": "active",
            "room_name": "直播间 A",
            "live_room_id": "room-a",
            "online_viewers": 10,
        },
    ]

    report = build_watch_report(event, history, 2.8, [])

    assert report["average_online_viewers"] == 20.0
    assert report["online_samples"] == 2
