"""账户近 60 天数据底座。

首次连接数据源时，把账户近 60 天的真实投放数据落成本地快照。
这里只做归一化、缓存和来源回退，不生成缺失数据，也不把支付 GMV 和结算 GMV 混用。
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

BEIJING = ZoneInfo("Asia/Shanghai")
DEFAULT_HISTORY_PATH = (
    Path(__file__).resolve().parents[3] / ".local" / "account_history.json"
)
HISTORY_DAYS = 60
CDP_ROI_DEFINITION = "综合营销ROI（结算口径）"
API_ROI_DEFINITION = "支付ROI（开放平台账户报表口径）"

Collector = Callable[[str, str, str], Awaitable[dict[str, Any]]]


class AccountHistoryError(RuntimeError):
    pass


def _item_value(container: Mapping[str, Any] | None, key: str) -> float | None:
    if not isinstance(container, Mapping):
        return None
    item = container.get(key)
    if isinstance(item, Mapping):
        value = item.get("Value")
    else:
        value = item
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_value(*values: float | None) -> float | None:
    for value in values:
        if value is not None:
            return value
    return None


def _day_text(row: Mapping[str, Any]) -> str | None:
    dimensions = row.get("Dimensions") or {}
    item = dimensions.get("stat_time_day") if isinstance(dimensions, Mapping) else None
    if isinstance(item, Mapping):
        return str(item.get("ValueStr") or "").strip() or None
    return str(item or "").strip() or None


def parse_cdp_history(overview_payload: dict, daily_payload: dict) -> dict[str, Any]:
    stats = ((overview_payload.get("data") or {}).get("StatsData") or {})
    totals = stats.get("Totals") or {}
    if not totals:
        rows = stats.get("Rows") or []
        totals = rows[0].get("Metrics", {}) if rows and isinstance(rows[0], dict) else {}

    spend = _first_value(
        _item_value(totals, "stat_cost_for_overall_roi2"),
        _item_value(totals, "stat_cost_for_roi2"),
    )
    gmv = _item_value(totals, "total_order_settle_amount_for_roi2_1h")
    pay_gmv = _item_value(totals, "total_pay_order_gmv_include_coupon_for_roi2")
    orders = _item_value(totals, "total_order_settle_count_for_roi2_1h")
    roi = _item_value(totals, "total_prepay_and_pay_settle_overall_roi2_1h")
    refund_rate = _item_value(totals, "total_refund_order_gmv_for_roi2_1h_rate")
    cost_per_order = _item_value(
        totals, "total_cost_per_pay_order_settle_for_overall_roi2_1h"
    )
    summary = {
        "spend": spend,
        "gmv": gmv,
        "pay_gmv": pay_gmv,
        "orders": int(orders) if orders is not None else None,
        "roi": roi,
        "refund_rate": refund_rate,
        "cost_per_order": cost_per_order,
        "roi_definition": CDP_ROI_DEFINITION,
    }

    daily: list[dict[str, Any]] = []
    rows = ((daily_payload.get("data") or {}).get("StatsData") or {}).get("Rows") or []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        day = _day_text(row)
        metrics = row.get("Metrics") or {}
        if not day or not isinstance(metrics, Mapping):
            continue
        day_spend = _first_value(
            _item_value(metrics, "stat_cost_for_overall_roi2"),
            _item_value(metrics, "stat_cost_for_roi2"),
        )
        day_gmv = _item_value(metrics, "total_order_settle_amount_for_roi2_1h")
        day_orders = _item_value(metrics, "total_order_settle_count_for_roi2_1h")
        daily.append(
            {
                "date": day,
                "spend": day_spend,
                "gmv": day_gmv,
                "pay_gmv": _item_value(
                    metrics, "total_pay_order_gmv_include_coupon_for_roi2"
                ),
                "orders": int(day_orders) if day_orders is not None else None,
                "roi": _item_value(
                    metrics, "total_prepay_and_pay_settle_overall_roi2_1h"
                ),
                "refund_rate": _item_value(
                    metrics, "total_refund_order_gmv_for_roi2_1h_rate"
                ),
                "cost_per_order": _item_value(
                    metrics, "total_cost_per_pay_order_settle_for_overall_roi2_1h"
                ),
            }
        )

    required = ("spend", "gmv", "orders", "roi")
    missing = [key for key in required if summary.get(key) is None]
    quality = {
        "status": "good" if not missing and daily else "partial",
        "days_with_data": len(daily),
        "active_days": sum(1 for item in daily if (item.get("spend") or 0) > 0),
        "missing_fields": missing,
        "notes": [
            "数据来自千川账户“近60天”综合数据，CDP 读取后直接解析页面真实响应",
            f"ROI 口径：{CDP_ROI_DEFINITION}；支付 GMV 与结算 GMV 分列保存",
        ],
    }
    return {"summary": summary, "daily": daily, "quality": quality}


def parse_api_history(payload: dict) -> dict[str, Any]:
    rows = ((payload.get("data") or {}).get("list") or [])
    daily: list[dict[str, Any]] = []
    total_spend = 0.0
    total_gmv = 0.0
    total_orders = 0
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        day = str(row.get("stat_datetime") or "").split(" ")[0].strip()
        if not day:
            continue
        spend = _item_value(row, "stat_cost")
        gmv = _item_value(row, "pay_order_amount")
        orders_value = _item_value(row, "pay_order_count")
        orders = int(orders_value) if orders_value is not None else None
        roi = _item_value(row, "prepay_and_pay_order_roi")
        daily.append(
            {
                "date": day,
                "spend": spend,
                "gmv": gmv,
                "pay_gmv": gmv,
                "orders": orders,
                "roi": roi,
            }
        )
        total_spend += spend or 0.0
        total_gmv += gmv or 0.0
        total_orders += orders or 0
    calculated_roi = total_gmv / total_spend if total_spend > 0 else None
    summary = {
        "spend": round(total_spend, 2) if total_spend else None,
        "gmv": round(total_gmv, 2) if total_gmv else None,
        "pay_gmv": round(total_gmv, 2) if total_gmv else None,
        "orders": total_orders,
        "roi": round(calculated_roi, 4) if calculated_roi is not None else None,
        "refund_rate": None,
        "cost_per_order": round(total_spend / total_orders, 2)
        if total_orders > 0 and total_spend > 0
        else None,
        "roi_definition": API_ROI_DEFINITION,
    }
    required = ("spend", "gmv", "orders", "roi")
    missing = [key for key in required if summary.get(key) is None]
    quality = {
        "status": "good" if not missing and daily else "partial",
        "days_with_data": len(daily),
        "active_days": sum(1 for item in daily if (item.get("spend") or 0) > 0),
        "missing_fields": missing,
        "notes": [
            "数据来自巨量开放平台账户日报，按日聚合后计算汇总",
            f"ROI 口径：{API_ROI_DEFINITION}；缺失字段保留为空，不做推测",
        ],
    }
    return {"summary": summary, "daily": daily, "quality": quality}


class AccountHistoryStore:
    def __init__(self, path: Path = DEFAULT_HISTORY_PATH) -> None:
        self.path = Path(path)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "accounts": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "accounts": {}}
        if not isinstance(payload, dict):
            return {"version": 1, "accounts": {}}
        accounts = payload.get("accounts")
        if not isinstance(accounts, dict):
            payload["accounts"] = {}
        payload.setdefault("version", 1)
        return payload

    def get(self, account_id: str) -> dict[str, Any] | None:
        value = self._read().get("accounts", {}).get(str(account_id))
        return value if isinstance(value, dict) else None

    def save(self, record: dict[str, Any]) -> dict[str, Any]:
        payload = self._read()
        payload.setdefault("accounts", {})[str(record["account_id"])] = record
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return record


class AccountHistoryService:
    def __init__(
        self,
        *,
        store: AccountHistoryStore | None = None,
        api_collector: Collector | None = None,
        cdp_collector: Collector | None = None,
        today: Callable[[], date] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store or AccountHistoryStore()
        self.api_collector = api_collector
        self.cdp_collector = cdp_collector
        self.now = now or (lambda: datetime.now(BEIJING))
        self.today = today or (lambda: self.now().date())

    def _fresh(self, record: dict[str, Any], today: date) -> bool:
        range_value = record.get("range") or {}
        imported = str(record.get("imported_at") or "")
        return (
            str(range_value.get("end") or "") == today.isoformat()
            and imported.startswith(today.isoformat())
        )

    async def bootstrap(
        self,
        *,
        account_id: str,
        room_name: str = "",
        api_available: bool = False,
        force: bool = False,
    ) -> dict[str, Any]:
        account = str(account_id or "").strip()
        if not account:
            raise AccountHistoryError("缺少账户 ID，无法读取近 60 天数据")
        today = self.today()
        existing = self.store.get(account)
        if existing and not force and self._fresh(existing, today):
            return {**existing, "cache_hit": True}

        start = today - timedelta(days=HISTORY_DAYS - 1)
        errors: list[str] = []
        collected: dict[str, Any] | None = None
        source = ""

        if api_available and self.api_collector is not None:
            try:
                collected = await self.api_collector(
                    account, start.isoformat(), today.isoformat()
                )
                source = "api"
            except Exception as exc:  # noqa: BLE001
                errors.append(f"开放平台读取失败：{exc}")
        if collected is None and self.cdp_collector is not None:
            try:
                collected = await self.cdp_collector(
                    account, start.isoformat(), today.isoformat()
                )
                source = "cdp"
            except Exception as exc:  # noqa: BLE001
                errors.append(f"本机浏览器读取失败：{exc}")
        if collected is None:
            raise AccountHistoryError("两个数据源都失败：" + "；".join(errors))

        quality = dict(collected.get("quality") or {})
        notes = list(quality.get("notes") or [])
        if errors:
            notes.extend(errors)
            quality["status"] = "partial"
        quality["notes"] = notes
        record = {
            "account_id": account,
            "room_name": str(room_name or "").strip(),
            "source": source,
            "range": {
                "start": start.isoformat(),
                "end": today.isoformat(),
                "days": HISTORY_DAYS,
            },
            "imported_at": self.now().isoformat(timespec="seconds"),
            "summary": collected.get("summary") or {},
            "daily": collected.get("daily") or [],
            "quality": quality,
        }
        self.store.save(record)
        return {**record, "cache_hit": False}
