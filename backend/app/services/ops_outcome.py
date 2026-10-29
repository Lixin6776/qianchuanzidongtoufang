"""操作净效应：你手动做的操作，有没有被数据正向反馈。

这套口径是先用真实数据做过自检的，不是拍脑袋：

1. 每个「有操作的时刻」，算 **操作前 10 分钟边际 ROI** vs **操作后 10 分钟边际 ROI**；
2. 用「前后 7 分钟都没有任何操作」的时刻当 **对照组**，算出账户的**基线漂移**
   （实测：什么都不做，10 分钟后边际 ROI 也会掉 -0.106 —— 不扣掉它，所有操作都会
   看起来是负的）；
3. **净效应 = 操作组中位Δ − 对照组中位Δ**；
4. 按**流速**分层（慢/中/快）—— 实测不分层会掩盖关键差异
   （慢流速操作 -0.167 / 中 +0.313 / 快 +0.221）；
5. **n<20 只标"样本不足"，不给结论**；结论性质是**观察性相关，不是因果**。
"""

import json
import re
import statistics
from bisect import bisect_left, bisect_right
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BEIJING = ZoneInfo("Asia/Shanghai")

MIN_SAMPLE = 20
OP_WINDOW_SECONDS = 7 * 60          # 判定"这一刻附近有操作"的时间窗
FORWARD_MINUTES = 10                # 看操作后 10 分钟
NEIGHBOR_TOLERANCE_SECONDS = 200    # 找 ±10 分钟对照记录时的容差

_OP_TIME = re.compile(r"(\d{2}-\d{2}) (\d{2}:\d{2})")
_OP_TIME_SHORT = re.compile(r"^\s*-?\s*(\d{2}:\d{2}):\d{2}")
_BUDGET = re.compile(r"调控预算[：:]\s*([\d.]+)元\s*->\s*([\d.]+)元")
_LOG_BLOCK = re.compile(r"近 \d+ 分钟有 \d+ 条[：:]\s*\n((?:- .*\n?)+)")


def classify_operation(entry: dict) -> str:
    """把一条平台日志归成可统计的操作类型。认不出的归"其他"，不硬凑。

    必须先认"操作对象"（素材追投 / 一键起量 / 抢首屏），再认"改了什么" ——
    否则「一键起量的调控预算 7500→8000」会被误归成「加追投预算」。
    """
    text = " ".join(
        [str(entry.get("summary") or "")]
        + [str(item) for item in (entry.get("details") or [])]
    )
    kind = str(entry.get("type") or "")

    if "素材追投" in text:
        if "调控状态" in text:
            if "-> 已暂停" in text or "调控手动关闭" in text:
                return "暂停追投"
            if "-> 调控中" in text:
                return "开启追投"
        if "调控预算" in text:
            match = _BUDGET.search(text)
            if match:
                before, after = float(match.group(1)), float(match.group(2))
                if after > before:
                    return "加追投预算"
                if after < before:
                    return "降追投预算"
                return "预算不变"
            if kind == "新建":
                return "新建追投"
        return "追投其他"
    if "一键起量" in text:
        return "一键起量"
    if "搜索抢首屏" in text:
        return "抢首屏"
    if "成交出价" in text:
        return "出价调整"
    if "综合营销ROI目标" in text:
        return "ROI目标调整"
    if "增加视频ID" in text or "增加标题ID" in text:
        return "加素材"
    if "删除千川星选" in text:
        return "删素材"
    return "其他"


def _parse_ts(value) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=BEIJING)


_TASK_ID = re.compile(r"任务ID[：:]\s*(\d{6,})")
_BUDGET_ONE = re.compile(r"调控预算[：:]\s*([\d.]+)元\s*$")
_ROI_TARGET = re.compile(r"综合营销ROI目标[：:]\s*([\d.]+)")
_GOAL = re.compile(r"优化目标[：:]\s*([^\n；;]+)")
_SCENARIO = re.compile(r"调控场景[：:]\s*([^\n；;]+)")
# 修改型日志里任务 ID 写成「操作内容：素材追投，ID：xxx」（没写"任务ID"）
_OP_CONTENT_TASK_ID = re.compile(r"操作内容[：:]\s*素材追投[，,]\s*ID[：:]\s*(\d{6,})")
_MATERIAL_ID = re.compile(r"素材ID[：:]\s*(\d{6,})")


