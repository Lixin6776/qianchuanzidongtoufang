import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

vi.mock("../lib/api", () => ({
  getOpsAssetDashboard: vi.fn().mockResolvedValue({
    overview: {
      asset_days: 12,
      span: { start: "2026-10-07", end: "2026-10-19" },
      watch_reports: 2431,
      operation_events: 412,
      operation_types: 10,
      conclusions: 3,
      reviews: 13,
      analyses: 16,
      health: { last_24h_total: 280, last_24h_valid: 245, valid_rate: 0.875, cdp_errors: 3 }
    },
    scenarios: {
      scenarios: [
        {
          label: "流速加快",
          control: { n: 131, median_delta: 0.083 },
          operations: [
            { operation: "加追投预算", n: 34, median_delta: -0.0001, net_effect: -0.0001, verdict: "neutral" }
          ]
        }
      ],
      velocity_cutoffs: { low: 75.3, high: 132.3 },
      min_sample: 20,
      note: "观察性相关，不是因果。"
    },
    cases: [
      { at: "2026-10-19 12:23", operation: "加追投预算", before_roi: 2.44, after_10m_roi: 1.83, after_20m_roi: null, delta_10m: -0.61, verdict: "negative" }
    ],
    outcome: {
      generated_at: "2026-10-19T08:10:00+08:00",
      window_minutes: 10,
      min_sample: 20,
      baseline: { n: 346, median_delta: -0.098, positive_rate: 0.48, net_effect: 0, operation: "（基线）" },
      treated: { n: 243, median_delta: 0.056, positive_rate: 0.55, net_effect: 0.154 },
      operations: [
        { operation: "加素材", n: 25, median_delta: 0.5, positive_rate: 0.68, net_effect: 0.53, verdict: "positive" }
      ],
      velocity_strata: [
        { label: "中", treated: { n: 78 }, control: { n: 119 }, net_effect: 0.31, verdict: "positive" }
      ],
      note: "观察性相关，不是因果。"
    }
  }),
  getOpsScenarios: vi.fn().mockResolvedValue({
    scenarios: [
      {
        label: "流速加快",
        control: { n: 131, median_delta: 0.083 },
        operations: [
          { operation: "加追投预算", n: 34, median_delta: -0.0001, net_effect: -0.0001, verdict: "neutral" }
        ]
      }
    ],
    velocity_cutoffs: { low: 75.3, high: 132.3 },
    min_sample: 20,
    note: "观察性相关，不是因果。"
  }),
  getOpsOutcomeCases: vi.fn().mockResolvedValue([
    { at: "2026-10-19 12:23", operation: "加追投预算", before_roi: 2.44, after_10m_roi: 1.83, after_20m_roi: null, delta_10m: -0.61, verdict: "negative" }
  ]),
  opsCasesCsvUrl: () => "http://127.0.0.1:8000/api/ops-outcome/cases.csv",
  getOpsOutcomeOverview: vi.fn().mockResolvedValue({
    asset_days: 12,
    span: { start: "2026-10-07", end: "2026-10-19" },
    watch_reports: 2431,
    operation_events: 412,
    operation_types: 10,
    conclusions: 3,
    reviews: 13,
    analyses: 16,
    health: { last_24h_total: 280, last_24h_valid: 245, valid_rate: 0.875, cdp_errors: 3 }
  }),
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
  getOpsOutcomeSnapshots: vi.fn().mockResolvedValue([]),
  getLearningSuggestions: vi.fn().mockResolvedValue([
    {
      id: "s1",
      strategy_profile_version: 1,
      suggestion_type: "阈值调整",
      proposed_change: { roi_floor_delta: 0.1 },
      evidence: { sample_size: 24 },
      confidence: "high",
      status: "proposed",
      created_at: "2026-10-29T08:00:00+08:00"
    }
  ]),
  getLearningEvaluations: vi.fn().mockResolvedValue([]),
  activateLearningSuggestion: vi.fn().mockResolvedValue({}),
  evaluateLearningSuggestion: vi.fn().mockResolvedValue({}),
  keepLearningSuggestion: vi.fn().mockResolvedValue({}),
  rollbackLearningSuggestion: vi.fn().mockResolvedValue({}),
  decideLearningSuggestion: vi.fn().mockResolvedValue({}),
  getMaterialAnalyses: vi.fn().mockResolvedValue([
    {
      id: "ma1",
      date: "2026-10-29",
      material_actions: [
        {
          key: "m1:replicate_winner",
          material_id: "m1",
          material_name: "高 ROI 素材",
          action_type: "replicate_winner",
          title: "复刻高 ROI 素材",
          reason: "ROI 达标",
          baseline: { roi: 3.2, spend: 3000 },
          success_criteria: { roi_min: 2.5 },
          stop_condition: "ROI 低于基线"
        }
      ]
    }
  ]),
  getMaterialExperiments: vi.fn().mockResolvedValue([]),
  createMaterialExperiment: vi.fn().mockResolvedValue({}),
  startMaterialExperiment: vi.fn().mockResolvedValue({}),
  evaluateMaterialExperiment: vi.fn().mockResolvedValue({}),
  stopMaterialExperiment: vi.fn().mockResolvedValue({}),
  getOpsTasks: vi.fn().mockResolvedValue([]),
  createOpsTask: vi.fn().mockResolvedValue({}),
  updateOpsTask: vi.fn().mockResolvedValue({}),
  getExecutionFeedback: vi.fn().mockResolvedValue([
    {
      execution_job_id: "job-12345678",
      confirmation_id: "confirm-12345678",
      action_name: "pause_plan",
      status: "succeeded",
      created_at: "2026-10-29T08:00:00+08:00",
      before: { status: "active" },
      after: { status: "paused" },
      platform_log_status: "待回流",
      link_status: "candidate",
      linked_operation: { at: "2026-10-29 08:04", operation: "暂停追投", verdict: "negative", delta_10m: -0.2 }
    }
  ])
}));

import { DataAssetPanel } from "../components/DataAssetPanel";

test("数据资产窗口：展示操作反馈 + 流速分层 + 因果声明", async () => {
  render(<DataAssetPanel />);

  expect(screen.getByText("数据证明了什么")).toBeInTheDocument();
  expect(await screen.findByText("资产年龄")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("tab", { name: "操作反馈" }));
  expect(await screen.findByText("操作反馈表（近 10 分钟）")).toBeInTheDocument();
  expect(screen.getByText("按流速分层（更有用的切法）")).toBeInTheDocument();
  expect(screen.getByText("加素材")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("tab", { name: "决策场景" }));
  expect(await screen.findByText("流速加快")).toBeInTheDocument();

  expect(screen.getAllByText(/不是因果|观察性相关/).length).toBeGreaterThan(0);

  fireEvent.click(screen.getByRole("tab", { name: "策略建议" }));
  expect(await screen.findByText("阈值调整")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "执行回流" }));
  expect(await screen.findByText("候选关联")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "素材实验" }));
  expect(await screen.findByText("复刻高 ROI 素材")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "运营任务" }));
  expect(await screen.findByText("新建运营任务")).toBeInTheDocument();
});
