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
    problem = problems[0] if problems else "本周期未返回明确异常"
    action = (
        adjustments[0]
        if adjustments
        else "暂不执行账户写操作，继续观察下一周期"
    )
    if quality_status not in {"good", "unknown"}:
        action = "先恢复并核验当前场次数据，数据可信前不执行投放动作"
        problem = "；".join(quality.get("issues") or []) or problem

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
