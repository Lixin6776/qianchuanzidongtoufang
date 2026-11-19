from datetime import UTC, date, datetime

import pytest

from app.services.account_history import (
    AccountHistoryError,
    AccountHistoryService,
    AccountHistoryStore,
    parse_cdp_history,
)


def _overview_payload():
    return {
        "data": {
            "StatsData": {
                "Totals": {
                    "stat_cost_for_overall_roi2": {"Value": 2932872.74},
                    "total_order_settle_amount_for_roi2_1h": {"Value": 6001935.89},
                    "total_order_settle_count_for_roi2_1h": {"Value": 35175},
                    "total_pay_order_gmv_include_coupon_for_roi2": {"Value": 6349610.88},
                    "total_prepay_and_pay_settle_overall_roi2_1h": {"Value": 2.05},
                    "total_refund_order_gmv_for_roi2_1h_rate": {"Value": 5.48},
                    "total_cost_per_pay_order_settle_for_overall_roi2_1h": {"Value": 83.38},
                }
            }
        }
    }


def _daily_payload():
    return {
        "data": {
            "StatsData": {
                "Rows": [
                    {
                        "Dimensions": {"stat_time_day": {"ValueStr": "2026-11-17"}},
                        "Metrics": {
                            "stat_cost_for_overall_roi2": {"Value": 1000},
                            "total_order_settle_amount_for_roi2_1h": {"Value": 2100},
                            "total_order_settle_count_for_roi2_1h": {"Value": 12},
                            "total_pay_order_gmv_include_coupon_for_roi2": {"Value": 2300},
                            "total_prepay_and_pay_settle_overall_roi2_1h": {"Value": 2.1},
                            "total_refund_order_gmv_for_roi2_1h_rate": {"Value": 4.2},
                            "total_cost_per_pay_order_settle_for_overall_roi2_1h": {"Value": 83.3},
                        },
                    },
                    {
                        "Dimensions": {"stat_time_day": {"ValueStr": "2026-11-18"}},
                        "Metrics": {
                            "stat_cost_for_overall_roi2": {"Value": 0},
                            "total_order_settle_amount_for_roi2_1h": {"Value": 0},
                            "total_order_settle_count_for_roi2_1h": {"Value": 0},
                            "total_pay_order_gmv_include_coupon_for_roi2": {"Value": 0},
                            "total_prepay_and_pay_settle_overall_roi2_1h": {"Value": 0},
                            "total_refund_order_gmv_for_roi2_1h_rate": {"Value": 0},
                            "total_cost_per_pay_order_settle_for_overall_roi2_1h": {"Value": 0},
                        },
                    },
                ]
            }
        }
    }


def test_parse_cdp_history_keeps_roi_and_gmv_definitions_aligned():
    parsed = parse_cdp_history(_overview_payload(), _daily_payload())

    assert parsed["summary"]["spend"] == 2932872.74
    assert parsed["summary"]["gmv"] == 6001935.89
    assert parsed["summary"]["pay_gmv"] == 6349610.88
    assert parsed["summary"]["orders"] == 35175
    assert parsed["summary"]["roi"] == 2.05
    assert parsed["summary"]["roi_definition"] == "综合营销ROI（结算口径）"
    assert parsed["daily"][0]["date"] == "2026-11-17"
    assert parsed["daily"][0]["roi"] == 2.1
    assert parsed["daily"][1]["spend"] == 0
    assert parsed["quality"]["days_with_data"] == 2


@pytest.mark.asyncio
async def test_bootstrap_prefers_api_and_caches_60_day_history(tmp_path):
    calls = {"api": 0, "cdp": 0}

    async def api_collector(account_id, start_date, end_date):
        calls["api"] += 1
        return {
            "summary": {
                "spend": 3000,
                "gmv": 6000,
                "pay_gmv": 6500,
                "orders": 40,
                "roi": 2.0,
                "roi_definition": "支付ROI（开放平台账户报表口径）",
            },
            "daily": [{"date": "2026-11-17", "spend": 3000, "gmv": 6000, "orders": 40, "roi": 2.0}],
            "quality": {"status": "good", "days_with_data": 1, "missing_fields": [], "notes": []},
        }

    async def cdp_collector(account_id, start_date, end_date):
        calls["cdp"] += 1
        raise AssertionError("API should be used first")

    store = AccountHistoryStore(tmp_path / "account_history.json")
    service = AccountHistoryService(
        store=store,
        api_collector=api_collector,
        cdp_collector=cdp_collector,
        today=lambda: date(2026, 11, 18),
        now=lambda: datetime(2026, 11, 18, 10, 0, tzinfo=UTC),
    )

    first = await service.bootstrap(
        account_id="123", room_name="测试直播间", api_available=True
    )
    second = await service.bootstrap(
        account_id="123", room_name="测试直播间", api_available=True
    )

    assert first["source"] == "api"
    assert first["range"] == {"start": "2026-09-20", "end": "2026-11-18", "days": 60}
    assert second["cache_hit"] is True
    assert calls == {"api": 1, "cdp": 0}
    assert store.get("123")["summary"]["roi"] == 2.0


@pytest.mark.asyncio
async def test_bootstrap_falls_back_to_cdp_when_api_fails(tmp_path):
    async def api_collector(account_id, start_date, end_date):
        raise RuntimeError("API permission denied")

    async def cdp_collector(account_id, start_date, end_date):
        return {
            "summary": {
                "spend": 1000,
                "gmv": 2000,
                "pay_gmv": 2100,
                "orders": 10,
                "roi": 2.0,
                "roi_definition": "综合营销ROI（结算口径）",
            },
            "daily": [{"date": "2026-11-18", "spend": 1000, "gmv": 2000, "orders": 10, "roi": 2.0}],
            "quality": {"status": "good", "days_with_data": 1, "missing_fields": [], "notes": []},
        }

    service = AccountHistoryService(
        store=AccountHistoryStore(tmp_path / "account_history.json"),
        api_collector=api_collector,
        cdp_collector=cdp_collector,
        today=lambda: date(2026, 11, 18),
        now=lambda: datetime(2026, 11, 18, 10, 0, tzinfo=UTC),
    )

    result = await service.bootstrap(
        account_id="123", room_name="测试直播间", api_available=True
    )

    assert result["source"] == "cdp"
    assert "API permission denied" in result["quality"]["notes"][0]


@pytest.mark.asyncio
async def test_bootstrap_reports_both_sources_failed(tmp_path):
    async def failed_collector(account_id, start_date, end_date):
        raise RuntimeError("source unavailable")

    service = AccountHistoryService(
        store=AccountHistoryStore(tmp_path / "account_history.json"),
        api_collector=failed_collector,
        cdp_collector=failed_collector,
        today=lambda: date(2026, 11, 18),
        now=lambda: datetime(2026, 11, 18, 10, 0, tzinfo=UTC),
    )

    with pytest.raises(AccountHistoryError, match="两个数据源都失败"):
        await service.bootstrap(
            account_id="123", room_name="测试直播间", api_available=True
        )
