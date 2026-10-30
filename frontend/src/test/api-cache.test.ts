import { afterEach, expect, test, vi } from "vitest";

import { clearApiGetCacheForTests, getCdpConnection } from "../lib/api";

afterEach(() => {
  clearApiGetCacheForTests();
  vi.unstubAllGlobals();
});

test("connection status requests are deduplicated within the cache window", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ connected: true, pages: 1, qianchuan_pages: 1 })
  });
  vi.stubGlobal("fetch", fetchMock);

  const [first, second] = await Promise.all([getCdpConnection(), getCdpConnection()]);

  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(first).toEqual(second);
});
