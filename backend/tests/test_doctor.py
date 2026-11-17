from pathlib import Path

from app.services import doctor


def _base_context(db_session, tmp_path: Path) -> dict:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    return {
        "db": db_session,
        "frontend_dist": dist,
        "local_dir": tmp_path / ".local",
        "room_name": "质润官方旗舰店",
        "aavid": "1873104018827399",
        "cdp_status": {
            "connected": True,
            "qianchuan_pages": 2,
            "login_pages": 0,
            "error": None,
        },
        "api_configured": False,
        "knowledge": {"mode": "historical_average", "active_count": 0},
        "report_count": 3,
        "monitor_status": {"running": True, "desired_running": True, "interrupted": False},
        "llm_configured": True,
        "python_version": (3, 12, 8),
        "platform_name": "Windows-11",
        "app_version": "0.1.0",
    }


def test_doctor_blocks_missing_room_and_data_source(db_session, tmp_path):
    context = _base_context(db_session, tmp_path)
    context.update({"room_name": "", "aavid": "", "cdp_status": {"connected": False}})

    report = doctor.assess_deployment(**context)

    assert report["status"] == "blocked"
    checks = {item["key"]: item for item in report["checks"]}
    assert checks["configuration"]["status"] == "blocked"
    assert checks["data_source"]["status"] == "blocked"
    assert checks["data_source"]["action_target"] == "data_source"


def test_doctor_is_ready_when_required_setup_passes(db_session, tmp_path):
    report = doctor.assess_deployment(**_base_context(db_session, tmp_path))

    assert report["status"] in {"ready", "attention"}
    assert report["summary"]["blocked"] == 0
    checks = {item["key"]: item for item in report["checks"]}
    assert checks["runtime"]["status"] == "ok"
    assert checks["frontend"]["status"] == "ok"
    assert checks["storage"]["status"] == "ok"
    assert checks["database"]["status"] == "ok"
    assert checks["configuration"]["status"] == "ok"
    assert checks["data_source"]["status"] == "ok"


def test_doctor_masks_environment_and_never_returns_secret_fields(db_session, tmp_path):
    report = doctor.assess_deployment(**_base_context(db_session, tmp_path))

    serialized = str(report).lower()
    assert "access_token" not in serialized
    assert "app_secret" not in serialized
    assert "cookie" not in serialized
    assert report["environment"]["app_version"] == "0.1.0"
    assert report["environment"]["python"] == "3.12.8"


def test_doctor_api_returns_safe_diagnostic_report(client, monkeypatch):
    from app.api import system as system_api

    async def fake_probe(endpoint: str, timeout: float = 4.0) -> dict:
        return {
            "endpoint": endpoint,
            "connected": True,
            "qianchuan_pages": 1,
            "login_pages": 0,
            "error": None,
        }

    monkeypatch.setattr(system_api, "probe_cdp", fake_probe)
    monkeypatch.setattr(system_api.local_config, "room_name", lambda default="": "测试直播间")
    monkeypatch.setattr(system_api.local_config, "aavid", lambda default="": "1234567890")

    response = client.get("/api/system/doctor")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ready", "attention", "blocked"}
    assert payload["checks"]
    assert "generated_at" in payload
    assert "access_token" not in response.text.lower()
    assert "app_secret" not in response.text.lower()
