import { useEffect, useState } from "react";

import { getOpsOutcomeCases, getOpsOutcomeOverview, getOpsScenarios, opsCasesCsvUrl } from "../lib/api";
import { ExecutionFeedbackPanel } from "./ExecutionFeedbackPanel";
import { StrategyLifecyclePanel } from "./StrategyLifecyclePanel";
import { MaterialExperimentPanel } from "./MaterialExperimentPanel";
import { OpsTaskPanel } from "./OpsTaskPanel";
import { OpsOutcomePanel } from "./OpsOutcomePanel";

type ScenarioOp = {
  operation: string;
  n: number;
  median_delta: number | null;
  net_effect: number | null;
  verdict: string;
};
type Scenario = {
  label: string;
  control: { n: number; median_delta: number | null };
  operations: ScenarioOp[];
};
type ScenarioPayload = {
  scenarios: Scenario[];
  velocity_cutoffs?: { low: number; high: number };
  min_sample: number;
  note: string;
};

type Overview = {
  asset_days: number;
  span: { start: string; end: string };
  watch_reports: number;
  operation_events: number;
  operation_types: number;
  conclusions: number;
  reviews: number;
  analyses: number;
  health: {
    last_24h_total: number;
    last_24h_valid: number;
    valid_rate: number | null;
    cdp_errors: number;
  };
};

type AssetTab = "overview" | "feedback" | "scenarios" | "cases" | "strategies" | "execution" | "materials" | "tasks";

const TABS: Array<{ id: AssetTab; label: string }> = [
  { id: "overview", label: "概览" },
  { id: "feedback", label: "操作反馈" },
  { id: "scenarios", label: "决策场景" },
  { id: "cases", label: "操作流水" },
  { id: "strategies", label: "策略建议" },
  { id: "execution", label: "执行回流" },
  { id: "materials", label: "素材实验" },
  { id: "tasks", label: "运营任务" }
];

const VERDICT_LABEL: Record<string, string> = {
  positive: "正向",
  negative: "负向",
  neutral: "中性",
  insufficient: "样本不足",
  flat: "持平",
  unknown: "数据不足"
};

function Verdict({ value }: { value: string }) {
  return <span className={`verdict-badge verdict-${value}`}>{VERDICT_LABEL[value] ?? value}</span>;
}

/**
 * 数据资产：数据证明了什么。
 *
 * 和「决策」分工：
 *   决策   = 我定的规则（阈值 / 策略 / ROI 目标）
 *   数据资产 = 本账户实测出来的证据（哪些操作被正向反馈、在什么流速下有效）
 */