def _op_meta(entry: dict) -> dict:
    """从一条日志里抽出：任务ID / 素材ID / 任务名称（有就抽，没有就空）。"""
    lines = [str(entry.get("summary") or "")] + [
        str(item) for item in (entry.get("details") or [])
    ]
    meta: dict = {}
    for line in lines:
        match = _TASK_ID.search(line) or _OP_CONTENT_TASK_ID.search(line)
        if match and "task_id" not in meta:
            meta["task_id"] = match.group(1)
        match = _MATERIAL_ID.search(line)
        if match and "material_id" not in meta:
            meta["material_id"] = match.group(1)
        budget_two = _BUDGET.search(line)
        if budget_two and "budget" not in meta:
            meta["budget"] = float(budget_two.group(2))   # 修改型取改后值
        budget_one = _BUDGET_ONE.search(line)
        if budget_one and "budget" not in meta:
            meta["budget"] = float(budget_one.group(1))   # 新建型
        match = _ROI_TARGET.search(line)
        if match and "roi_target" not in meta:
            meta["roi_target"] = float(match.group(1))
        match = _GOAL.search(line)
        if match and "optimization_goal" not in meta:
            meta["optimization_goal"] = match.group(1).strip()
        match = _SCENARIO.search(line)
        if match and "scenario" not in meta:
            meta["scenario"] = match.group(1).strip()
        if "任务名称" in line and "task_name" not in meta:
            part = line.split("任务名称", 1)[1].lstrip("：: ")
            part = part.split("；")[0].split(";")[0].split(" -> ")[0].strip()
            if part:
                meta["task_name"] = part
    return meta


def _ops_from_report(report: dict) -> list[tuple[datetime, str, dict]]:
    """从一条盯盘记录里取出操作（含任务/素材身份）。

    新报告直接用结构化的 platform_operations；分析投影优先使用预解析结果；
    老报告最后回退去解析 markdown。
    """
    if "_operations" in report:
        projected: list[tuple[datetime, str, dict]] = []
        for item in report.get("_operations") or []:
            if not isinstance(item, dict):
                continue
            at = _parse_ts(item.get("at"))
            name = str(item.get("operation") or "")
            meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
            if at is not None and name:
                projected.append((at.astimezone(BEIJING), name, dict(meta)))
        return projected

    out: list[tuple[datetime, str, dict]] = []
    for entry in report.get("platform_operations") or []:
        at = _parse_ts(str(entry.get("time") or "").replace(" ", "T"))
        if at is not None:
            meta = _op_meta(entry)
            meta["raw"] = str(entry.get("summary") or "")
            meta["_origin"] = "platform"
            out.append((at.astimezone(BEIJING), classify_operation(entry), meta))
    if out:
        return out

    markdown = str(report.get("report_markdown") or "")
    block = _LOG_BLOCK.search(markdown)
    if not block:
        return []
    report_at = _parse_ts(report.get("created_at"))
    if report_at is None:
        return []
    report_at = report_at.astimezone(BEIJING)
    for line in block.group(1).splitlines():
        text = line.strip()
        if not text:
            continue
        at = None
        match = _OP_TIME.search(text)
        if match:
            try:
                at = datetime.strptime(
                    f"2026-{match.group(1)} {match.group(2)}", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=BEIJING)
            except ValueError:
                at = None
        if at is None:
            short = _OP_TIME_SHORT.match(text)
            if short:
                try:
                    at = datetime.strptime(
                        f"2026-{report_at.strftime('%m-%d')} {short.group(1)}",
                        "%Y-%m-%d %H:%M",
                    ).replace(tzinfo=BEIJING)
                except ValueError:
                    at = None
        if at is None:
            continue
        entry = {"summary": text, "type": "新建" if "新建" in text[:30] else "修改"}
        meta = _op_meta(entry)
        meta["raw"] = text
        meta["_origin"] = "markdown"
        out.append((at, classify_operation(entry), meta))
    return out


