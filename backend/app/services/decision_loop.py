from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.schemas import OpsTaskCreate

_WINDOW_TOLERANCE = timedelta(minutes=5)
_WINDOWS = (10, 30)
_METRIC_LABELS = {
    "roi": "ROI",
    "gpm": "GPM",
    "average_online_viewers": "平均在线",
    "spend_delta": "近5分钟消耗",
    "data_quality": "数据质量",
}


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _short(value: Any, limit: int = 90) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _priority_severity(problem: str, index: int, level: str) -> str:
    if any(
        keyword in problem
        for keyword in ("数据", "读取失败", "场次", "未通过", "停滞", "来源")
    ):
        return "critical"
    if any(
        keyword in problem
        for keyword in ("ROI", "GPM", "消耗", "预算", "素材", "在线", "成交", "CPM")
    ):
        return "high"
    return "high" if index == 0 and level == "action" else "medium"


def _problem_category(problem: str) -> str:
    upper = problem.upper()
    if "ROI" in upper:
        return "roi"
    if "追投" in problem or "调控" in problem:
        return "assist"
    if "素材" in problem or "低效" in problem:
        return "material"
    if "GPM" in upper or "在线" in problem or "承接" in problem:
        return "conversion"
    if "CPM" in upper or "曝光" in problem:
        return "cpm"
    if "消耗" in problem or "流速" in problem:
        return "spend"
    return ""


def _action_category(action: str) -> str:
    text = action.lstrip()
    upper = text.upper()
    if upper.startswith("综合营销 ROI") or "ROI：" in text:
        return "roi"
    if text.startswith(("追投", "降低追投")):
        return "assist"
    if "素材" in text or "低效" in text:
        return "material"
    if text.startswith("承接") or "GPM" in upper:
        return "conversion"
    if "CPM" in upper or "曝光" in text:
        return "cpm"
    if text.startswith(("消耗", "流速")):
        return "spend"
    return ""


def _match_action(
    problem: str,
    adjustments: list[str],
    used_indices: set[int],
) -> str:
    category = _problem_category(problem)
    if category:
        for index, action in enumerate(adjustments):
            if index in used_indices:
                continue
            if _action_category(action) == category:
                used_indices.add(index)
                return action
    for index, action in enumerate(adjustments):
        if index not in used_indices and len(adjustments) == 1:
            used_indices.add(index)
            return action
    return "打开完整报表核对证据后再决定是否操作；本轮不追加新的账户写动作"


def build_priority_actions(
    problems: list[str],
    adjustments: list[str],
    data_quality: dict,
    *,
    level: str = "normal",
    limit: int = 3,
) -> list[dict]:
    """把异常收敛为最多 3 个问题，每个问题只配一个动作。"""
    quality_status = str((data_quality or {}).get("status") or "unknown")
    if quality_status not in {"good", "unknown"}:
        issues = [
            str(item).strip()
            for item in (data_quality or {}).get("issues") or []
            if str(item).strip()
        ]
        return [
            {
                "rank": 1,
                "severity": "critical",
                "problem": "数据质量不可信：" + ("；".join(issues) or "场次、来源或新鲜度未确认"),
                "action": "先恢复并核验当前场次数据：重新读取并确认来源、新鲜度和场次；数据可信前不执行投放动作",
                "verify_minutes": 10,
            }
        ]

    clean_problems = [str(item).strip() for item in problems if str(item).strip()]
    clean_adjustments = [
        str(item).strip() for item in adjustments if str(item).strip()
    ]
    items: list[dict] = []
    seen_problems: set[str] = set()
    used_adjustments: set[int] = set()
    for index, problem in enumerate(clean_problems):
        if problem in seen_problems:
            continue
        seen_problems.add(problem)
        action = _match_action(problem, clean_adjustments, used_adjustments)
        items.append(
            {
                "rank": len(items) + 1,
                "severity": _priority_severity(problem, index, level),
                "problem": problem,
                "action": action,
                "verify_minutes": 10,
            }
        )
        if len(items) >= limit:
            break
    return items


def _focus_metric(report: dict) -> str:
    text = " ".join(
        [
            *(str(item) for item in report.get("problems") or []),
            *(str(item) for item in report.get("adjustments") or []),
        ]
    )
    upper = text.upper()
    if "GPM" in upper:
        return "gpm"
    if "在线" in text or "承接" in text:
        return "average_online_viewers"
    if "流速" in text or "消耗" in text:
        return "spend_delta"
    return "roi"


