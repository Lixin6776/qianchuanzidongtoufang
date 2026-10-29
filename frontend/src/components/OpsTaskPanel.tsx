import { useEffect, useState } from "react";

import { createOpsTask, getOpsTasks, updateOpsTask } from "../lib/api";

type OpsTask = {
  id: string; title: string; description: string; owner: string; priority: string;
  due_at?: string | null; status: string; success_criteria: string; stop_condition: string;
  result: string; created_at: string; completed_at?: string | null;
};

const STATUS_LABEL: Record<string, string> = { open: "待处理", in_progress: "处理中", done: "已完成", dismissed: "已关闭" };

export function OpsTaskPanel() {
  const [tasks, setTasks] = useState<OpsTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ title: "", owner: "", priority: "medium", due_at: "", success_criteria: "", description: "", stop_condition: "", notify_feishu: false });

  async function refresh() { setTasks((await getOpsTasks()) as OpsTask[]); }
  useEffect(() => {
    let active = true;
    refresh().catch(() => { if (active) setError("运营任务读取失败，请检查本地服务。"); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  async function run(id: string, action: () => Promise<unknown>) {
    setBusy(id); setError("");
    try { await action(); await refresh(); } catch { setError("任务操作失败，请检查本地服务。 "); } finally { setBusy(null); }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!form.title.trim()) { setError("请填写任务标题。"); return; }
    setBusy("new"); setError("");
    try {
      await createOpsTask({ ...form, due_at: form.due_at || null });
      setForm({ title: "", owner: "", priority: "medium", due_at: "", success_criteria: "", description: "", stop_condition: "", notify_feishu: false });
      await refresh();
    } catch { setError("任务创建失败，请检查本地服务。 "); } finally { setBusy(null); }
  }

  if (loading) return <div className="module-loading"><span className="module-spinner" aria-hidden="true" />正在读取运营任务…</div>;
  return (
    <div className="module-stack">
      <p className="monitor-signal">任务用于把盯盘、素材、复盘和策略建议落实到负责人；任务执行仍不自动修改账户。</p>
      {error ? <div className="module-error">{error}</div> : null}
      <form className="ops-task-form" onSubmit={(event) => void submit(event)}>
        <div className="module-toolbar"><div><strong>新建运营任务</strong><span>明确负责人、截止时间和成功标准。</span></div></div>
        <div className="ops-task-form-grid">
          <label>任务标题<input className="form-control" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="例如：复核低 ROI 素材" /></label>
          <label>负责人<input className="form-control" value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })} placeholder="姓名 / 岗位" /></label>
          <label>优先级<select className="form-select" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}><option value="high">高</option><option value="medium">中</option><option value="low">低</option></select></label>
          <label>截止时间<input className="form-control" type="datetime-local" value={form.due_at} onChange={(e) => setForm({ ...form, due_at: e.target.value })} /></label>
          <label>成功标准<input className="form-control" value={form.success_criteria} onChange={(e) => setForm({ ...form, success_criteria: e.target.value })} placeholder="例如：30 分钟内完成归因" /></label>
          <label>止损条件<input className="form-control" value={form.stop_condition} onChange={(e) => setForm({ ...form, stop_condition: e.target.value })} placeholder="例如：数据未通过校验则暂停" /></label>
          <label className="ops-task-wide">任务说明<textarea className="form-control" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} /></label>
          <label className="ops-task-check"><input type="checkbox" checked={form.notify_feishu} onChange={(e) => setForm({ ...form, notify_feishu: e.target.checked })} />创建后推送到飞书</label>
        </div>
        <button className="button-primary" disabled={busy === "new"} type="submit">创建任务</button>
      </form>
      <section className="module-stack">
        <h3>任务清单</h3>
        {tasks.length ? <div className="strategy-list">{tasks.map((task) => (
          <article className="strategy-card" key={task.id}>
            <header><div><strong>{task.title}</strong><span className="monitor-signal">{task.owner || "未分配负责人"} · {task.priority === "high" ? "高优先级" : task.priority === "low" ? "低优先级" : "中优先级"}</span></div><span className={`verdict-badge verdict-${task.status}`}>{STATUS_LABEL[task.status] ?? task.status}</span></header>
            {task.description ? <p>{task.description}</p> : null}
            <div className="execution-meta"><span>截止 {task.due_at ? new Date(task.due_at).toLocaleString("zh-CN") : "未设置"}</span><span>成功标准 {task.success_criteria || "未填写"}</span></div>
            <div className="strategy-actions">
              {task.status === "open" ? <button className="button-outline" disabled={busy === task.id} onClick={() => void run(task.id, () => updateOpsTask(task.id, { status: "in_progress" }))}>开始处理</button> : null}
              {task.status === "in_progress" ? <button className="button-primary" disabled={busy === task.id} onClick={() => void run(task.id, () => updateOpsTask(task.id, { status: "done" }))}>标记完成</button> : null}
              {task.status === "open" || task.status === "in_progress" ? <button className="button-outline" disabled={busy === task.id} onClick={() => void run(task.id, () => updateOpsTask(task.id, { status: "dismissed" }))}>关闭任务</button> : null}
            </div>
          </article>
        ))}</div> : <div className="module-empty-state"><strong>暂无运营任务</strong><span>把需要跟进的问题落成有负责人和截止时间的任务。</span></div>}
      </section>
    </div>
  );
}
