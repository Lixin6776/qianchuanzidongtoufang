import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

// 注意：vi.mock 会被提升到文件顶部，工厂里不能引用外部变量 —— payload 必须写在工厂内部。
vi.mock("../lib/api", () => {
  const payload = {
    generated_at: "2026-10-19T08:10:00+08:00",
    window_minutes: 10,
    min_sample: 20,
    baseline: { n: 346, median_delta: -0.098, positive_rate: 0.48, net_effect: 0 },
    treated: { n: 243, median_delta: 0.056, positive_rate: 0.55, net_effect: 0.154 },
    operations: [
      { operation: "加素材", n: 25, median_delta: 0.5, positive_rate: 0.68, net_effect: 0.53, verdict: "positive" }
    ],
    velocity_strata: [],
    note: "观察性相关，不是因果。"
  };
  return {
    getOpsOutcome: vi.fn().mockResolvedValue(payload),
    getOpsOutcomeSnapshots: vi.fn().mockResolvedValue([
      { date: "2026-10-18", snapshot: { ...payload, operations: [{ ...payload.operations[0], net_effect: 0.45 }] } },
      { date: "2026-10-19", snapshot: payload }
    ])
  };
});

import { OpsOutcomePanel } from "../components/OpsOutcomePanel";

test("资产趋势图：有 2 份快照时渲染折线", async () => {
  render(<OpsOutcomePanel />);
  expect(await screen.findByLabelText("资产趋势折线图")).toBeInTheDocument();
  expect(screen.getByText(/纵轴 = 净效应/)).toBeInTheDocument();
});
