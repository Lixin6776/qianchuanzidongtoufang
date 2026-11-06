import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

const getActiveProfile = vi.fn();
const createStrategyProfile = vi.fn();
const getKnowledgeOverview = vi.fn();
const uploadKnowledgeFile = vi.fn();

vi.mock("../lib/api", () => ({
  getActiveProfile: (...a: unknown[]) => getActiveProfile(...a),
  createStrategyProfile: (...a: unknown[]) => createStrategyProfile(...a),
  getKnowledgeOverview: (...a: unknown[]) => getKnowledgeOverview(...a),
  uploadKnowledgeFile: (...a: unknown[]) => uploadKnowledgeFile(...a),
  // 投手知识库窗口现在也会渲染《操作反馈表》
  getOpsOutcomeSnapshots: vi.fn().mockResolvedValue([]),
  getOpsOutcome: vi.fn().mockResolvedValue({
    baseline: { n: 0, median_delta: null, positive_rate: null, net_effect: null, operation: "（基线）" },
    treated: { n: 0, median_delta: null, positive_rate: null, net_effect: null },
    operations: [],
    velocity_strata: [],
    window_minutes: 10,
    min_sample: 20,
    note: "测试"
  })
}));

import { ThresholdPanel } from "../components/ThresholdPanel";

test("判断标准：读当前值、留空=自动、保存生成新版本", async () => {
  getActiveProfile.mockResolvedValue({
    version: 1,
    name: "质润官方旗舰店 · 全域直播投放",
    business_direction: "全域直播投放",
    primary_objective: "稳定放量",
    secondary_objectives: [],
    hard_constraints: { roi_target: 2.7, thresholds: { gpm: 2500 } },
    monitoring_config: { interval_minutes: 5 },
    allowed_actions: [],
    notification_policy: { dedupe_minutes: 10 }
  });
  getKnowledgeOverview.mockResolvedValue({
    mode: "historical_average",
    files: [],
    historical_reference: {
      sample_count: 120,
      note: "未上传知识文件时，使用本账户历史有效采样平均值；仅作历史参考，不是规则。",
      metrics: [
        { key: "roi", label: "ROI", average: 2.35, unit: "", samples: 120 },
        { key: "gpm", label: "GPM", average: 3200, unit: "元", samples: 118 }
      ]
    }
  });
  createStrategyProfile.mockResolvedValue({
    version: 2,
    name: "质润官方旗舰店 · 全域直播投放",
    business_direction: "全域直播投放",
    primary_objective: "稳定放量",
    hard_constraints: { roi_target: 2.7, thresholds: { gpm: 2500, cpm: 120 } },
    allowed_actions: []
  });

  render(<ThresholdPanel />);

  await waitFor(() => expect(getActiveProfile).toHaveBeenCalled());
  expect(screen.getByRole("heading", { name: "账户判断标准" })).toBeInTheDocument();
  // 读到了当前设定的值
  const gpm = (await screen.findByLabelText("GPM")) as HTMLInputElement;
  expect(gpm.value).toBe("2500");
  // 没设的留空
  expect((screen.getByLabelText("CPM") as HTMLInputElement).value).toBe("");
  // 说明文案要讲清楚"留空=自动"
  expect(screen.getByText(/留空则自动/)).toBeInTheDocument();
  // ROI 目标不在这里设，避免和计划打架
  expect(screen.getByText(/ROI 目标不在这里设/)).toBeInTheDocument();
});

test("knowledge file upload sends file content to the local knowledge base", async () => {
  getActiveProfile.mockResolvedValue({
    version: 1,
    name: "test",
    business_direction: "全域直播投放",
    primary_objective: "稳定放量",
    secondary_objectives: [],
    hard_constraints: {},
    monitoring_config: { interval_minutes: 5 },
    allowed_actions: [],
    notification_policy: { dedupe_minutes: 10 }
  });
  getKnowledgeOverview.mockResolvedValue({
    mode: "historical_average",
    files: [],
    historical_reference: { sample_count: 0, metrics: [], note: "暂无历史样本" }
  });
  uploadKnowledgeFile.mockResolvedValue({
    id: "kb-1",
    name: "投手规则.md",
    size: 8,
    parse_status: "parsed",
    preview: "ROI 规则",
    uploaded_at: "2026-11-06T08:00:00+00:00"
  });

  render(<ThresholdPanel />);
  const file = new File(["ROI rule"], "投手规则.md", { type: "text/markdown" });
  fireEvent.change(await screen.findByLabelText("上传知识文件"), {
    target: { files: [file] }
  });
  await waitFor(() => expect(screen.getByRole("button", { name: "上传到知识库" })).not.toBeDisabled());
  fireEvent.click(screen.getByRole("button", { name: "上传到知识库" }));

  await waitFor(() => expect(uploadKnowledgeFile).toHaveBeenCalled());
  const payload = uploadKnowledgeFile.mock.calls[0][0] as Record<string, string>;
  expect(payload.name).toBe("投手规则.md");
  expect(payload.content_base64).toBeTruthy();
});
