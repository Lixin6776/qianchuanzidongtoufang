"""盯盘日志存储（SQLite）：接口要和老的 JSON 版一致，且能导入老数据。"""

import json

from app.services.watch_log_store import SqliteWatchLogStore


def _report(i: int, day: str = "2026-10-10T08:00:00+00:00") -> dict:
    return {"id": f"r{i}", "created_at": f"2026-10-10T08:{i:02d}:00+00:00", "room_name": "质润官方旗舰店", "spend": i}


def test_append_and_list_newest_first(tmp_path):
    store = SqliteWatchLogStore(tmp_path / "w.sqlite3", tmp_path / "none.json")
    store.append(_report(1))
    store.append(_report(3))
    store.append(_report(2))

    items = store.list_logs(limit=10)
    assert [i["id"] for i in items] == ["r3", "r2", "r1"]     # 时间倒序
    assert store.latest()["id"] == "r3"
    assert store.count() == 3


def test_append_same_id_replaces(tmp_path):
    store = SqliteWatchLogStore(tmp_path / "w.sqlite3", tmp_path / "none.json")
    store.append({"id": "same", "created_at": "2026-10-10T08:00:00+00:00", "spend": 1})
    store.append({"id": "same", "created_at": "2026-10-10T08:00:00+00:00", "spend": 2})
    assert store.count() == 1
    assert store.latest()["spend"] == 2


def test_keeps_only_latest_rows(tmp_path):
    store = SqliteWatchLogStore(tmp_path / "w.sqlite3", tmp_path / "none.json", keep=5)
    for i in range(12):
        store.append(_report(i))
    assert store.count() == 5
    assert store.latest()["id"] == "r11"       # 保留最新的


def test_imports_legacy_json_once(tmp_path):
    legacy = tmp_path / "legacy.json"
    legacy.write_text(
        json.dumps([_report(1), _report(2)], ensure_ascii=False), encoding="utf-8"
    )
    store = SqliteWatchLogStore(tmp_path / "w.sqlite3", legacy, keep=100)
    assert store.count() == 2
    # 再建一个（同库）不会重复导入
    again = SqliteWatchLogStore(tmp_path / "w.sqlite3", legacy, keep=100)
    assert again.count() == 2
    # 老文件保留，当备份
    assert legacy.exists()


def test_survives_broken_payload(tmp_path):
    import sqlite3

    path = tmp_path / "w.sqlite3"
    store = SqliteWatchLogStore(path, tmp_path / "none.json")
    store.append(_report(1))
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO watch_reports (id, created_at, payload) VALUES ('bad','2026-10-10T09:00:00+00:00','{not json')")
        conn.commit()
    items = store.list_logs(limit=5)
    assert items[0] == {}          # 坏数据不炸，返回空 dict
    assert items[1]["id"] == "r1"


def _analysis_report(i: int, *, spend: float = 100.0, ops: list[dict] | None = None) -> dict:
    return {
        "id": f"a{i}",
        "created_at": f"2026-10-10T10:{i:02d}:00+00:00",
        "source": "cdp",
        "spend": spend,
        "gmv": spend * 2,
        "spend_split": {"materials": [{"name": "不应进入分析投影"}]},
        "platform_operations": ops or [],
    }


def _op(minute: int, summary: str) -> dict:
    return {
        "time": f"2026-10-10 18:{minute:02d}:00",
        "type": "修改",
        "summary": summary,
        "details": [],
    }


def test_analysis_projection_omits_large_payload_and_keeps_operations(tmp_path):
    store = SqliteWatchLogStore(tmp_path / "w.sqlite3", tmp_path / "none.json")
    report = _analysis_report(
        1,
        ops=[_op(1, "操作内容：素材追投，ID：1880000000000001；调控预算：1000.00元 -> 1500.00元")],
    )
    store.append(report)

    row = store.list_analysis_logs(limit=10)[0]
    assert row["id"] == "a1"
    assert row["source"] == "cdp"
    assert row["spend"] == 100.0
    assert row["gmv"] == 200.0
    assert "spend_split" not in row
    assert row["_operations"][0]["operation"] == "加追投预算"
    assert row["_operations"][0]["meta"]["raw"].startswith("操作内容：素材追投")


def test_analysis_projection_follows_same_id_replacement(tmp_path):
    store = SqliteWatchLogStore(tmp_path / "w.sqlite3", tmp_path / "none.json")
    store.append(_analysis_report(1, spend=100, ops=[_op(1, "操作内容：素材追投，ID：1；调控预算：100.00元 -> 200.00元")]))
    store.append(_analysis_report(1, spend=250))

    row = store.list_analysis_logs(limit=10)[0]
    assert row["spend"] == 250.0
    assert row["_operations"] == []


def test_analysis_projection_deletes_with_retention(tmp_path):
    store = SqliteWatchLogStore(tmp_path / "w.sqlite3", tmp_path / "none.json", keep=2)
    for i in range(1, 4):
        store.append(_analysis_report(i))

    assert [row["id"] for row in store.list_analysis_logs(limit=10)] == ["a3", "a2"]


def test_analysis_projection_backfills_existing_watch_rows(tmp_path):
    import sqlite3

    path = tmp_path / "w.sqlite3"
    store = SqliteWatchLogStore(path, tmp_path / "none.json")
    store.append(_analysis_report(1))
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM watch_analysis")
        payload = json.dumps(_analysis_report(2), ensure_ascii=False)
        conn.execute(
            "INSERT INTO watch_reports (id, created_at, payload) VALUES (?, ?, ?)",
            ("a2", "2026-10-10T10:02:00+00:00", payload),
        )
        conn.commit()

    reopened = SqliteWatchLogStore(path, tmp_path / "none.json")
    rows = reopened.list_analysis_logs(limit=10)
    assert [row["id"] for row in rows] == ["a2", "a1"]


def test_bad_payload_is_not_projected(tmp_path):
    import sqlite3

    path = tmp_path / "w.sqlite3"
    SqliteWatchLogStore(path, tmp_path / "none.json")
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO watch_reports (id, created_at, payload) VALUES ('bad','2026-10-10T09:00:00+00:00','{not json')"
        )
        conn.commit()

    reopened = SqliteWatchLogStore(path, tmp_path / "none.json")
    assert reopened.list_analysis_logs(limit=10) == []
