# -*- coding: utf-8 -*-
"""操作净效应：分类 + 结构 + 护栏（样本不足不给结论）。"""

from datetime import datetime, timedelta, timezone

from app.services.ops_outcome import classify_operation, compute_ops_outcome

BJ = timezone(timedelta(hours=8))


def test_classify_operation_covers_common_types():
    assert classify_operation({"summary": "操作内容：素材追投，ID：1；调控状态：调控中 -> 已暂停"}) == "暂停追投"
    assert classify_operation({"summary": "操作内容：素材追投，ID：1；调控预算：3000.00元 -> 100.00元"}) == "降追投预算"
    assert classify_operation({"summary": "操作内容：素材追投，ID：1；调控预算：1000.00元 -> 3000.00元"}) == "加追投预算"
    assert (
        classify_operation({"type": "新建", "summary": "操作：素材追投；调控预算：2000.00元"})
        == "新建追投"
    )
    assert classify_operation({"summary": "综合营销ROI目标：3 -> 2.80"}) == "ROI目标调整"
    assert classify_operation({"summary": "增加视频ID: 123,456"}) == "加素材"
    assert classify_operation({"summary": "完全看不懂的东西"}) == "其他"


def _report(minute: int, spend: float, gmv: float, ops=None):
    at = datetime(2026, 10, 10, 8, 0, tzinfo=BJ) + timedelta(minutes=5 * minute)
    return {
        "source": "cdp",
        "created_at": at.isoformat(),
        "spend": spend,
        "gmv": gmv,
        "platform_operations": ops or [],
    }


def _op(minute: int, summary: str, kind: str = "修改"):
    at = datetime(2026, 10, 10, 8, 0, tzinfo=BJ) + timedelta(minutes=5 * minute)
    return {"time": at.strftime("%Y-%m-%d %H:%M:%S"), "type": kind, "summary": summary, "details": []}


def test_compute_ops_outcome_structure_and_sample_guard():
    logs = []
    for i in range(12):
        logs.append(_report(i, spend=1000 + i * 300, gmv=2000 + i * 750))
    # 在第 6 个时刻做一次"加追投预算"
    logs[6]["platform_operations"] = [_op(6, "操作内容：素材追投，ID：1；调控预算：3000.00元 -> 4000.00元")]

    result = compute_ops_outcome(logs)
    assert result["window_minutes"] == 10
    assert result["min_sample"] == 20
    assert "baseline" in result and "operations" in result and "velocity_strata" in result
    # 只有 1 个操作样本 → 必须标"样本不足"，不能给结论
    op = next((x for x in result["operations"] if x["operation"] == "加追投预算"), None)
    assert op is not None
    assert op["verdict"] == "insufficient"


def test_asset_snapshot_store_dedupes_by_day(tmp_path):
    """资产快照：同一天只留一份（后写覆盖），跨天各留一份。"""
    from app.services.ops_outcome import AssetSnapshotStore

    store = AssetSnapshotStore(tmp_path / "snaps.json")
    store.record({"generated_at": "2026-10-17T08:10:00+08:00", "operations": [1]})
    store.record({"generated_at": "2026-10-17T09:00:00+08:00", "operations": [2]})
    store.record({"generated_at": "2026-10-18T08:10:00+08:00", "operations": [3]})

    items = store.list()
    assert len(items) == 2
    assert items[0]["date"] == "2026-10-17"
    assert items[0]["snapshot"]["operations"] == [2]   # 同天后写覆盖
    assert items[1]["date"] == "2026-10-18"


def test_classify_one_click_boost_is_not_budget_change():
    """一键起量里的"调控预算"不能把它误归成"加追投预算"（真实踩过）。"""
    assert (
        classify_operation(
            {"summary": "操作内容：一键起量，ID：1；调控预算：7500.00元 -> 8000.00元"}
        )
        == "一键起量"
    )


def test_material_name_store_upsert_and_lookup(tmp_path):
    """素材ID→素材名：落盘后能查回来（操作日志归因要用）。"""
    from app.services.material_names import MaterialNameStore

    store = MaterialNameStore(tmp_path / "names.json")
    changed = store.upsert(
        [
            {"material_id": "111", "name": "素材A"},
            {"material_id": "222", "name": "素材B"},
        ]
    )
    assert changed == 2
    assert store.name_of("111") == "素材A"
    assert store.name_of("999") == ""

    # 同名不重复写；改名会更新
    assert store.upsert([{"material_id": "111", "name": "素材A"}]) == 0
    assert store.upsert([{"material_id": "111", "name": "素材A-改"}]) == 1
    assert store.name_of("111") == "素材A-改"


def test_op_meta_extracts_budget_roi_material():
    """新建追投的 预算 / ROI目标 / 素材ID / 场景 都要抽出来（用于归因）。"""
    from app.services.ops_outcome import _op_meta

    meta = _op_meta(
        {
            "type": "新建",
            "details": [
                "操作：素材追投",
                "任务名称：20261019_素材追投_12:04:21直投",
                "任务ID：1879449451916506",
                "调控预算：2000.00元",
                "调控场景：控成本追投",
                "优化目标：综合营销ROI",
                "综合营销ROI目标：1.70",
                "素材ID：1876023120663875",
            ],
            "summary": "",
        }
    )
    assert meta["task_id"] == "1879449451916506"
    assert meta["budget"] == 2000.0
    assert meta["roi_target"] == 1.7
    assert meta["material_id"] == "1876023120663875"
    assert meta["scenario"] == "控成本追投"
    assert meta["optimization_goal"] == "综合营销ROI"
