import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  live_started_at: "2026-10-20T13:00:00+08:00",
  session_status: "active",
  average_online_viewers: 28.5,
  online_samples: 6,
  data_quality: {
    status: "good",
    freshness: "fresh",
    captured_at: "2026-10-20T14:24:49+08:00",
    source_confirmed: true,
    session_confirmed: true,
    session_status: "active",
    fields_present: 7,
    fields_total: 7,
    missing_fields: [],
    issues: [],
    average_online_viewers: 28.5,
    average_online_samples: 6,
    average_online_window_start: "2026-10-20T13:05:00+08:00"
  },
  verify_passed: true,
  problems: ["综合营销 ROI 未达标：当前 2.19，目标 2.80，缺口 0.61"],
  adjustments: ["先收缩低效素材，10～20 分钟后复核 ROI"],
  priority_actions: [
    {
      rank: 1,
      severity: "high",
      problem: "综合营销 ROI 未达标",
      action: "先收缩低效素材，10～20 分钟后复核 ROI",
      action_title: "收缩低效消耗，争取 ROI 回到目标",
      steps: ["收缩低效素材或追投预算", "10～20 分钟后复核 ROI", "继续下降则停止并回滚"],
      success_criteria: "ROI 改善至少 0.10 或达到目标",
      stop_condition: "ROI 继续下降或数据质量异常时停止",
      verify_minutes: 10
    },
    {
      rank: 2,
      severity: "medium",
      problem: "GPM 低于本账户基线",
      action: "先核对承接话术，10 分钟后复核 GPM",
      action_title: "先修承接，再考虑加量",
      steps: ["检查直播画面和话术", "10 分钟后复核 GPM", "承接未稳前不加量"],
      success_criteria: "GPM 提升至少 5%",
      stop_condition: "承接继续恶化时停止",
      verify_minutes: 10
    },
    {
      rank: 3,
      severity: "medium",
      problem: "素材消耗集中度过高",
      action: "补充一条测试素材，观察消耗集中度",
      action_title: "补充测试素材，降低集中度",
      steps: ["补充一条测试素材", "观察消耗集中度", "不直接删除高跑量素材"],
      success_criteria: "素材消耗集中度下降",
      stop_condition: "ROI 明显恶化时停止",
      verify_minutes: 10
    },
    {
      rank: 4,
      severity: "low",
      problem: "这条不应出现在首页",
      action: "这条也不应出现",
      verify_minutes: 30
    }
  ],
  operations: [],
  report_markdown: "## 直播盯盘报表"
};

