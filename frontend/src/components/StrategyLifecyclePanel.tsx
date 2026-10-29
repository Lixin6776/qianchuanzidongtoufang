import { useEffect, useState } from "react";

import {
  activateLearningSuggestion,
  decideLearningSuggestion,
  evaluateLearningSuggestion,
  getLearningEvaluations,
  getLearningSuggestions,
  keepLearningSuggestion,
  rollbackLearningSuggestion
} from "../lib/api";

type Suggestion = {
  id: string;
  strategy_profile_version: number;
  suggestion_type: string;
  proposed_change: Record<string, unknown>;
  evidence: Record<string, unknown>;
  confidence: string;
  status: string;
  draft_profile_id?: string | null;
  activated_profile_id?: string | null;
  evaluation_id?: string | null;
  decided_at?: string | null;
  created_at: string;
};

type Evaluation = {
  id: string;
  sample_size: number;
  effect_size: number | null;
  confidence: string;
  verdict: string;
  evidence: Record<string, unknown>;
  window_start?: string | null;
  window_end?: string | null;
};

const STATUS_LABEL: Record<string, string> = {
  proposed: "待决策",
  accepted: "已生成草案",
  active: "观察中",
  evaluated: "已评估",
  kept: "已保留",
  rolled_back: "已回滚",
  rejected: "已拒绝"
};

const VERDICT_LABEL: Record<string, string> = {
  positive: "正向",
  negative: "负向",
  neutral: "中性",
  insufficient_data: "样本不足",
  beneficial: "正向",
  harmful: "负向"
};

function ChangeList({ value }: { value: Record<string, unknown> }) {
  const entries = Object.entries(value ?? {});
  if (!entries.length) return <span className="monitor-signal">无可展示变更</span>;
  return (
    <dl className="strategy-change-list">
      {entries.map(([key, item]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{typeof item === "object" ? JSON.stringify(item) : String(item)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function StrategyLifecyclePanel() {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [reasons, setReasons] = useState<Record<string, string>>({});

  async function refresh() {
    const [nextSuggestions, nextEvaluations] = await Promise.all([
      getLearningSuggestions(),
      getLearningEvaluations()
    ]);
    setSuggestions(nextSuggestions as Suggestion[]);
    setEvaluations(nextEvaluations as Evaluation[]);
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    refresh()
      .catch(() => {
        if (active) setError("策略建议读取失败，请检查本地服务。");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function runAction(id: string, action: () => Promise<unknown>) {
    setBusyId(id);
    setError("");
    try {
      await action();
      await refresh();
    } catch {
      setError("操作失败，请确认当前状态和本地服务。 ");
    } finally {
      setBusyId(null);
    }
  }

  if (loading) {
    return <div className="module-loading"><span className="module-spinner" aria-hidden="true" />正在读取策略建议…</div>;
  }

  if (!suggestions.length) {
    return (
      <div className="module-empty-state">
        <strong>暂无策略建议</strong>
        <span>当数据资产积累到足够样本后，策略建议会出现在这里。</span>
      </div>
    );
  }

  return (
    <div className="module-stack">
      {error ? <div className="module-error">{error}</div> : null}
      <div className="strategy-list">
        {suggestions.map((suggestion) => {
          const evaluation = evaluations.find((item) => item.id === suggestion.evaluation_id);
          const reason = reasons[suggestion.id] ?? "";
          const busy = busyId === suggestion.id;
          return (
            <article className="strategy-card" key={suggestion.id}>
              <header>
                <div>
                  <strong>{suggestion.suggestion_type}</strong>
                  <span className="monitor-signal">基于策略 v{suggestion.strategy_profile_version} · 置信度 {suggestion.confidence}</span>
                </div>
                <span className={`verdict-badge verdict-${suggestion.status}`}>{STATUS_LABEL[suggestion.status] ?? suggestion.status}</span>
              </header>
              <ChangeList value={suggestion.proposed_change} />
              <p className="monitor-signal">证据样本：{String(suggestion.evidence?.sample_size ?? "未提供")} · 创建于 {new Date(suggestion.created_at).toLocaleString("zh-CN")}</p>
              {evaluation ? (
                <section className="strategy-evaluation">
                  <div><strong>评估结果：{VERDICT_LABEL[evaluation.verdict] ?? evaluation.verdict}</strong><span>样本 {evaluation.sample_size} · 效果值 {evaluation.effect_size === null ? "--" : evaluation.effect_size.toFixed(2)}</span></div>
                  <p>观察窗口：{evaluation.window_start ? new Date(evaluation.window_start).toLocaleString("zh-CN") : "--"} 至 {evaluation.window_end ? new Date(evaluation.window_end).toLocaleString("zh-CN") : "--"}</p>
                  <p className="monitor-signal">观察性相关，不是因果；样本不足时不给方向。</p>
                </section>
              ) : null}
              <div className="strategy-actions">
                {suggestion.status === "proposed" ? <>
                  <input className="decision-input" value={reason} onChange={(event) => setReasons((current) => ({ ...current, [suggestion.id]: event.target.value }))} placeholder="拒绝原因（可选）" aria-label={`${suggestion.suggestion_type} 拒绝原因`} />
                  <button className="button-primary" disabled={busy} onClick={() => void runAction(suggestion.id, () => decideLearningSuggestion(suggestion.id, "accept"))}>采纳并生成草案</button>
                  <button className="button-outline" disabled={busy} onClick={() => void runAction(suggestion.id, () => decideLearningSuggestion(suggestion.id, "reject", reason))}>拒绝</button>
                </> : null}
                {suggestion.status === "accepted" ? <button className="button-primary" disabled={busy} onClick={() => void runAction(suggestion.id, () => activateLearningSuggestion(suggestion.id))}>激活策略版本</button> : null}
                {(suggestion.status === "active" || suggestion.status === "evaluated") ? <button className="button-outline" disabled={busy} onClick={() => void runAction(suggestion.id, () => evaluateLearningSuggestion(suggestion.id))}>重新评估</button> : null}
                {suggestion.status === "evaluated" ? <>
                  <input className="decision-input" value={reason} onChange={(event) => setReasons((current) => ({ ...current, [suggestion.id]: event.target.value }))} placeholder="保留/回滚原因（可选）" aria-label={`${suggestion.suggestion_type} 决策原因`} />
                  <button className="button-primary" disabled={busy} onClick={() => void runAction(suggestion.id, () => keepLearningSuggestion(suggestion.id, reason))}>保留策略</button>
                  <button className="button-outline" disabled={busy} onClick={() => void runAction(suggestion.id, () => rollbackLearningSuggestion(suggestion.id, reason))}>回滚上一版</button>
                </> : null}
                {suggestion.status === "active" ? <button className="button-outline" disabled={busy} onClick={() => void runAction(suggestion.id, () => rollbackLearningSuggestion(suggestion.id, "观察期人工回滚"))}>回滚上一版</button> : null}
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
