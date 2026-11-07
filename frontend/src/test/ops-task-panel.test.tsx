import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { OpsTaskPanel } from "../components/OpsTaskPanel";

function task(id: string, overrides: Record<string, unknown> = {}) {
  return {
    id,
    title: `任务 ${id}`,
    description: "",
    owner: "当前投手",
    priority: "medium",
    status: "open",
    success_criteria: "指标改善",
    stop_condition: "数据异常时停止",
    result: "",
    created_at: "2026-11-06T08:00:00+00:00",
    source_type: "manual",
    source_id: null,
    context: {},
    verification: null,
    ...overrides
  };
}

test("ops task panel shows 10 and 30 minute verification evidence", async () => {
  const loadTasks = vi.fn().mockResolvedValue([
    task("task-1", {
      title: "执行：先收缩低效素材",
      description: "问题：ROI 未达标",
      priority: "high",
      status: "in_progress",
      source_type: "live_watch",
      source_id: "watch-1",
      verification: {
        status: "ready",
        suggested_verdict: "success",
        focus_metric: "roi",
        focus_label: "ROI",
        message: "10 分钟 ROI 2.15（+0.15）→ 建议保留动作",
        window_10m: { target_minutes: 10, observed_at: "2026-11-06T08:10:00+00:00", value: 2.15, delta: 0.15 },
        window_30m: { target_minutes: 30, observed_at: "2026-11-06T08:30:00+00:00", value: 2.2, delta: 0.2 }
      }
    })
  ]);

  render(<OpsTaskPanel loadTasks={loadTasks} refreshMs={0} />);

  expect(await screen.findByText("10 分钟：ROI 2.15（+0.15）")).toBeInTheDocument();
  expect(screen.getByText("30 分钟：ROI 2.20（+0.20）")).toBeInTheDocument();
  expect(screen.getByText(/建议保留动作/)).toBeInTheDocument();
});

test("task filters separate pending, verifying and completed work", async () => {
  const loadTasks = vi.fn().mockResolvedValue([
    task("open", { title: "待处理任务", status: "open" }),
    task("running", { title: "验证中任务", status: "in_progress" }),
    task("done", { title: "已完成任务", status: "done" })
  ]);

  render(<OpsTaskPanel loadTasks={loadTasks} refreshMs={0} />);
  await screen.findByText("待处理任务");

  fireEvent.click(screen.getByRole("button", { name: /验证中/ }));
  expect(screen.getByText("验证中任务")).toBeInTheDocument();
  expect(screen.queryByText("待处理任务")).not.toBeInTheDocument();
  expect(screen.queryByText("已完成任务")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /已完成/ }));
  expect(screen.getByText("已完成任务")).toBeInTheDocument();
  expect(screen.queryByText("验证中任务")).not.toBeInTheDocument();
});

test("task board refreshes verification data automatically", async () => {
  vi.useFakeTimers();
  const loadTasks = vi.fn().mockResolvedValue([task("task-1")]);

  render(<OpsTaskPanel loadTasks={loadTasks} refreshMs={1000} />);
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
  expect(loadTasks).toHaveBeenCalledTimes(1);

  await act(async () => {
    vi.advanceTimersByTime(1000);
    await Promise.resolve();
    await Promise.resolve();
  });
  expect(loadTasks).toHaveBeenCalledTimes(2);
  vi.useRealTimers();
});

test("overdue tasks are marked and available in the attention filter", async () => {
  const overdue = new Date(Date.now() - 15 * 60_000).toISOString();
  const loadTasks = vi.fn().mockResolvedValue([
    task("overdue", { title: "超时任务", due_at: overdue, priority: "high" }),
    task("normal", { title: "普通任务", due_at: new Date(Date.now() + 2 * 60 * 60_000).toISOString() })
  ]);

  render(<OpsTaskPanel loadTasks={loadTasks} refreshMs={0} />);
  await screen.findByText("超时任务");

  expect(screen.getByText("已超时")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /需关注/ }));
  expect(screen.getByText("超时任务")).toBeInTheDocument();
  expect(screen.queryByText("普通任务")).not.toBeInTheDocument();
});
