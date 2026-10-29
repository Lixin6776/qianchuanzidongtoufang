import { useEffect, useState } from "react";

import { getExecutionFeedback } from "../lib/api";

type ExecutionFeedback = {
  source: string;
  execution_job_id: string;
  confirmation_id: string;
  action_name: string;
  status: string;
  created_at: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  error?: string | null;
  learning_case_id?: string | null;
  outcome?: Record<string, unknown> | null;
  platform_log_status: string;
  link_status: "linked" | "candidate" | "unlinked";
  linked_operation?: {
    at: string;
    operation: string;
    verdict: string;
    delta_10m: number | null;
  } | null;
};

const LINK_LABEL = {
  linked: "平台流水已关联",
  candidate: "候选关联",
  unlinked: "待平台日志回流"
};

function StateDiff({ before, after }: { before: Record<string, unknown>; after: Record<string, unknown> }) {
  const keys = Array.from(new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})]));
  if (!keys.length) return <span className="monitor-signal">暂无执行前后字段</span>;
  return (
    <div className="execution-diff">
      {keys.map((key) => (
        <div key={key}>
          <span>{key}</span>
          <code>{String(before?.[key] ?? "--")} → {String(after?.[key] ?? "--")}</code>
        </div>
      ))}
    </div>
  );
}

export function ExecutionFeedbackPanel() {
  const [rows, setRows] = useState<ExecutionFeedback[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    getExecutionFeedback()
      .then((value) => {
        if (active) setRows(value as ExecutionFeedback[]);
      })
      .catch(() => {
        if (active) setError("执行回流读取失败，请检查本地服务。");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  if (loading) return <div className="module-loading"><span className="module-spinner" aria-hidden="true" />正在读取执行回流…</div>;
  if (error) return <div className="module-error">{error}</div>;
  if (!rows.length) return <div className="module-empty-state"><strong>暂无已执行任务</strong><span>人工确认并执行后，任务和结果会回流到这里。</span></div>;

  return (
    <div className="module-stack">
      <p className="monitor-signal">执行记录来自工具的确认执行链路；平台操作日志只在能匹配时才标注关联。</p>
      <div className="execution-feedback-list">
        {rows.map((row) => (
          <article className="execution-feedback-card" key={row.execution_job_id}>
            <header>
              <div><strong>{row.action_name}</strong><span className="monitor-signal">{new Date(row.created_at).toLocaleString("zh-CN")}</span></div>
              <span className={`verdict-badge verdict-${row.status}`}>{row.status}</span>
            </header>
            <div className="execution-meta">
              <span>任务 {row.execution_job_id.slice(0, 8)}</span>
              <span>确认单 {row.confirmation_id.slice(0, 8)}</span>
              <span className={`execution-link execution-link-${row.link_status}`}>{LINK_LABEL[row.link_status]}</span>
            </div>
            <StateDiff before={row.before} after={row.after} />
            {row.linked_operation ? <p className="monitor-signal">平台流水：{row.linked_operation.at} · {row.linked_operation.operation} · {row.linked_operation.verdict}</p> : <p className="monitor-signal">平台流水：{row.platform_log_status}</p>}
            {row.outcome ? <p className="monitor-signal">结果：{Object.entries(row.outcome).slice(0, 5).map(([key, value]) => `${key} ${String(value)}`).join(" · ")}</p> : null}
            {row.error ? <div className="module-error">{row.error}</div> : null}
          </article>
        ))}
      </div>
    </div>
  );
}
