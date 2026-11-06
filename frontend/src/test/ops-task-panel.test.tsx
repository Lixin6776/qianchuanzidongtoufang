import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { OpsTaskPanel } from "../components/OpsTaskPanel";

test("ops task panel shows 10 and 30 minute verification evidence", async () => {
  const loadTasks = vi.fn().mockResolvedValue([
    {
      id: "task-1",
      title: "执行：先收缩低效素材",
      description: "问题：ROI 未达标",
      owner: "当前投手",
      priority: "high",
      status: "in_progress",
      success_criteria: "10 分钟内 ROI 改善 0.10",
      stop_condition: "数据质量非可信时停止",
      result: "",
      created_at: "2026-11-06T08:00:00+00:00",
      source_type: "live_watch",
      source_id: "watch-1",
      context: {},
      verification: {
        status: "ready",
        suggested_verdict: "success",
        focus_metric: "roi",
        message: "10 分钟 ROI 2.15（+0.15）→ 建议保留动作",
        window_10m: { target_minutes: 10, observed_at: "2026-11-06T08:10:00+00:00", value: 2.15, delta: 0.15 },
        window_30m: { target_minutes: 30, observed_at: "2026-11-06T08:30:00+00:00", value: 2.2, delta: 0.2 }
      }
    }
  ]);

  render(<OpsTaskPanel loadTasks={loadTasks} />);

  expect(await screen.findByText("10 分钟：ROI 2.15（+0.15）")).toBeInTheDocument();
  expect(screen.getByText("30 分钟：ROI 2.20（+0.20）")).toBeInTheDocument();
  expect(screen.getByText(/建议保留动作/)).toBeInTheDocument();
});
