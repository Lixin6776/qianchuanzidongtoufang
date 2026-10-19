import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

vi.mock("../lib/api", () => ({
  getOpsOutcome: vi.fn().mockResolvedValue({
    generated_at: "2026-10-19T08:10:00+08:00",
    window_minutes: 10,
    min_sample: 20,
    baseline: { n: 346, median_delta: -0.098, positive_rate: 0.48, net_effect: 0 },
    treated: { n: 243, median_delta: 0.056, positive_rate: 0.55, net_effect: 0.154 },
    operations: [
      { operation: "加素材", n: 25, median_delta: 0.5, positive_rate: 0.68, net_effect: 0.53, verdict: "positive" }
    ],
    velocity_strata: [
      { label: "中", treated: { n: 78 }, control: { n: 119 }, net_effect: 0.31, verdict: "positive" }
    ],
    note: "观察性相关，不是因果。"
  }),
  getOpsOutcomeSnapshots: vi.fn().mockResolvedValue([])
}));

import { DataAssetPanel } from "../components/DataAssetPanel";

test("数据资产窗口：展示操作反馈 + 流速分层 + 因果声明", async () => {
  render(<DataAssetPanel />);

  expect(screen.getByText("数据资产")).toBeInTheDocument();
  expect(await screen.findByText("操作反馈表（近 10 分钟）")).toBeInTheDocument();
  expect(screen.getByText("按流速分层（更有用的切法）")).toBeInTheDocument();
  expect(screen.getByText("加素材")).toBeInTheDocument();
  // 必须一直带着"非因果"的护栏
  expect(screen.getAllByText(/不是因果|观察性相关/).length).toBeGreaterThan(0);
});
