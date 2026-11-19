
def test_account_history_api_bootstraps_and_returns_status(client, monkeypatch):
    from app.api import account_history as api

    record = {
        "account_id": "123",
        "room_name": "测试直播间",
        "source": "cdp",
        "range": {"start": "2026-09-20", "end": "2026-11-18", "days": 60},
        "imported_at": "2026-11-18T10:00:00+00:00",
        "summary": {"spend": 1000, "gmv": 2000, "orders": 10, "roi": 2.0},
        "daily": [],
        "quality": {"status": "good", "days_with_data": 30, "notes": []},
    }

    class FakeService:
        async def bootstrap(self, **kwargs):
            assert kwargs["account_id"] == "123"
            assert kwargs["force"] is True
            return {**record, "cache_hit": False}

    class FakeStore:
        def get(self, account_id):
            return record if account_id == "123" else None

    monkeypatch.setattr(api.local_config, "aavid", lambda default="": "123")
    monkeypatch.setattr(api.local_config, "room_name", lambda default="": "测试直播间")
    monkeypatch.setattr(api, "make_service", lambda: FakeService())
    monkeypatch.setattr(api, "AccountHistoryStore", lambda: FakeStore())

    response = client.post("/api/account-history/bootstrap?force=true")

    assert response.status_code == 200
    body = response.json()
    assert body["account_id"] == "123"
    assert body["source"] == "cdp"
    assert body["summary"]["roi"] == 2.0

    status = client.get("/api/account-history")
    assert status.status_code == 200
    assert status.json()["configured"] is True
    assert status.json()["history"]["account_id"] == "123"

import time


def test_bootstrap_start_returns_immediately_and_completes_asynchronously(client, monkeypatch):
    from app.api import account_history as api

    record = {
        "account_id": "123",
        "room_name": "测试直播间",
        "source": "cdp",
        "range": {"start": "2026-09-20", "end": "2026-11-18", "days": 60},
        "imported_at": "2026-11-19T10:00:00+00:00",
        "summary": {"spend": 1000, "gmv": 2000, "orders": 10, "roi": 2.0},
        "daily": [],
        "quality": {"status": "good", "days_with_data": 60, "notes": []},
    }

    class SlowService:
        async def bootstrap(self, **kwargs):
            import asyncio

            await asyncio.sleep(0.2)
            return {**record, "cache_hit": False}

    monkeypatch.setattr(api.local_config, "aavid", lambda default="": "123")
    monkeypatch.setattr(api.local_config, "room_name", lambda default="": "测试直播间")
    monkeypatch.setattr(api, "make_service", lambda: SlowService())
    api.reset_bootstrap_jobs_for_tests()

    started_at = time.perf_counter()
    response = client.post("/api/account-history/bootstrap/start?force=true")
    elapsed = time.perf_counter() - started_at

    assert response.status_code == 202
    job = response.json()
    assert job["status"] == "running"
    assert elapsed < 0.15

    deadline = time.perf_counter() + 3
    result = job
    while time.perf_counter() < deadline:
        result = client.get(f"/api/account-history/bootstrap/{job['id']}").json()
        if result["status"] != "running":
            break
        time.sleep(0.05)

    assert result["status"] == "completed"
    assert result["result"]["range"]["days"] == 60