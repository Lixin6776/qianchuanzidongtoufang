"""从千川「近30天」账户总览页读取数据底座。

只读取页面真实网络响应，不解析 DOM 猜测数值；读取完成后关闭临时页面，
不会因为“连接数据源”反复弹出一堆千川 tab。
"""

from __future__ import annotations

import asyncio
from datetime import date
from urllib.parse import quote

from playwright.async_api import async_playwright

from app.services.account_history import parse_cdp_history

ACCOUNT_HISTORY_PAGE = "https://qianchuan.jinritemai.com/overall-prom"
CDP_CONNECT_TIMEOUT_MS = 30_000


def build_history_url(account_id: str, start_date: date, end_date: date) -> str:
    date_range = quote(f"{start_date.isoformat()},{end_date.isoformat()}", safe="")
    return (
        f"{ACCOUNT_HISTORY_PAGE}?campaignType=1&aavid={quote(str(account_id), safe='')}"
        f"&dateRange={date_range}&uniTab=ad"
    )


class CdpAccountHistoryReader:
    def __init__(self, endpoint: str, timeout_seconds: int = 30) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    async def read(
        self, account_id: str, start_date: date, end_date: date
    ) -> dict:
        captured: dict[str, dict] = {}
        async with async_playwright() as playwright:
            browser = await playwright.chromium.connect_over_cdp(
                self.endpoint,
                timeout=CDP_CONNECT_TIMEOUT_MS,
            )
            context = browser.contexts[0]
            page = await context.new_page()

            async def on_response(response) -> None:
                url = response.url
                if "/ad/api/data/v1/common/statQuery" not in url:
                    return
                try:
                    if "reqFrom=uniDataOverview_trend_today" in url:
                        captured["daily"] = await response.json()
                    elif "reqFrom=uniDataOverview&" in url:
                        captured["overview"] = await response.json()
                except Exception:  # noqa: BLE001
                    # 页面可能有被中断的重复请求；以最终拿到的有效响应为准。
                    return

            page.on("response", on_response)
            try:
                await page.goto(
                    build_history_url(account_id, start_date, end_date),
                    wait_until="domcontentloaded",
                    timeout=self.timeout_seconds * 1000,
                )
                deadline = asyncio.get_running_loop().time() + self.timeout_seconds
                while asyncio.get_running_loop().time() < deadline:
                    if "overview" in captured and "daily" in captured:
                        return parse_cdp_history(captured["overview"], captured["daily"])
                    await asyncio.sleep(0.5)
            finally:
                try:
                    await page.close()
                except Exception:  # noqa: BLE001
                    await asyncio.sleep(0)
        missing = []
        if "overview" not in captured:
            missing.append("账户汇总")
        if "daily" not in captured:
            missing.append("每日趋势")
        raise RuntimeError("千川近30天数据未读取完整：缺少" + "、".join(missing))