def _success_and_stop(report: dict, focus_metric: str, baseline: dict) -> tuple[str, str]:
    value = baseline.get(focus_metric)
    target = report.get("roi_target")
    if focus_metric == "roi":
        base_text = f"{float(value):.2f}" if value is not None else "--"
        target_text = (
            f"，或达到目标 ROI {float(target):.2f}" if target is not None else ""
        )
        success = (
            f"10 分钟内综合营销 ROI 较动作前 {base_text} 改善至少 0.10{target_text}；"
            "30 分钟不回落"
        )
        stop = (
            "若 10 分钟内 ROI 较动作前下降至少 0.10、数据质量非可信、"
            "场次不一致或消耗异常放大，停止动作并回滚；30 分钟仍未改善按失败处理"
        )
        return success, stop
    label = _METRIC_LABELS.get(focus_metric, focus_metric)
    success = f"10 分钟内 {label} 较动作前提升至少 5%，且下一轮数据质量为可信"
    stop = (
        f"若 10 分钟内 {label} 继续下降至少 5%、数据质量非可信或场次不一致，"
        "停止动作并回滚；30 分钟仍未改善按失败处理"
    )
    return success, stop


def build_live_watch_task(
    report: dict,
    *,
    now: datetime | None = None,
) -> OpsTaskCreate:
    """把一份盯盘报表转成带基线、验证窗口和止损条件的运营任务。"""
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    quality = report.get("data_quality") or {}
    quality_status = str(quality.get("status") or "unknown")
    problems = [str(item).strip() for item in report.get("problems") or [] if str(item).strip()]
    adjustments = [
        str(item).strip() for item in report.get("adjustments") or [] if str(item).strip()
    ]
    priority_actions = report.get("priority_actions") or build_priority_actions(
        problems, adjustments, quality, level=str(report.get("level") or "normal")
    )
    top_action = priority_actions[0] if priority_actions else {}
    problem = str(top_action.get("problem") or "本周期未返回明确异常")
    action = str(
        top_action.get("action")
        or "暂不执行账户写操作，继续观察下一周期"
    )

    focus_metric = "data_quality" if quality_status not in {"good", "unknown"} else _focus_metric(report)
    baseline = {
        "captured_at": report.get("captured_at") or report.get("created_at"),
        "roi": report.get("roi"),
        "gpm": report.get("gpm"),
        "spend": report.get("spend"),
        "spend_delta": report.get("spend_delta"),
        "gmv": report.get("gmv"),
        "average_online_viewers": report.get("average_online_viewers"),
        "online_samples": report.get("online_samples"),
        "roi_target": report.get("roi_target"),
        "data_quality_status": quality_status,
    }
    if focus_metric == "data_quality":
        success = "重新读取后数据质量为可信、场次已确认，且字段完整"
        stop = "数据质量持续非可信时，不生成或执行任何投放动作"
    else:
        success, stop = _success_and_stop(report, focus_metric, baseline)

    priority = (
        "high"
        if report.get("level") == "action" or quality_status not in {"good", "unknown"}
        else "medium"
    )
    payload = OpsTaskCreate(
        title=f"执行：{_short(action)}",
        description=(
            f"问题：{problem}\n"
            f"建议动作：{action}\n"
            f"数据依据：ROI {report.get('roi')} / GPM {report.get('gpm')} / "
            f"平均在线 {report.get('average_online_viewers')} / "
            f"近5分钟消耗 {report.get('spend_delta')}\n"
            f"来源报表：{report.get('id')}（{report.get('captured_at') or report.get('created_at')}）"
        ),
        source_type="live_watch",
        source_id=report.get("id"),
        owner="当前投手",
        priority=priority,
        due_at=moment + timedelta(minutes=10),
        success_criteria=success,
        stop_condition=stop,
        context={
            "report_id": report.get("id"),
            "problem": problem,
            "action": action,
            "focus_metric": focus_metric,
            "priority_action": top_action,
            "baseline": baseline,
            "session_started_at": report.get("live_started_at"),
            "live_room_id": report.get("live_room_id"),
            "room_name": report.get("room_name"),
            "verification_windows_minutes": list(_WINDOWS),
            "data_quality": quality,
        },
    )
    return payload


def _report_value(report: dict, focus_metric: str) -> float | None:
    if focus_metric == "data_quality":
        return 1.0 if (report.get("data_quality") or {}).get("status") == "good" else 0.0
    value = report.get(focus_metric)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _same_context(report: dict, context: dict) -> bool:
    session = _as_datetime(context.get("session_started_at"))
    report_session = _as_datetime(report.get("live_started_at"))
    if session is not None and report_session is not None and session != report_session:
        return False
    room_id = str(context.get("live_room_id") or "").strip()
    report_room_id = str(report.get("live_room_id") or "").strip()
    if room_id and report_room_id and room_id != report_room_id:
        return False
    return True


