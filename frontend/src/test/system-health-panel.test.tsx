import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

const getSystemDoctor = vi.fn();

vi.mock("../lib/api", () => ({
  getSystemDoctor: (...a: unknown[]) => getSystemDoctor(...a)
}));

import { SystemHealthPanel } from "../components/SystemHealthPanel";

test("自检窗口显示阻断项，并能带着用户去对应模块处理", async () => {
  const onOpenWindow = vi.fn();
  getSystemDoctor.mockResolvedValue({
    status: "blocked",
    ready: false,
    generated_at: "2026-11-17T10:00:00+00:00",
    environment: {
      app_version: "0.1.0",
      python: "3.12.8",
      platform: "Windows-11",
      deployment: "single_account_local"
    },
    summary: { total: 2, ok: 1, warning: 0, blocked: 1 },
    checks: [
      {
        key: "configuration",
        label: "直播间配置",
        status: "ok",
        message: "直播间「测试店」和账户 ID 已配置",
        action_label: "",
        action_target: "",
        optional: false
      },
      {
        key: "data_source",
        label: "数据连接",
        status: "blocked",
        message: "本机浏览器尚未连接数据源",
        action_label: "连接数据源",
        action_target: "data_source",
        optional: false
      }
    ]
  });

  render(<SystemHealthPanel onOpenWindow={onOpenWindow} />);

  expect(await screen.findByText("部署存在 1 个阻断项")).toBeInTheDocument();
  expect(screen.getByText("本机浏览器尚未连接数据源")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "连接数据源" }));
  expect(onOpenWindow).toHaveBeenCalledWith("data_source");

  fireEvent.click(screen.getByRole("button", { name: "重新自检" }));
  await waitFor(() => expect(getSystemDoctor).toHaveBeenCalledTimes(2));
});

test("自检窗口清楚展示当前版本与总体状态", async () => {
  getSystemDoctor.mockResolvedValue({
    status: "attention",
    ready: true,
    generated_at: "2026-11-17T10:00:00+00:00",
    environment: {
      app_version: "0.1.0",
      python: "3.12.8",
      platform: "Windows-11",
      deployment: "single_account_local"
    },
    summary: { total: 1, ok: 0, warning: 1, blocked: 0 },
    checks: [
      {
        key: "llm",
        label: "运营助手对话",
        status: "warning",
        message: "大模型未配置；盯盘、复盘和素材分析仍可使用",
        action_label: "打开大模型",
        action_target: "llm",
        optional: true
      }
    ]
  });

  render(<SystemHealthPanel />);

  expect(await screen.findByText("基础部署可用，有 1 项提醒")).toBeInTheDocument();
  expect(screen.getByText(/版本 0.1.0/)).toBeInTheDocument();
  expect(screen.getByText(/Python 3.12.8/)).toBeInTheDocument();
});
