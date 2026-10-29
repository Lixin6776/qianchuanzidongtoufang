import { act, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { LiveStatusCard } from "../components/LiveStatusCard";
import type { LiveWatchReport } from "../lib/api";

const report: LiveWatchReport = {
  id: "watch-1",
  created_at: "2026-10-20T14:25:20+08:00",
  captured_at: "2026-10-20T14:24:49+08:00",
  level: "normal",
  source: "cdp",
  roi: 2.19,
  spend: 52388.57,
  gmv: 114836.1,
  gpm: 3912.69,
  cpm: 86.88,
  online_viewers: 33,
  orders: 696,
  spend_delta: 50,
  roi_target: 2.8,
  exposure_view_rate: 3.48,
  room_name: "质润官方旗舰店",
  session_status: "active",
  verify_passed: true,
  problems: ["综合营销 ROI 未达标：当前 2.19，目标 2.80，缺口 0.61"],
  adjustments: ["先收缩低效素材，10～20 分钟后复核 ROI"],
  operations: [],
  report_markdown: "## 直播盯盘报表"
};

test("live status card surfaces the latest room and operator metrics", () => {
  const { container } = render(<LiveStatusCard report={report} refreshMs={0} />);

  expect(Array.from(container.querySelectorAll(".live-status-metric-label > span")).map((node) => node.textContent)).toEqual([
    "综合营销 ROI",
    "GPM",
    "近5分钟消耗金额",
    "实时在线",
    "CPM"
  ]);
  expect(screen.getByLabelText("目标达成 78%")).toBeInTheDocument();
  expect(screen.getByText("质润官方旗舰店")).toBeInTheDocument();
  expect(screen.getByText("需要关注")).toBeInTheDocument();
  expect(screen.getByText("¥50")).toBeInTheDocument();
  expect(screen.getByText("2.19")).toBeInTheDocument();
  expect(screen.getByText("¥86.88")).toBeInTheDocument();
  expect(screen.getByText("¥3,912.69")).toBeInTheDocument();
  expect(screen.getByText(/综合营销 ROI 未达标/)).toBeInTheDocument();
  expect(screen.getByText(/先收缩低效素材/)).toBeInTheDocument();
});
test("ended live shows the final snapshot and stops polling", async () => {
  vi.useFakeTimers();
  const ended = { ...report, session_status: "ended" };
  const load = vi.fn().mockResolvedValue(ended);
  render(<LiveStatusCard load={load} refreshMs={1000} />);

  await act(async () => {
    await Promise.resolve();
  });
  expect(load).toHaveBeenCalledTimes(1);
  expect(screen.getByText("直播已结束")).toBeInTheDocument();
  expect(screen.getAllByText(/自动盯盘和数据轮询已停止/).length).toBeGreaterThan(0);

  await act(async () => {
    vi.advanceTimersByTime(4000);
    await Promise.resolve();
  });
  expect(load).toHaveBeenCalledTimes(1);
  vi.useRealTimers();
});


test("stopped watch is shown as a final snapshot instead of live zero spend", async () => {
  const stopped = {
    ...report,
    captured_at: "2026-10-29T15:45:53+08:00",
    spend_delta: 0,
    session_status: "active",
    note: "指标正常"
  };
  const status = {
    running: false,
    desired_running: false,
    interval_seconds: 300,
    tick_count: 1,
    last_run: "2026-10-29T15:46:18+08:00",
    reports: 1,
    last_error: "",
    latest: stopped
  };
  const load = vi.fn().mockResolvedValue({ report: stopped, status });

  render(<LiveStatusCard load={load} refreshMs={0} />);
  await act(async () => {
    await Promise.resolve();
  });

  expect(screen.getByText("盯盘已停止")).toBeInTheDocument();
  expect(screen.getAllByText(/当前展示最后快照/).length).toBeGreaterThan(0);
  expect(screen.getByText("盯盘未运行，不计算实时增量")).toBeInTheDocument();
  expect(screen.queryByText("¥0")).not.toBeInTheDocument();
});

test("ended note is recognized even when structured status is missing", async () => {
  const endedNote = {
    ...report,
    created_at: "2026-10-29T15:46:18+08:00",
    captured_at: "2026-10-29T15:45:53+08:00",
    spend_delta: 0,
    session_status: null,
    note: "本场已结束：消耗停留在 ¥47,190.30"
  };
  const status = {
    running: false,
    desired_running: false,
    interval_seconds: 300,
    tick_count: 1,
    last_run: "2026-10-29T15:46:18+08:00",
    reports: 1,
    last_error: "",
    latest: endedNote
  };
  const load = vi.fn().mockResolvedValue({ report: endedNote, status });

  render(<LiveStatusCard load={load} refreshMs={0} />);
  await act(async () => {
    await Promise.resolve();
  });

  expect(screen.getByText("直播已结束")).toBeInTheDocument();
  expect(screen.getAllByText(/不再代表实时数据/).length).toBeGreaterThan(0);
  expect(screen.getByText("已结束，不再计算实时增量")).toBeInTheDocument();
  expect(screen.queryByText("¥0")).not.toBeInTheDocument();
});