def _marginal_roi(before: dict, after: dict) -> float | None:
    spend_delta = float(after.get("spend") or 0) - float(before.get("spend") or 0)
    gmv_delta = float(after.get("gmv") or 0) - float(before.get("gmv") or 0)
    if spend_delta <= 50:
        return None
    return gmv_delta / spend_delta


def _nearest_report(
    reports: list[dict],
    report_times: list[datetime],
    moment: datetime,
    minutes: int,
) -> dict | None:
    """用有序时间索引找目标时刻最近的一条报告，保持原来的容差口径。"""
    target = moment + timedelta(minutes=minutes)
    position = bisect_left(report_times, target)
    best = None
    best_gap = 10**9
    for index in (position - 1, position):
        if not 0 <= index < len(reports):
            continue
        gap = abs((report_times[index] - target).total_seconds())
        if gap < best_gap:
            best = reports[index]
            best_gap = gap
    return best if best_gap <= NEIGHBOR_TOLERANCE_SECONDS else None


def _operation_names_near(
    op_events: list[tuple[datetime, str, dict]],
    op_times: list[datetime],
    moment: datetime,
) -> set[str]:
    """只扫描操作时间窗内的记录，避免每个报告都遍历全部操作。"""
    start = bisect_left(op_times, moment - timedelta(seconds=OP_WINDOW_SECONDS))
    end = bisect_right(op_times, moment + timedelta(seconds=OP_WINDOW_SECONDS))
    return {name for _at, name, _meta in op_events[start:end]}