export function DataAssetPanel() {
  const [tab, setTab] = useState<AssetTab>("overview");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [scenarios, setScenarios] = useState<ScenarioPayload | null>(null);
  const [scenariosLoading, setScenariosLoading] = useState(false);
  const [scenariosLoaded, setScenariosLoaded] = useState(false);
  const [cases, setCases] = useState<Array<Record<string, unknown>>>([]);
  const [casesLoading, setCasesLoading] = useState(false);
  const [casesLoaded, setCasesLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    setOverviewLoading(true);
    getOpsOutcomeOverview()
      .then((value) => {
        if (active) setOverview(value as Overview);
      })
      .catch(() => {
        if (active) setOverview(null);
      })
      .finally(() => {
        if (active) setOverviewLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (tab !== "scenarios" || scenariosLoaded || scenariosLoading) return;
    let active = true;
    setScenariosLoading(true);
    getOpsScenarios()
      .then((value) => {
        if (active) setScenarios(value as ScenarioPayload);
      })
      .catch(() => {
        if (active) setScenarios(null);
      })
      .finally(() => {
        if (!active) return;
        setScenariosLoading(false);
        setScenariosLoaded(true);
      });
    return () => {
      active = false;
    };
  }, [tab]);

  useEffect(() => {
    if (tab !== "cases" || casesLoaded || casesLoading) return;
    let active = true;
    setCasesLoading(true);
    getOpsOutcomeCases(100)
      .then((value) => {
        if (active) setCases(value as Array<Record<string, unknown>>);
      })
      .catch(() => {
        if (active) setCases([]);
      })
      .finally(() => {
        if (!active) return;
        setCasesLoading(false);
        setCasesLoaded(true);
      });
    return () => {
      active = false;
    };
  }, [tab]);

  return (
    <section className="panel data-asset-panel">
      <div className="module-toolbar">
        <div>
          <strong>数据证明了什么</strong>
          <span>本账户实测：哪些操作有正向反馈、在什么流速下更有效、结论是否在变稳。</span>
        </div>
      </div>

      <div className="module-tabs" role="tablist" aria-label="数据资产视图">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={tab === item.id ? "active" : ""}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "overview" ? (
        <div className="module-stack" role="tabpanel">
          {overviewLoading ? (
            <div className="module-loading" role="status">
              <span className="module-spinner" aria-hidden="true" />
              正在计算数据资产概览…
            </div>
          ) : null}
          {overview ? (
            <>
              <div className="asset-overview-grid">
                <div className="asset-card"><span>资产年龄</span><strong>{overview.asset_days} 天</strong></div>
                <div className="asset-card"><span>盯盘记录</span><strong>{overview.watch_reports.toLocaleString()} 条</strong></div>
                <div className="asset-card"><span>操作笔数</span><strong>{overview.operation_events} 笔</strong></div>
                <div className="asset-card"><span>已下结论</span><strong>{overview.conclusions} 类</strong></div>
              </div>
              <div className="asset-meta-grid">
                <p className="monitor-signal">数据跨度：{overview.span.start} ~ {overview.span.end}</p>
                <p className="monitor-signal">复盘 {overview.reviews} 份 · 素材分析 {overview.analyses} 份 · 操作类型 {overview.operation_types} 种</p>
                <p className="monitor-signal">
                  最近 24h 有效 <strong>{overview.health.last_24h_valid}</strong>/{overview.health.last_24h_total}
                  {overview.health.valid_rate !== null ? `（${Math.round(overview.health.valid_rate * 100)}%）` : ""}
                  {" · "}累计 CDP 失败 {overview.health.cdp_errors} 次
                </p>
              </div>
              <p className="monitor-signal">所有结论都是观察性相关，不是因果；样本少于一类的门槛时只标“样本不足”，不给方向。</p>
            </>
          ) : !overviewLoading ? (
            <div className="module-error"><strong>数据资产概览读取失败，请检查本地服务。</strong></div>
          ) : null}
        </div>
      ) : null}

      {tab === "feedback" ? (
        <div role="tabpanel" className="module-tab-panel">
          <OpsOutcomePanel />
        </div>
      ) : null}

      {tab === "scenarios" ? (
        <div className="module-stack" role="tabpanel">
          {scenariosLoading ? <div className="module-loading"><span className="module-spinner" aria-hidden="true" />正在计算决策场景…</div> : null}
          {scenarios?.scenarios?.length ? (
            <>
              <p className="monitor-signal">
                按流速分档（偏低 &lt; {scenarios.velocity_cutoffs?.low ?? "--"} ｜ 加快 ≥ {scenarios.velocity_cutoffs?.high ?? "--"} ¥/分钟），各档内比“有操作 vs 无操作”。
              </p>
              <div className="asset-scenarios">
                {scenarios.scenarios.map((scenario) => (
                  <section className="asset-scenario-card" key={scenario.label}>
                    <header>
                      <strong>{scenario.label}</strong>
                      <span className="monitor-signal">对照 n={scenario.control.n} · 基准 {scenario.control.median_delta === null ? "--" : scenario.control.median_delta.toFixed(2)}</span>
                    </header>
                    <table>
                      <thead><tr><th>操作</th><th>n</th><th>净效应</th><th>判定</th></tr></thead>
                      <tbody>
                        {scenario.operations.map((op) => (
                          <tr key={op.operation}>
                            <td>{op.operation}</td><td>{op.n}</td>
                            <td>{op.net_effect === null ? "--" : `${op.net_effect > 0 ? "+" : ""}${op.net_effect.toFixed(2)}`}</td>
                            <td><Verdict value={op.verdict} /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </section>
                ))}
              </div>
              <p className="monitor-signal">{scenarios.note}</p>
            </>
          ) : !scenariosLoading && scenariosLoaded ? (
            <div className="module-empty-state"><strong>暂无决策场景结论</strong><span>继续积累同场景操作样本后再判断。</span></div>
          ) : null}
        </div>
      ) : null}

      {tab === "strategies" ? (
        <div className="module-tab-panel" role="tabpanel">
          <StrategyLifecyclePanel />
        </div>
      ) : null}

      {tab === "execution" ? (
        <div className="module-tab-panel" role="tabpanel">
          <ExecutionFeedbackPanel />
        </div>
      ) : null}

      {tab === "materials" ? (
        <div className="module-tab-panel" role="tabpanel">
          <MaterialExperimentPanel />
        </div>
      ) : null}

      {tab === "tasks" ? (
        <div className="module-tab-panel" role="tabpanel">
          <OpsTaskPanel />
        </div>
      ) : null}

      {tab === "cases" ? (
        <div className="module-stack" role="tabpanel">
          <div className="module-toolbar">
            <div><strong>操作流水</strong><span>原始凭证：每笔操作 + 操作前 / 10 分钟后 / 20 分钟后的边际 ROI。</span></div>
            <a className="button-outline" href={opsCasesCsvUrl()} download>导出 CSV</a>
          </div>
          {casesLoading ? <div className="module-loading"><span className="module-spinner" aria-hidden="true" />正在计算操作流水…</div> : null}
          {cases.length ? (
            <table>
              <thead><tr><th>时间</th><th>操作</th><th>任务 / 素材</th><th>预算 / ROI目标</th><th>操作前 ROI</th><th>10 分钟后</th><th>20 分钟后</th><th>10 分 Δ</th><th>判定</th></tr></thead>
              <tbody>
                {cases.slice(0, 30).map((row, index) => (
                  <tr key={`${row.at}-${index}`}>
                    <td>{String(row.at ?? "")}</td><td>{String(row.operation ?? "")}</td>
                    <td>{String(row.material_name ?? "") || String(row.task_name ?? "") || "--"}{row.material_id ? <div className="monitor-signal">素材ID {String(row.material_id)}</div> : null}</td>
                    <td>{row.budget === null || row.budget === undefined ? "--" : `¥${Number(row.budget).toLocaleString()}`}{row.roi_target !== null && row.roi_target !== undefined ? ` / ROI ${Number(row.roi_target).toFixed(2)}` : ""}</td>
                    <td>{row.before_roi === null ? "--" : Number(row.before_roi).toFixed(2)}</td><td>{row.after_10m_roi === null ? "--" : Number(row.after_10m_roi).toFixed(2)}</td><td>{row.after_20m_roi === null ? "--" : Number(row.after_20m_roi).toFixed(2)}</td>
                    <td>{row.delta_10m === null ? "--" : `${Number(row.delta_10m) > 0 ? "+" : ""}${Number(row.delta_10m).toFixed(2)}`}</td>
                    <td><Verdict value={String(row.verdict ?? "unknown")} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : !casesLoading && casesLoaded ? (
            <div className="module-empty-state"><strong>还没有可追溯的操作流水</strong><span>需要千川日志中的真实操作记录。</span></div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
