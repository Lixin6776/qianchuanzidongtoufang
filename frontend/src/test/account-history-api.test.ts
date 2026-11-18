import { afterEach, expect, test, vi } from "vitest";

import { clearApiGetCacheForTests, connectCdp } from "../lib/api";

afterEach(() => {
  clearApiGetCacheForTests();
  vi.unstubAllGlobals();
});

test("连接成功后自动读取账户近30天数据底座", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        connected: true,
        pages: 1,
        qianchuan_pages: 1,
        error: null
      })
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        account_id: "123",
        source: "cdp",
        range: { start: "2026-10-20", end: "2026-11-18", days: 30 },
        summary: { spend: 100, gmv: 205, orders: 2, roi: 2.05 },
        daily: [],
        quality: { status: "good", days_with_data: 30, notes: [] }
      })
    });
  vi.stubGlobal("fetch", fetchMock);

  const result = await connectCdp("auto");

  expect(result.connected).toBe(true);
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    expect.stringContaining("/api/account-history/bootstrap?force=false"),
    expect.objectContaining({ method: "POST" })
  );
});
