import { afterEach, expect, test, vi } from "vitest";

import { clearApiGetCacheForTests, connectCdp } from "../lib/api";

afterEach(() => {
  clearApiGetCacheForTests();
  vi.unstubAllGlobals();
});

test("连接成功后立即启动账户近60天数据底座任务", async () => {
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
        id: "job-1",
        account_id: "123",
        status: "running",
        stage: "正在读取本机浏览器中的千川账户数据",
        started_at: "2026-11-19T10:00:00+00:00",
        result: null,
        error: ""
      })
    });
  vi.stubGlobal("fetch", fetchMock);

  const result = await connectCdp("auto");

  expect(result.connected).toBe(true);
  expect(result.account_history_job_id).toBe("job-1");
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    expect.stringContaining("/api/account-history/bootstrap/start?force=false"),
    expect.objectContaining({ method: "POST" })
  );
});