def compute_ops_outcome(logs: Iterable[dict]) -> dict:
    """算出《操作反馈表》需要的全部数据。"""
    reports = []
    for report in logs:
        if report.get("source") != "cdp":
            continue
        at = _parse_ts(report.get("created_at"))
        if at is None:
            continue
        reports.append({**report, "_at": at.astimezone(BEIJING)})
    reports.sort(key=lambda item: item["_at"])

    # 去重操作时刻（同一条日志会在多个 tick 里重复出现）
    seen: set[tuple[str, str]] = set()
    op_events: list[tuple[datetime, str, dict]] = []
    for report in reports:
        for at, name, meta in _ops_from_report(report):
            key = (at.isoformat(), name)
            if key in seen:
                continue
            seen.add(key)
            op_events.append((at, name, meta))

    op_events.sort(key=lambda item: item[0])
    op_times = [at for at, _name, _meta in op_events]
    report_times = [report["_at"] for report in reports]

    rows = []
    for report in reports:
        pre = _nearest_report(reports, report_times, report["_at"], -FORWARD_MINUTES)
        post = _nearest_report(reports, report_times, report["_at"], FORWARD_MINUTES)
        if pre is None or post is None:
            continue
        pre_roi = _marginal_roi(pre, report)
        post_roi = _marginal_roi(report, post)
        if pre_roi is None or post_roi is None:
            continue
        velocity = (float(report.get("spend") or 0) - float(pre.get("spend") or 0)) / 10.0
        rows.append(
            {
                "at": report["_at"],
                "delta": post_roi - pre_roi,
                "velocity": velocity,
                "has_op": bool(_operation_names_near(op_events, op_times, report["_at"])),
            }
        )

    control = [row["delta"] for row in rows if not row["has_op"]]
    treated = [row["delta"] for row in rows if row["has_op"]]
    baseline = statistics.median(control) if control else 0.0

    def summarize(values: list[float]) -> dict:
        if not values:
            return {"n": 0, "median_delta": None, "positive_rate": None, "net_effect": None}
        median = statistics.median(values)
        return {
            "n": len(values),
            "median_delta": round(median, 4),
            "positive_rate": round(sum(1 for v in values if v > 0) / len(values), 4),
            "net_effect": round(median - baseline, 4),
        }

    # 按操作类型汇总：以"时刻"为单位归属（同一时刻有多个操作就各记一次），
    # 不能每个操作各抓一条 —— 那样会重复计数、且数字随解析顺序漂移。
    by_type: dict[str, list[float]] = {}
    for row in rows:
        if not row["has_op"]:
            continue
        names = _operation_names_near(op_events, op_times, row["at"])
        # 只统计"此刻只有一种操作"的样本：操作扎堆时无法区分是哪一个起的作用，
        # 硬算会让所有操作类型都继承同一个效应（实测会全部变成 positive）。
        if len(names) != 1:
            continue
        by_type.setdefault(next(iter(names)), []).append(row["delta"])

    operations = []
    for name, values in sorted(by_type.items(), key=lambda kv: len(kv[1]), reverse=True):
        summary = summarize(values)
        summary["operation"] = name
        summary["verdict"] = (
            "insufficient"
            if summary["n"] < MIN_SAMPLE
            else ("positive" if (summary["net_effect"] or 0) > 0.1 else "negative" if (summary["net_effect"] or 0) < -0.1 else "neutral")
        )
        operations.append(summary)

    # 按流速分层（这是实测里最有价值的切法）
    velocities = sorted(row["velocity"] for row in rows)
    strata = []
    if len(velocities) >= 6:
        low, high = statistics.quantiles(velocities, n=3)[0], statistics.quantiles(velocities, n=3)[1]
        for label, predicate in (
            ("慢", lambda v: v < low),
            ("中", lambda v: low <= v < high),
            ("快", lambda v: v >= high),
        ):
            treated_v = [row["delta"] for row in rows if row["has_op"] and predicate(row["velocity"])]
            control_v = [row["delta"] for row in rows if not row["has_op"] and predicate(row["velocity"])]
            item = {
                "label": label,
                "treated": summarize(treated_v),
                "control": summarize(control_v),
            }
            if item["treated"]["n"] and item["control"]["n"]:
                item["net_effect"] = round(
                    item["treated"]["median_delta"] - item["control"]["median_delta"], 4
                )
                item["verdict"] = (
                    "insufficient"
                    if min(item["treated"]["n"], item["control"]["n"]) < MIN_SAMPLE
                    else ("positive" if item["net_effect"] > 0.1 else "negative" if item["net_effect"] < -0.1 else "neutral")
                )
            else:
                item["net_effect"] = None
                item["verdict"] = "insufficient"
            strata.append(item)

    return {
        "generated_at": datetime.now(BEIJING).isoformat(),
        "window_minutes": FORWARD_MINUTES,
        "operation_events": len(op_events),
        "min_sample": MIN_SAMPLE,
        "baseline": summarize(control) | {"operation": "（基线：无操作时刻）"},
        "treated": summarize(treated),
        "operations": operations,
        "velocity_strata": strata,
        "note": "观察性相关，不是因果：操作是你自己按状态选的，且同一时刻可能有多个操作。",
    }


_VERDICT_LABEL = {"positive": "正向", "negative": "负向", "neutral": "中性"}


def significant_operations(result: dict) -> list[dict]:
    """只保留样本够（n >= min_sample）的操作类型。"""
    min_sample = int(result.get("min_sample") or MIN_SAMPLE)
    return [
        row
        for row in result.get("operations", [])
        if int(row.get("n") or 0) >= min_sample
    ]


def format_ledger(rows: list[dict]) -> str:
    """把历史账本渲染成一段 Markdown（盯盘报表 / 复盘共用）。"""
    if not rows:
        return ""
    lines = ["### 历史账本（本账户实测）", ""]
    for row in rows:
        lines.append(
            f"- {row.get('operation')}：净效应 {float(row.get('net_effect') or 0):+.2f}"
            f"（n={row.get('n')}，{_VERDICT_LABEL.get(str(row.get('verdict')), row.get('verdict'))}）"
        )
    lines.append("")
    lines.append(
        "> 已扣掉账户自然漂移；样本 < 20 不出结论；"
        "这是**观察到相关**，不是因果，做决策时请结合当下判断。"
    )
    return "\n".join(lines)


SNAPSHOT_PATH = Path(__file__).resolve().parents[3] / ".local" / "asset_snapshots.json"


