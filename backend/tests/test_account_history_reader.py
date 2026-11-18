from datetime import date

from app.execution.cdp.account_history_reader import build_history_url
from app.services.account_history import parse_api_history


def test_build_history_url_uses_exact_60_day_range_and_account():
    url = build_history_url(
        "1873104018827399", date(2026, 9, 20), date(2026, 11, 18)
    )

    assert "aavid=1873104018827399" in url
    assert "dateRange=2026-09-20%2C2026-11-18" in url
    assert "/overall-prom?" in url


def test_parse_api_history_computes_totals_from_daily_rows():
    parsed = parse_api_history(
        {
            "data": {
                "list": [
                    {
                        "stat_datetime": "2026-11-17 00:00:00",
                        "stat_cost": 1000,
                        "pay_order_amount": 2200,
                        "pay_order_count": 20,
                        "prepay_and_pay_order_roi": 2.2,
                    },
                    {
                        "stat_datetime": "2026-11-18 00:00:00",
                        "stat_cost": 500,
                        "pay_order_amount": 900,
                        "pay_order_count": 8,
                        "prepay_and_pay_order_roi": 1.8,
                    },
                ]
            }
        }
    )

    assert parsed["summary"]["spend"] == 1500
    assert parsed["summary"]["gmv"] == 3100
    assert parsed["summary"]["orders"] == 28
    assert parsed["summary"]["roi"] == 2.0667
    assert parsed["quality"]["days_with_data"] == 2
