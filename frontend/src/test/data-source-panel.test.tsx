import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

const getCdpConnection = vi.fn();
const getAccountHistory = vi.fn();
const bootstrapAccountHistory = vi.fn();
const getApiConnectionStatus = vi.fn();
const getLocalConfig = vi.fn();
const saveLocalConfig = vi.fn();

vi.mock("../lib/api", () => ({
  getCdpConnection: (...a: unknown[]) => getCdpConnection(...a),
  getAccountHistory: (...a: unknown[]) => getAccountHistory(...a),
  bootstrapAccountHistory: (...a: unknown[]) => bootstrapAccountHistory(...a),
  getApiConnectionStatus: (...a: unknown[]) => getApiConnectionStatus(...a),
  getLocalConfig: (...a: unknown[]) => getLocalConfig(...a),
  saveLocalConfig: (...a: unknown[]) => saveLocalConfig(...a),
  connectCdp: vi.fn(),
  resumeLiveWatch: vi.fn(),
  saveApiConnection: vi.fn().mockResolvedValue({ configured: true }),
  testApiConnection: vi.fn().mockResolvedValue({ ok: true, message: "API 连接成功" })
}));

import { DataSourcePanel } from "../components/DataSourcePanel";

beforeEach(() => {
  getAccountHistory.mockResolvedValue({ account_id: "", configured: false, history: null });
  bootstrapAccountHistory.mockResolvedValue(null);
});

test("数据源窗口同时展示 CDP 和 API 两条链路，并标出当前生效", async () => {
  getCdpConnection.mockResolvedValue({
    endpoint: "http://127.0.0.1:9222",
    connected: true,
    browser: "Chrome/155",
    pages: 4,
    qianchuan_pages: 4,
    error: null
  });
  getApiConnectionStatus.mockResolvedValue({
    configured: false,
    provider_preference: "cdp",
    base_url: "https://api.oceanengine.com",
    advertiser_id: 0
  });
  getLocalConfig.mockResolvedValue({
    saved: { room_name: "质润官方旗舰店" },
    effective: { room_name: "质润官方旗舰店", aavid: "1873104018827399" }
  });

  render(<DataSourcePanel />);

  await waitFor(() => expect(getCdpConnection).toHaveBeenCalled());
  // 两条链路都在
  expect(await screen.findByRole("heading", { name: "本机浏览器连接" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "开放平台连接" })).toBeInTheDocument();
  // CDP 已连接、页面数正确
  expect(screen.getByText("已连接")).toBeInTheDocument();
  expect(screen.getByText(/千川页面 4 个/)).toBeInTheDocument();
  // API 未配置要说清楚
  expect(screen.getByText("未配置")).toBeInTheDocument();
  // API 现在有真正的配置窗口（之前只是个占位说明）
  expect(screen.getByLabelText("App ID")).toBeInTheDocument();
  expect(screen.getByLabelText("App Secret")).toBeInTheDocument();
  expect(screen.getByLabelText("广告主 ID")).toBeInTheDocument();
  expect(screen.getByLabelText("Access Token")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "保存凭据" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "测试连接" })).toBeInTheDocument();
  // 当前生效链路
  expect(screen.getAllByText("本机浏览器连接").length).toBeGreaterThan(0);
});

test("账户近30天数据底座可以手动读取并展示真实汇总", async () => {
  getCdpConnection.mockResolvedValue({ connected: true, pages: 1, qianchuan_pages: 1, error: null, endpoint: "x", browser: "" });
  getApiConnectionStatus.mockResolvedValue({ configured: false, provider_preference: "cdp" });
  getLocalConfig.mockResolvedValue({
    saved: {},
    effective: { room_name: "质润官方旗舰店", aavid: "1873104018827399" }
  });
  getAccountHistory.mockResolvedValue({
    account_id: "1873104018827399",
    configured: true,
    history: null
  });
  bootstrapAccountHistory.mockResolvedValue({
    account_id: "1873104018827399",
    room_name: "质润官方旗舰店",
    source: "cdp",
    range: { start: "2026-10-20", end: "2026-11-18", days: 30 },
    imported_at: "2026-11-18T10:00:00+00:00",
    summary: {
      spend: 2933164.12,
      gmv: 6003556.89,
      orders: 35184,
      roi: 2.05,
      roi_definition: "综合营销ROI（结算口径）"
    },
    daily: [],
    quality: { status: "good", days_with_data: 30, active_days: 29, notes: [] }
  });

  render(<DataSourcePanel />);

  expect(await screen.findByText("账户近30天数据底座")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "读取近30天数据" }));
  await waitFor(() => expect(bootstrapAccountHistory).toHaveBeenCalledWith(true));
  expect(await screen.findByText("2.05")).toBeInTheDocument();
  expect(screen.getByText(/有效天数/)).toBeInTheDocument();
});

test("数据源窗口可以直接改直播间/账户（不用碰 .env）", async () => {
  getCdpConnection.mockResolvedValue({ connected: true, pages: 1, qianchuan_pages: 1, error: null, endpoint: "x", browser: "" });
  getApiConnectionStatus.mockResolvedValue({ configured: false, provider_preference: "cdp" });
  getLocalConfig.mockResolvedValue({
    saved: {},
    effective: { room_name: "质润官方旗舰店", aavid: "1873104018827399" }
  });

  render(<DataSourcePanel />);

  // 两个输入框 + 保存按钮
  expect(await screen.findByLabelText("直播间名称")).toBeInTheDocument();
  expect(screen.getByLabelText("账户 ID")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "保存" })).toBeInTheDocument();
  // 说明要讲清楚"留空=用 .env 的值"
  expect(screen.getByText(/不需要修改配置文件/)).toBeInTheDocument();
});