class AssetSnapshotStore:
    """数据资产快照：每天存一份"当前资产长什么样"。

    价值：能看到样本在长大、结论在变稳（还是变卦），而不是只有一份"此刻"的表。
    """

    def __init__(self, path: Path = SNAPSHOT_PATH) -> None:
        self.path = path

    def list(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return payload if isinstance(payload, list) else []

    def record(self, result: dict) -> dict:
        """同一天只留一份（后写的覆盖），避免一天多次刷新堆一堆。"""
        day = str(result.get("generated_at") or "")[:10]
        items = [item for item in self.list() if item.get("date") != day]
        entry = {"date": day, "snapshot": result}
        items.append(entry)
        items.sort(key=lambda item: str(item.get("date") or ""))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return entry


def compute_asset_overview(
    logs: Iterable[dict],
    *,
    reviews: int = 0,
    analyses: int = 0,
) -> dict:
    """数据资产概览：资产有多厚、结论有几条、最近数据健不健康。"""
    reports = []
    error_count = 0
    for report in logs:
        at = _parse_ts(report.get("created_at"))
        if at is None:
            continue
        reports.append((at.astimezone(BEIJING), report))
        if report.get("source") == "cdp-error":
            error_count += 1
    reports.sort(key=lambda item: item[0])

    if reports:
        start, end = reports[0][0], reports[-1][0]
        asset_days = max(1, (end.date() - start.date()).days + 1)
        span_start = start.strftime("%Y-%m-%d")
        span_end = end.strftime("%Y-%m-%d")
    else:
        asset_days = 0
        span_start = span_end = ""

    # 最近 24 小时的数据健康
    cutoff = datetime.now(BEIJING) - timedelta(hours=24)
    recent = [item for item in reports if item[0] >= cutoff]
    recent_total = len(recent)
    recent_valid = sum(1 for _, report in recent if report.get("source") == "cdp")
    valid_rate = round(recent_valid / recent_total, 4) if recent_total else None

    outcome = compute_ops_outcome([report for _, report in reports])
    conclusions = len(significant_operations(outcome))

    return {
        "asset_days": asset_days,
        "span": {"start": span_start, "end": span_end},
        "watch_reports": len(reports),
        "operation_events": outcome.get("operation_events", 0),
        "operation_types": len(outcome.get("operations", [])),
        "conclusions": conclusions,
        "reviews": reviews,
        "analyses": analyses,
        "health": {
            "last_24h_total": recent_total,
            "last_24h_valid": recent_valid,
            "valid_rate": valid_rate,
            "cdp_errors": error_count,
        },
    }


def _state_of(report: dict, before_window: dict | None) -> dict:
    """操作时刻的账户状态：流速 / 在线 / CPM / 曝光观看率 / 追投占比。"""
    velocity = None
    if before_window is not None:
        span = (_parse_ts(report.get("created_at")) - _parse_ts(before_window.get("created_at")))
        minutes = span.total_seconds() / 60 if span else 0
        if minutes > 0:
            velocity = (
                float(report.get("spend") or 0) - float(before_window.get("spend") or 0)
            ) / minutes
    assist_share = report.get("assist_share")
    if assist_share is None:
        split = report.get("spend_split") or {}
        basic = float(split.get("basic_spend") or 0)
        assist = float(split.get("assist_spend") or 0)
        assist_share = assist / (basic + assist) if (basic + assist) > 0 else None
    return {
        "velocity": round(velocity, 1) if velocity is not None else None,
        "online_viewers": report.get("online_viewers"),
        "cpm": round(float(report.get("cpm")), 2) if report.get("cpm") is not None else None,
        "exposure_view_rate": report.get("exposure_view_rate"),
        "roi": report.get("roi"),
        "assist_share": round(assist_share, 3) if assist_share is not None else None,
    }


def compute_op_cases(logs: Iterable[dict], limit: int = 200) -> list[dict]:
    """操作流水：每一笔操作 + 操作前后的边际 ROI（可追溯的原始凭证）。"""
    try:
        from app.services.material_names import MaterialNameStore

        material_names = MaterialNameStore().load()
    except Exception:  # noqa: BLE001
        material_names = {}
    reports = []
    for report in logs:
        at = _parse_ts(report.get("created_at"))
        if at is None:
            continue
        reports.append({**report, "_at": at.astimezone(BEIJING)})
    reports.sort(key=lambda item: item["_at"])
    report_times = [report["_at"] for report in reports]

    # 任务ID -> 素材ID：只有「新建」日志里同时带这两个，用它回填「暂停/调预算」
    task_materials: dict[str, str] = {}
    task_names: dict[str, str] = {}
    for report in reports:
        for _at, _name, meta in _ops_from_report(report):
            if meta.get("_origin") != "platform":
                continue
            task_id = meta.get("task_id")
            if not task_id:
                continue
            if meta.get("material_id"):
                task_materials.setdefault(task_id, meta["material_id"])
            if meta.get("task_name"):
                task_names.setdefault(task_id, meta["task_name"])

    seen: set[tuple[str, str]] = set()
    events: list[tuple[datetime, str, str, dict]] = []
    for report in reports:
        for at, name, meta in _ops_from_report(report):
            raw = ""
            if meta.get("_origin") == "platform":
                raw = str(meta.get("raw") or "")
            key = (at.isoformat(), name)
            if key in seen:
                continue
            seen.add(key)
            task_id = str(meta.get("task_id") or "")
            material_id = str(meta.get("material_id") or "") or task_materials.get(task_id, "")
            task_name = str(meta.get("task_name") or "") or task_names.get(task_id, "")
            events.append(
                (
                    at,
                    name,
                    raw,
                    {
                        "task_id": task_id,
                        "material_id": material_id,
                        "task_name": task_name,
                        "budget": meta.get("budget"),
                        "roi_target": meta.get("roi_target"),
                        "optimization_goal": meta.get("optimization_goal") or "",
                        "scenario": meta.get("scenario") or "",
                    },
                )
            )

    def wroi(before: dict, after: dict) -> float | None:
        spend_delta = float(after.get("spend") or 0) - float(before.get("spend") or 0)
        gmv_delta = float(after.get("gmv") or 0) - float(before.get("gmv") or 0)
        if spend_delta <= 50:
            return None
        return gmv_delta / spend_delta

    rows: list[dict] = []
    for at, name, raw, meta in events:
        base_index = bisect_right(report_times, at) - 1
        base = reports[base_index] if base_index >= 0 else None
        if base is None:
            continue
        before_report = _nearest_report(reports, report_times, base["_at"], -FORWARD_MINUTES)
        after_10 = _nearest_report(reports, report_times, base["_at"], FORWARD_MINUTES)
        after_20 = _nearest_report(reports, report_times, base["_at"], 2 * FORWARD_MINUTES)
        pre_roi = wroi(before_report, base) if before_report else None
        roi_10 = wroi(base, after_10) if after_10 else None
        roi_20 = wroi(base, after_20) if after_20 else None
        delta_10 = roi_10 - pre_roi if (pre_roi is not None and roi_10 is not None) else None
        delta_20 = roi_20 - pre_roi if (pre_roi is not None and roi_20 is not None) else None
        if delta_10 is None:
            verdict = "unknown"
        elif delta_10 > 0:
            verdict = "positive"
        elif delta_10 < 0:
            verdict = "negative"
        else:
            verdict = "flat"
        rows.append(
            {
                "at": at.strftime("%Y-%m-%d %H:%M"),
                "operation": name,
                "summary": raw or name,
                "before_roi": round(pre_roi, 4) if pre_roi is not None else None,
                "after_10m_roi": round(roi_10, 4) if roi_10 is not None else None,
                "after_20m_roi": round(roi_20, 4) if roi_20 is not None else None,
                "delta_10m": round(delta_10, 4) if delta_10 is not None else None,
                "delta_20m": round(delta_20, 4) if delta_20 is not None else None,
                "verdict": verdict,
                "task_id": meta.get("task_id") or "",
                "material_id": meta.get("material_id") or "",
                "task_name": meta.get("task_name") or "",
                "material_name": material_names.get(str(meta.get("material_id") or ""), ""),
                "state": _state_of(base, before_report),
                "budget": meta.get("budget"),
                "roi_target": meta.get("roi_target"),
                "optimization_goal": meta.get("optimization_goal") or "",
                "scenario": meta.get("scenario") or "",
            }
        )
    rows.sort(key=lambda item: item["at"], reverse=True)
    return rows[:limit]


def compute_scenarios(logs: Iterable[dict], min_sample: int | None = None) -> dict:
    """决策场景 × 操作 × 结果。

    运营的真实问题不是"哪个操作平均好"，而是"**我现在这个状态**下该做什么"。
    所以这里按流速分档，各档内再比"有操作 vs 无操作"，给出每个操作在**该状态下**的净效应。
    """
    threshold = int(min_sample or MIN_SAMPLE)
    reports = []
    for report in logs:
        at = _parse_ts(report.get("created_at"))
        if at is None or report.get("source") != "cdp":
            continue
        reports.append({**report, "_at": at.astimezone(BEIJING)})
    reports.sort(key=lambda item: item["_at"])

    op_events: list[tuple[datetime, str, dict]] = []
    seen: set[tuple[str, str]] = set()
    for report in reports:
        for at, name, meta in _ops_from_report(report):
            key = (at.isoformat(), name)
            if key in seen:
                continue
            seen.add(key)
            op_events.append((at, name, meta))
    op_events.sort(key=lambda item: item[0])
    op_times = [at for at, _name, _meta in op_events]
    report_times = [report["_at"] for report in reports]

    def wroi(before: dict, after: dict) -> float | None:
        spend_delta = float(after.get("spend") or 0) - float(before.get("spend") or 0)
        gmv_delta = float(after.get("gmv") or 0) - float(before.get("gmv") or 0)
        if spend_delta <= 50:
            return None
        return gmv_delta / spend_delta

    rows = []
    for report in reports:
        pre = _nearest_report(reports, report_times, report["_at"], -FORWARD_MINUTES)
        post = _nearest_report(reports, report_times, report["_at"], FORWARD_MINUTES)
        if pre is None or post is None:
            continue
        pre_roi = wroi(pre, report)
        post_roi = wroi(report, post)
        if pre_roi is None or post_roi is None:
            continue
        velocity = (float(report.get("spend") or 0) - float(pre.get("spend") or 0)) / 10.0
        names = _operation_names_near(op_events, op_times, report["_at"])
        rows.append(
            {
                "delta": post_roi - pre_roi,
                "velocity": velocity,
                "names": names,
                "has_op": bool(names),
            }
        )

    if len(rows) < 6:
        return {"scenarios": [], "min_sample": threshold, "note": "样本不足"}

    velocities = sorted(row["velocity"] for row in rows)
    q1, q2 = statistics.quantiles(velocities, n=3)[0], statistics.quantiles(velocities, n=3)[1]

    def bucket(value: float) -> str:
        if value < q1:
            return "流速偏低"
        if value < q2:
            return "流速正常"
        return "流速加快"

    scenarios = []
    for label in ("流速偏低", "流速正常", "流速加快"):
        group = [row for row in rows if bucket(row["velocity"]) == label]
        control = [row["delta"] for row in group if not row["has_op"]]
        if not control:
            continue
        baseline = statistics.median(control)
        operations = []
        for name in {n for row in group for n in row["names"]}:
            treated = [
                row["delta"]
                for row in group
                if row["names"] == {name}
            ]
            if not treated:
                continue
            median = statistics.median(treated)
            net = median - baseline
            verdict = (
                "insufficient"
                if len(treated) < threshold
                else ("positive" if net > 0.1 else "negative" if net < -0.1 else "neutral")
            )
            operations.append(
                {
                    "operation": name,
                    "n": len(treated),
                    "median_delta": round(median, 4),
                    "net_effect": round(net, 4),
                    "verdict": verdict,
                }
            )
        operations.sort(key=lambda item: (item["verdict"] == "insufficient", -abs(item["net_effect"])))
        scenarios.append(
            {
                "label": label,
                "control": {"n": len(control), "median_delta": round(baseline, 4)},
                "operations": operations,
            }
        )

    return {
        "scenarios": scenarios,
        "velocity_cutoffs": {"low": round(q1, 1), "high": round(q2, 1)},
        "min_sample": threshold,
        "note": "观察性相关，不是因果；只统计'此刻只有一种操作'的样本。",
    }