test("live status card surfaces the latest room and operator metrics", () => {
  const { container } = render(<LiveStatusCard report={report} refreshMs={0} />);

  expect(Array.from(container.querySelectorAll(".live-status-metric-label > span")).map((node) => node.textContent)).toEqual([
    "综合营销 ROI",
    "GPM",
    "近5分钟消耗金额",
    "平均在线",
    "CPM"
  ]);
  expect(screen.getByLabelText("目标达成 78%")).toBeInTheDocument();
  expect(screen.getByText("质润官方旗舰店")).toBeInTheDocument();
  expect(screen.getByText("需要关注")).toBeInTheDocument();
  expect(screen.getByText("¥50")).toBeInTheDocument();
  expect(screen.getByText("2.19")).toBeInTheDocument();
  expect(screen.getByText("¥86.88")).toBeInTheDocument();
  expect(screen.getByText("¥3,912.69")).toBeInTheDocument();
  expect(screen.getByText("28.5")).toBeInTheDocument();
  expect(screen.getByText("本场均值 · 6 个样本")).toBeInTheDocument();
  expect(screen.getByText("数据质量 数据可信")).toBeInTheDocument();
  expect(screen.getByText("字段 7/7")).toBeInTheDocument();
  expect(screen.getByText("新鲜度 新鲜")).toBeInTheDocument();
  expect(screen.getByText("场次 已确认")).toBeInTheDocument();
  expect(screen.getAllByText(/综合营销 ROI 未达标/).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/先收缩低效素材/).length).toBeGreaterThan(0);
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

test("session mismatch blocks the latest report from being treated as live", async () => {
  const staleSessionReport = {
    ...report,
    live_started_at: "2026-10-20T13:00:00+08:00"
  };
  const status = {
    running: true,
    desired_running: true,
    interval_seconds: 300,
    tick_count: 2,
    last_run: "2026-10-20T14:30:00+08:00",
    live_started_at: "2026-10-20T15:00:00+08:00",
    reports: 2,
    last_error: "",
    latest: staleSessionReport
  };
  const load = vi.fn().mockResolvedValue({ report: staleSessionReport, status });

  render(<LiveStatusCard load={load} refreshMs={0} />);
  await act(async () => {
    await Promise.resolve();
  });

  expect(screen.getByText("场次不一致")).toBeInTheDocument();
  expect(screen.getAllByText(/最新数据不属于当前场次/).length).toBeGreaterThan(0);
});

test("backend stale quality blocks live judgment even if the timestamp looks recent", async () => {
  const staleReport = {
    ...report,
    captured_at: new Date().toISOString(),
    data_quality: {
      ...report.data_quality!,
      status: "stale" as const,
      freshness: "stale"
    }
  };
  const status = {
    running: true,
    desired_running: true,
    interval_seconds: 300,
    tick_count: 2,
    last_run: new Date().toISOString(),
    live_started_at: report.live_started_at,
    reports: 2,
    last_error: "",
    latest: staleReport
  };
  const load = vi.fn().mockResolvedValue({ report: staleReport, status });

  render(<LiveStatusCard load={load} refreshMs={0} />);
  await act(async () => {
    await Promise.resolve();
  });

  expect(screen.getByText("数据已过期")).toBeInTheDocument();
  expect(screen.getAllByText(/当前读数只代表最后一次成功采集/).length).toBeGreaterThan(0);
});

test("unconfirmed session blocks live judgment and average online", async () => {
  const unconfirmed = {
    ...report,
    live_started_at: null,
    average_online_viewers: null,
    online_samples: 0,
    data_quality: {
      ...report.data_quality!,
      status: "unconfirmed" as const,
      session_confirmed: false,
      average_online_viewers: null,
      average_online_samples: 0,
      issues: ["当前场次开播时间未确认，不计算本场平均在线"]
    }
  };
  const status = {
    running: true,
    desired_running: true,
    interval_seconds: 300,
    tick_count: 2,
    last_run: new Date().toISOString(),
    live_started_at: "2026-10-20T15:00:00+08:00",
    reports: 2,
    last_error: "",
    latest: unconfirmed
  };
  const load = vi.fn().mockResolvedValue({ report: unconfirmed, status });

  render(<LiveStatusCard load={load} refreshMs={0} />);
  await act(async () => {
    await Promise.resolve();
  });

  expect(screen.getByText("场次待确认")).toBeInTheDocument();
  expect(screen.getByText("场次未确认，不计算均值")).toBeInTheDocument();
  expect(screen.getAllByText(/场次开播时间未确认/).length).toBeGreaterThan(0);
});

test("creates a 10-minute verification task from the current report", async () => {
  const createTask = vi.fn().mockResolvedValue({
    id: "task-1",
    status: "open",
    due_at: "2026-10-20T14:35:00+08:00"
  });

  render(<LiveStatusCard report={report} refreshMs={0} createTask={createTask} />);
  fireEvent.click(screen.getByRole("button", { name: "生成 10 分钟验证任务" }));

  await waitFor(() => expect(createTask).toHaveBeenCalledWith("watch-1"));
  await waitFor(() => expect(screen.getByText(/已生成验证任务/)).toBeInTheDocument());
});

test("priority board shows at most three unique actions", () => {
  render(<LiveStatusCard report={report} refreshMs={0} />);

  expect(screen.getByText("本轮先做 3 件事")).toBeInTheDocument();
  expect(screen.getByText("综合营销 ROI 未达标")).toBeInTheDocument();
  expect(screen.getByText("收缩低效消耗，争取 ROI 回到目标")).toBeInTheDocument();
  expect(screen.getByText("收缩低效素材或追投预算")).toBeInTheDocument();
  expect(screen.getByText("10～20 分钟后复核 ROI")).toBeInTheDocument();
  expect(screen.getByText("先修承接，再考虑加量")).toBeInTheDocument();
  expect(screen.getByText("补充测试素材，降低集中度")).toBeInTheDocument();
  expect(screen.getByText("GPM 低于本账户基线")).toBeInTheDocument();
  expect(screen.getByText("先核对承接话术，10 分钟后复核 GPM")).toBeInTheDocument();
  expect(screen.getByText("素材消耗集中度过高")).toBeInTheDocument();
  expect(screen.queryByText("这条不应出现在首页")).not.toBeInTheDocument();
});
