from app.execution.api_read_provider import ApiReadProvider


class MockResponse:
    def json(self):
        return {
            "code": 0,
            "data": {
                "list": [
                    {
                        "ad_id": "plan-1",
                        "ad_name": "计划 A",
                        "status": "active",
                        "budget": 1000,
                    }
                ]
            },
        }


class MockClient:
    def request(self, method, path, params=None, json=None):
        return MockResponse()


def test_read_provider_normalizes_plan_snapshot():
    provider = ApiReadProvider(MockClient(), advertiser_id=123)
    snapshot = provider.get_plan("plan-1")
    assert snapshot.id == "plan-1"
    assert snapshot.status == "active"
    assert snapshot.budget == 1000

def test_read_provider_preserves_extended_plan_fields():
    class ExtendedClient:
        def request(self, method, path, params=None, json=None):
            return MockResponseWithExtendedFields()

    provider = ApiReadProvider(ExtendedClient(), advertiser_id=123)
    snapshot = provider.get_plan("plan-1")
    assert snapshot.bid == 2.5
    assert snapshot.targeting == {"gender": "female"}
    assert snapshot.schedule == {"days": ["mon"]}
    assert snapshot.materials == ["material-1"]


class MockResponseWithExtendedFields:
    def json(self):
        return {
            "code": 0,
            "data": {
                "list": [
                    {
                        "ad_id": "plan-1",
                        "ad_name": "计划 A",
                        "status": "active",
                        "budget": 1000,
                        "bid": 2.5,
                        "targeting": {"gender": "female"},
                        "schedule": {"days": ["mon"]},
                        "materials": ["material-1"],
                    }
                ]
            },
        }
def test_read_provider_requests_daily_account_history_for_date_range():
    captured = {}

    class HistoryClient:
        def request(self, method, path, params=None, json=None):
            captured["method"] = method
            captured["path"] = path
            captured["params"] = params
            return HistoryResponse()

    class HistoryResponse:
        def json(self):
            return {
                "code": 0,
                "data": {
                    "list": [
                        {
                            "stat_datetime": "2026-11-17 00:00:00",
                            "stat_cost": 100,
                            "pay_order_amount": 250,
                            "pay_order_count": 3,
                            "prepay_and_pay_order_roi": 2.5,
                        }
                    ]
                },
            }

    provider = ApiReadProvider(HistoryClient(), advertiser_id=123)
    payload = provider.get_account_history("2026-09-20", "2026-11-18")

    assert captured["method"] == "GET"
    assert captured["path"] == "/open_api/v1.0/qianchuan/report/advertiser/get/"
    params = captured["params"]
    assert params["advertiser_id"] == 123
    assert params["start_date"] == "2026-09-20"
    assert params["end_date"] == "2026-11-18"
    assert params["time_granularity"] == "TIME_GRANULARITY_DAILY"
    assert "stat_cost" in params["fields"]
    assert "LIVE_PROM_GOODS" in params["filtering"]
    assert payload["data"]["list"][0]["pay_order_amount"] == 250
