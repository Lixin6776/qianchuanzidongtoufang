import { useEffect, useState } from "react";

import {
  createMaterialExperiment,
  evaluateMaterialExperiment,
  getMaterialAnalyses,
  getMaterialExperiments,
  startMaterialExperiment,
  stopMaterialExperiment
} from "../lib/api";

type MaterialAction = {
  key: string;
  material_id: string;
  material_name: string;
  action_type: string;
  title: string;
  reason: string;
  baseline: Record<string, unknown>;
  success_criteria: Record<string, unknown>;
  stop_condition: string;
};

type Analysis = { id: string; date: string; material_actions?: MaterialAction[] };
type Experiment = {
  id: string;
  analysis_id: string;
  analysis_date: string;
  material_id: string;
  material_name: string;
  action_type: string;
  title: string;
  reason: string;
  baseline_metrics: Record<string, unknown>;
  success_criteria: Record<string, unknown>;
  stop_condition: string;
  status: string;
  observation_started_at?: string | null;
  observation_ends_at?: string | null;
  result: Record<string, unknown>;
  created_at: string;
};

const STATUS_LABEL: Record<string, string> = {
  suggested: "待开始",
  observing: "观察中",
  insufficient: "数据不足",
  completed: "已完成",
  stopped: "已停止"
};
const VERDICT_LABEL: Record<string, string> = {
  positive: "正向",
  negative: "负向",
  neutral: "中性",
  insufficient_data: "样本不足"
};

function MaterialActionCard({ action, analysis, onCreate }: { action: MaterialAction; analysis: Analysis; onCreate: (analysis: Analysis, action: MaterialAction) => void }) {
  return (
    <article className="strategy-card material-action-card">
      <header><div><strong>{action.title}</strong><span className="monitor-signal">{action.material_name || action.material_id}</span></div><span className="verdict-badge verdict-proposed">建议</span></header>
      <p className="monitor-signal">{action.reason}</p>
      <div className="execution-meta"><span>素材 {action.material_id}</span><span>基线 ROI {String(action.baseline?.roi ?? "--")}</span><span>样本消耗 ¥{String(action.baseline?.spend ?? "--")}</span></div>
      <p className="monitor-signal">停止条件：{action.stop_condition}</p>
      <div className="strategy-actions"><button className="button-primary" type="button" onClick={() => onCreate(analysis, action)}>创建素材实验</button></div>
    </article>
  );
}

export function MaterialExperimentPanel() {
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [reasons, setReasons] = useState<Record<string, string>>({});

  async function refresh() {
    const [nextAnalyses, nextExperiments] = await Promise.all([getMaterialAnalyses(), getMaterialExperiments()]);
    setAnalyses(nextAnalyses as Analysis[]);
    setExperiments(nextExperiments as Experiment[]);
  }

  useEffect(() => {
    let active = true;
    refresh().catch(() => { if (active) setError("素材实验读取失败，请检查本地服务。"); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  async function run(id: string, action: () => Promise<unknown>) {
    setBusy(id); setError("");
    try { await action(); await refresh(); }
    catch { setError("素材实验操作失败，请确认当前状态和本地服务。 "); }
    finally { setBusy(null); }
  }

  async function create(analysis: Analysis, action: MaterialAction) {
    await run(action.key, () => createMaterialExperiment({
      analysis_id: analysis.id, analysis_date: analysis.date, material_id: action.material_id,
      material_name: action.material_name, action_type: action.action_type, title: action.title,
      reason: action.reason, baseline_metrics: action.baseline, success_criteria: action.success_criteria,
      stop_condition: action.stop_condition
    }));
  }

  if (loading) return <div className="module-loading"><span className="module-spinner" aria-hidden="true" />正在读取素材实验…</div>;
  if (error) return <div className="module-error">{error}</div>;

  const latest = analyses[0];
  const actions = latest?.material_actions ?? [];
  return (
    <div className="module-stack">
      <p className="monitor-signal">素材实验只记录人工动作和结果，不会自动修改素材、预算或计划。评估使用下一份素材分析快照。</p>
      {actions.length ? (
        <section className="module-stack">
          <h3>来自最新分析的素材动作建议</h3>
          <div className="strategy-list">{actions.map((action) => <MaterialActionCard key={action.key} action={action} analysis={latest} onCreate={(a, item) => void create(a, item)} />)}</div>
        </section>
      ) : <div className="module-empty-state"><strong>暂无结构化素材动作</strong><span>生成一份新格式素材分析后，这里会出现可创建实验的动作建议。</span></div>}

      <section className="module-stack">
        <h3>素材实验记录</h3>
        {experiments.length ? (
          <div className="strategy-list">
            {experiments.map((item) => {
              const verdict = String(item.result?.verdict ?? "");
              const reason = reasons[item.id] ?? "";
              return (
                <article className="strategy-card" key={item.id}>
                  <header><div><strong>{item.title}</strong><span className="monitor-signal">{item.material_name || item.material_id}</span></div><span className={`verdict-badge verdict-${item.status}`}>{STATUS_LABEL[item.status] ?? item.status}</span></header>
                  <p className="monitor-signal">{item.reason}</p>
                  <div className="execution-meta"><span>分析日期 {item.analysis_date}</span><span>动作 {item.action_type}</span>{item.observation_started_at ? <span>开始 {new Date(item.observation_started_at).toLocaleString("zh-CN")}</span> : null}</div>
                  {verdict ? <div className="strategy-evaluation"><strong>结果：{VERDICT_LABEL[verdict] ?? verdict}</strong><p className="monitor-signal">观察性相关，不是因果；评估只基于下一份素材快照。</p></div> : null}
                  <div className="strategy-actions">
                    {item.status === "suggested" || item.status === "insufficient" ? <button className="button-primary" disabled={busy === item.id} onClick={() => void run(item.id, () => startMaterialExperiment(item.id))}>开始观察</button> : null}
                    {item.status === "observing" || item.status === "insufficient" ? <button className="button-outline" disabled={busy === item.id} onClick={() => void run(item.id, () => evaluateMaterialExperiment(item.id))}>评估最新快照</button> : null}
                    {item.status === "observing" || item.status === "suggested" ? <><input className="decision-input" value={reason} onChange={(event) => setReasons((current) => ({ ...current, [item.id]: event.target.value }))} placeholder="停止原因（可选）" aria-label={`${item.title} 停止原因`} /><button className="button-outline" disabled={busy === item.id} onClick={() => void run(item.id, () => stopMaterialExperiment(item.id, reason))}>停止实验</button></> : null}
                  </div>
                </article>
              );
            })}
          </div>
        ) : <div className="module-empty-state"><strong>还没有素材实验</strong><span>从上方动作建议创建实验，人工开始后再评估。</span></div>}
      </section>
    </div>
  );
}