def _nearest_window(
    reports: list[dict],
    *,
    created_at: datetime,
    target_minutes: int,
    focus_metric: str,
) -> tuple[dict | None, bool]:
    target = created_at + timedelta(minutes=target_minutes)
    best: dict | None = None
    best_gap: float | None = None
    blocked_by_quality = False
    for report in reports:
        observed = _as_datetime(report.get("captured_at") or report.get("created_at"))
        if observed is None or observed <= created_at:
            continue
        gap = abs((observed - target).total_seconds())
        if gap > _WINDOW_TOLERANCE.total_seconds():
            continue
        quality = report.get("data_quality") or {}
        if quality.get("status") != "good":
            blocked_by_quality = True
            continue
        value = _report_value(report, focus_metric)
        if value is None:
            continue
        if best_gap is None or gap < best_gap:
            best_gap = gap
            best = {
                "target_minutes": target_minutes,
                "observed_at": observed.isoformat(),
                "value": value,
                "delta": None,
                "data_quality": quality.get("status"),
            }
    return best, blocked_by_quality


def _classify(focus_metric: str, baseline: Any, value: float) -> str:
    if focus_metric == "data_quality":
        return "success" if value >= 1.0 else "failure"
    try:
        base = float(baseline) if baseline is not None else None
    except (TypeError, ValueError):
        base = None
    if base is None:
        return "neutral"
    if focus_metric == "roi":
        delta = value - base
        if delta >= 0.10:
            return "success"
        if delta <= -0.10:
            return "failure"
        return "neutral"
    if base == 0:
        return "neutral"
    pct = (value - base) / abs(base) * 100
    if pct >= 5:
        return "success"
    if pct <= -5:
        return "failure"
    return "neutral"


def compute_task_verification(
    task: Any,
    reports: list[dict],
    *,
    now: datetime | None = None,
) -> dict | None:
    context = getattr(task, "context", None) or {}
    baseline = context.get("baseline") or {}
    focus_metric = str(context.get("focus_metric") or "roi")
    created_at = _as_datetime(getattr(task, "created_at", None))
    if created_at is None or not baseline:
        return None
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    eligible = [
        report
        for report in reports
        if str(report.get("source") or "") != "cdp-error"
        and _same_context(report, context)
    ]
    windows: dict[int, dict] = {}
    blocked_any = False
    for minutes in _WINDOWS:
        window, blocked = _nearest_window(
            eligible,
            created_at=created_at,
            target_minutes=minutes,
            focus_metric=focus_metric,
        )
        blocked_any = blocked_any or blocked
        if window is not None:
            window["suggested_verdict"] = _classify(
                focus_metric, baseline.get(focus_metric), window["value"]
            )
            base_value = baseline.get(focus_metric)
            if base_value is not None:
                try:
                    window["delta"] = round(float(window["value"]) - float(base_value), 2)
                except (TypeError, ValueError):
                    window["delta"] = None
            else:
                window["delta"] = None
            windows[minutes] = window

    selected = windows.get(10) or windows.get(30)
    if selected is None:
        elapsed = (moment - created_at).total_seconds()
        if blocked_any:
            status = "insufficient_data"
            verdict = "insufficient_data"
            message = "10 分钟验证缺少可信数据；本轮不能判定动作有效，请先恢复数据质量"
        elif elapsed < 15 * 60:
            status = "pending"
            verdict = "pending"
            message = "等待 10 分钟验证数据"
        else:
            status = "insufficient_data"
            verdict = "insufficient_data"
            message = "验证窗口内没有可信的同场次数据，不能判断动作效果"
    else:
        status = "ready"
        verdict = selected["suggested_verdict"]
        label = _METRIC_LABELS.get(focus_metric, focus_metric)
        change = selected.get("delta")
        change_text = f"{change:+.2f}" if isinstance(change, (int, float)) else "--"
        if focus_metric == "roi":
            value_text = f"{selected['value']:.2f}"
        else:
            value_text = f"{selected['value']:.2f}"
        if verdict == "success":
            message = f"10 分钟 {label} {value_text}（{change_text}）→ 建议保留动作"
        elif verdict == "failure":
            message = f"10 分钟 {label} {value_text}（{change_text}）→ 建议停止并回滚"
        else:
            message = f"10 分钟 {label} {value_text}（{change_text}）→ 效果未确认，继续观察"

    return {
        "status": status,
        "suggested_verdict": verdict,
        "focus_metric": focus_metric,
        "focus_label": _METRIC_LABELS.get(focus_metric, focus_metric),
        "baseline": baseline,
        "window_10m": windows.get(10),
        "window_30m": windows.get(30),
        "message": message,
        "checked_at": moment.isoformat(),
    }
