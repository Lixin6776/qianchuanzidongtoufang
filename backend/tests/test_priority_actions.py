from app.services.decision_loop import build_live_watch_task, build_priority_actions


def test_priority_actions_keep_only_top_three_with_unique_actions():
    items = build_priority_actions(
        [
            "综合营销 ROI 未达标",
            "GPM 低于基线",
            "近5分钟消耗流速过快",
            "素材集中度过高",
        ],
        [
            "素材：先核对低效素材是否持续多天低跑量",
            "承接：检查承接话术，10 分钟后复核 GPM",
            "消耗：先确认预算是否撞线",
            "素材：补充第二条素材，观察集中度",
            "综合营销 ROI：10～20 分钟后复核目标",
        ],
        {"status": "good", "issues": []},
        level="action",
    )

    assert len(items) == 3
    assert [item["rank"] for item in items] == [1, 2, 3]
    assert items[0]["problem"] == "综合营销 ROI 未达标"
    assert items[0]["action"] == "综合营销 ROI：10～20 分钟后复核目标"
    assert all(item["verify_minutes"] == 10 for item in items)
    assert len({item["action"] for item in items}) == 3
    assert items[0]["action_title"] == "收缩低效消耗，争取 ROI 回到目标"
    assert len(items[0]["steps"]) == 3
    assert "ROI" in items[0]["success_criteria"]
    assert "停止" in items[0]["stop_condition"]


def test_untrusted_data_has_only_one_recovery_action():
    items = build_priority_actions(
        ["ROI 未达标", "GPM 偏低"],
        ["先收缩素材", "调整话术"],
        {
            "status": "unconfirmed",
            "issues": ["当前场次开播时间未确认，不计算本场平均在线"],
        },
        level="action",
    )

    assert len(items) == 1
    assert items[0]["severity"] == "critical"
    assert "数据" in items[0]["problem"]
    assert "恢复" in items[0]["action"] or "核验" in items[0]["action"]
    assert "收缩素材" not in items[0]["action"]
    assert items[0]["action_title"] == "先恢复可信数据"
    assert len(items[0]["steps"]) == 3


def test_task_builder_uses_the_top_priority_action():
    report = {
        "id": "watch-1",
        "captured_at": "2026-11-06T08:00:00+00:00",
        "live_started_at": "2026-11-06T07:00:00+00:00",
        "source": "cdp",
        "level": "action",
        "roi": 2.0,
        "roi_target": 2.5,
        "spend_delta": 500,
        "average_online_viewers": 50,
        "data_quality": {"status": "good", "issues": []},
        "problems": ["旧问题"],
        "adjustments": ["旧动作"],
        "priority_actions": [
            {
                "rank": 1,
                "severity": "high",
                "problem": "综合营销 ROI 未达标",
                "action": "先收缩低效素材",
                "action_title": "收缩低效消耗，争取 ROI 回到目标",
                "steps": ["收缩低效素材", "10 分钟后复核 ROI", "继续下降则停止回滚"],
                "success_criteria": "ROI 改善至少 0.10",
                "stop_condition": "ROI 继续下降时停止",
                "verify_minutes": 10,
            }
        ],
    }

    task = build_live_watch_task(report)

    assert task.context["problem"] == "综合营销 ROI 未达标"
    assert task.context["action"] == "先收缩低效素材"
    assert task.title == "执行：收缩低效消耗，争取 ROI 回到目标"
    assert task.context["action_title"] == "收缩低效消耗，争取 ROI 回到目标"

def test_priority_actions_match_by_category_when_lists_are_reordered():
    items = build_priority_actions(
        [
            "综合营销 ROI 未达标",
            "消耗停滞",
            "追投占比偏高",
            "高消耗低效素材",
        ],
        [
            "素材：先核对高消耗素材是否持续多天低跑量",
            "追投：把追投整体下调 20%～30%",
            "综合营销 ROI：10～20 分钟后复核目标",
            "消耗：先确认预算是否撞线",
        ],
        {"status": "good", "issues": []},
        level="action",
    )

    assert "综合营销 ROI：10～20 分钟后复核目标" in items[0]["action"]
    assert "消耗：先确认预算是否撞线" in items[1]["action"]
    assert "追投：把追投整体下调 20%～30%" in items[2]["action"]
