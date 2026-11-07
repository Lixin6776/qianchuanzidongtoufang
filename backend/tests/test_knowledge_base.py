import base64
from datetime import UTC, datetime, timedelta

from app.api import knowledge_base as knowledge_api
from app.services.knowledge_base import KnowledgeBaseStore


def test_text_knowledge_file_is_saved_and_available_as_excerpt(tmp_path):
    store = KnowledgeBaseStore(tmp_path / "knowledge")

    item = store.save_file(
        "投手规则.md",
        "高消耗低效素材先核对是否持续多天低跑量".encode(),
        "text/markdown",
    )

    assert item["name"] == "投手规则.md"
    assert item["parse_status"] == "parsed"
    assert "持续多天低跑量" in item["preview"]
    assert store.list_files()[0]["id"] == item["id"]
    assert "高消耗低效素材" in store.knowledge_excerpt()


def test_no_uploaded_files_uses_historical_average_only(tmp_path):
    store = KnowledgeBaseStore(tmp_path / "knowledge")
    now = datetime(2026, 11, 6, 8, 0, tzinfo=UTC)
    reports = [
        {
            "id": "r1",
            "created_at": now.isoformat(),
            "source": "cdp",
            "verify_passed": True,
            "roi": 2.0,
            "gpm": 3000,
            "cpm": 80,
            "exposure_view_rate": 4.0,
            "view_conversion_rate": 5.0,
            "online_viewers": 40,
            "spend_split": {"basic_spend": 70, "assist_spend": 30},
            "data_quality": {"status": "good"},
        },
        {
            "id": "r2",
            "created_at": (now + timedelta(minutes=5)).isoformat(),
            "source": "cdp",
            "verify_passed": True,
            "roi": 4.0,
            "gpm": 5000,
            "cpm": 100,
            "exposure_view_rate": 6.0,
            "view_conversion_rate": 7.0,
            "online_viewers": 60,
            "spend_split": {"basic_spend": 50, "assist_spend": 50},
            "data_quality": {"status": "good"},
        },
        {
            "id": "bad-source",
            "created_at": (now + timedelta(minutes=10)).isoformat(),
            "source": "cdp-error",
            "roi": 100,
            "data_quality": {"status": "invalid"},
        },
        {
            "id": "bad-quality",
            "created_at": (now + timedelta(minutes=15)).isoformat(),
            "source": "cdp",
            "roi": 200,
            "data_quality": {"status": "stale"},
        },
    ]

    overview = store.overview(reports)

    assert overview["mode"] == "historical_average"
    assert overview["historical_reference"]["sample_count"] == 2
    metrics = {item["key"]: item for item in overview["historical_reference"]["metrics"]}
    assert metrics["roi"]["average"] == 3.0
    assert metrics["gpm"]["average"] == 4000.0
    assert metrics["assist_share"]["average"] == 40.0
    assert "仅作历史参考" in overview["historical_reference"]["note"]


def test_uploaded_file_takes_priority_over_historical_average(tmp_path):
    store = KnowledgeBaseStore(tmp_path / "knowledge")
    store.save_file("rules.txt", b"my rule", "text/plain")

    overview = store.overview([{"source": "cdp", "roi": 2.0}])

    assert overview["mode"] == "uploaded"
    assert overview["historical_reference"] is None
    assert overview["files"][0]["name"] == "rules.txt"

def test_knowledge_upload_api_accepts_base64_file(client, tmp_path, monkeypatch):
    store = KnowledgeBaseStore(tmp_path / "knowledge")
    monkeypatch.setattr(knowledge_api, "KnowledgeBaseStore", lambda: store)
    content = base64.b64encode("账户规则：ROI 低于目标先收缩".encode()).decode("ascii")

    response = client.post(
        "/api/knowledge-base/files",
        json={
            "name": "账户规则.md",
            "content_base64": content,
            "content_type": "text/markdown",
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "账户规则.md"
    assert response.json()["parse_status"] == "parsed"
    assert store.list_files()[0]["name"] == "账户规则.md"

def test_ops_assistant_prefers_uploaded_knowledge(tmp_path, monkeypatch):
    import app.services.knowledge_base as knowledge_module

    store = KnowledgeBaseStore(tmp_path / "knowledge")
    store.save_file("投手SOP.md", "ROI 未达标时先收缩素材".encode(), "text/markdown")
    monkeypatch.setattr(knowledge_module, "KnowledgeBaseStore", lambda: store)
    from app.services.ops_chat import _knowledge_excerpt

    assert "ROI 未达标时先收缩素材" in _knowledge_excerpt()

def test_delete_file_removes_content_and_falls_back_to_history(tmp_path):
    store = KnowledgeBaseStore(tmp_path / "knowledge")
    first = store.save_file("old.md", "旧规则".encode(), "text/markdown")
    second = store.save_file("new.md", "新规则".encode(), "text/markdown")
    reports = [
        {
            "source": "cdp",
            "verify_passed": True,
            "roi": 2.5,
            "data_quality": {"status": "good"},
        }
    ]

    assert store.delete_file(first["id"]) is True
    assert [item["id"] for item in store.list_files()] == [second["id"]]
    assert "旧规则" not in store.knowledge_excerpt()

    assert store.delete_file(second["id"]) is True
    overview = store.overview(reports)
    assert overview["mode"] == "historical_average"
    assert overview["historical_reference"]["sample_count"] == 1
    assert store.delete_file("missing") is False


def test_knowledge_delete_api(client, tmp_path, monkeypatch):
    store = KnowledgeBaseStore(tmp_path / "knowledge")
    item = store.save_file("rules.md", b"rule", "text/markdown")
    monkeypatch.setattr(knowledge_api, "KnowledgeBaseStore", lambda: store)

    response = client.delete(f"/api/knowledge-base/files/{item['id']}")

    assert response.status_code == 204
    assert store.list_files() == []
    assert client.delete(f"/api/knowledge-base/files/{item['id']}").status_code == 404
