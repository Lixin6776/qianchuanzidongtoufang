import { useEffect, useState } from "react";

import { createOpsTask, getOpsTasks, updateOpsTask } from "../lib/api";

type VerificationWindow = {
  target_minutes: number;
  observed_at: string;
  value: number;
  delta: number | null;
};

type TaskVerification = {
  status: string;
  suggested_verdict: string;
  focus_metric: string;
  focus_label?: string;
  message: string;
  window_10m?: VerificationWindow | null;
  window_30m?: VerificationWindow | null;
};

type OpsTask = {
  id: string;
  title: string;
  description: string;
  source_type?: string;
  source_id?: string | null;
  owner: string;
  priority: string;
  due_at?: string | null;
  status: string;
  success_criteria: string;
  stop_condition: string;
  result: string;
  created_at: string;
  completed_at?: string | null;
  context?: Record<string, unknown>;
  verification?: TaskVerification | null;
};

const STATUS_LABEL: Record<string, string> = {
  open: "待处理",
  in_progress: "处理中",
  done: "已完成",
  dismissed: "已关闭"
};

const VERDICT_LABEL: Record<string, string> = {
  success: "建议保留",
  failure: "建议回滚",
  neutral: "继续观察",
  pending: "等待验证",
  insufficient_data: "数据不足"
};

type TaskFilter = "all" | "pending" | "verifying" | "done";

const FILTER_LABEL: Record<TaskFilter, string> = {
  all: "全部",
  pending: "待处理",
  verifying: "验证中",
  done: "已完成"
};

function formatWindow(window: VerificationWindow | null | undefined, label: string) {
  if (!window) return null;
  const delta = window.delta;
  const deltaText =
    delta === null || delta === undefined
      ? "--"
      : `${delta >= 0 ? "+" : ""}${Number(delta).toFixed(2)}`;
  return `${window.target_minutes} 分钟：${label} ${Number(window.value).toFixed(2)}（${deltaText}）`;
}

export function OpsTaskPanel({
  loadTasks = getOpsTasks,
  refreshMs = 30_000
}: {
  loadTasks?: () => Promise<OpsTask[]>;
  refreshMs?: number;
}) {
  const [tasks, setTasks] = useState<OpsTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<TaskFilter>("all");
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string>("");
  const [form, setForm] = useState({
    title: "",
    owner: "",
    priority: "medium",
    due_at: "",
    success_criteria: "",
    description: "",
    stop_condition: "",
    notify_feishu: false
  });

  async function refresh() {
    const next = await loadTasks();
    setTasks(next);
    setLastRefreshedAt(new Date().toLocaleTimeString("zh-CN"));
  }

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const next = await loadTasks();
        if (!active) return;
        setTasks(next);
        setLastRefreshedAt(new Date().toLocaleTimeString("zh-CN"));
        setError("");
      } catch {
        if (active) setError("运营任务读取失败，请检查本地服务。");
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    const timer = refreshMs > 0 ? window.setInterval(load, refreshMs) : null;
    return () => {
      active = false;
      if (timer !== null) window.clearInterval(timer);
    };
  }, [loadTasks, refreshMs]);

  async function run(id: string, action: () => Promise<unknown>) {
    setBusy(id);
    setError("");
    try {
      await action();
      await refresh();
    } catch {
      setError("任务操作失败，请检查本地服务。");
    } finally {
      setBusy(null);
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!form.title.trim()) {
      setError("请填写任务标题。");
      return;
    }
    setBusy("new");
    setError("");
    try {
      await createOpsTask({ ...form, due_at: form.due_at || null });
      setForm({
        title: "",
        owner: "",
        priority: "medium",
        due_at: "",
        success_criteria: "",
        description: "",
        stop_condition: "",
        notify_feishu: false
      });
      await refresh();
    } catch {
      setError("任务创建失败，请检查本地服务。");
    } finally {
      setBusy(null);
    }
  }

  async function confirmVerdict(task: OpsTask, verdict: "success" | "failure") {
    const message = task.verification?.message || "10 分钟验证窗口已到期";
    if (verdict === "success") {
      await updateOpsTask(task.id, {
        status: "done",
        result: `验证通过并保留动作：${message}`
      });
      return;
    }
    await createOpsTask({
      title: `回滚：${task.title.replace(/^执行：/, "")}`,
      description: `原任务验证未通过。\n${message}\n原任务：${task.id}`,
      owner: task.owner || "当前投手",
      priority: "high",
      due_at: new Date(Date.now() + 10 * 60_000).toISOString(),
      success_criteria: "10 分钟内关键指标止跌，恢复到动作前基线附近",
      stop_condition: "回滚后指标继续恶化或数据质量非可信时立即停止"
    });
    await updateOpsTask(task.id, {
      status: "dismissed",
      result: `验证未通过，已生成回滚任务：${message}`
    });
  }

  if (loading) {
    return (
      <div className="module-loading">
        <span className="module-spinner" aria-hidden="true" />
        正在读取运营任务…
      </div>
    );
  }

  const counts: Record<TaskFilter, number> = {
    all: tasks.length,
    pending: tasks.filter((task) => task.status === "open").length,
    verifying: tasks.filter((task) => task.status === "in_progress").length,
    done: tasks.filter((task) => task.status === "done" || task.status === "dismissed").length
  };
  const filteredTasks = tasks.filter((task) => {
    if (filter === "pending") return task.status === "open";
    if (filter === "verifying") return task.status === "in_progress";
    if (filter === "done") return task.status === "done" || task.status === "dismissed";
    return true;
  });

  return (
    <div className="module-stack">
      <p className="monitor-signal">
        任务用于把盯盘、素材、复盘和策略建议落实到负责人；账户写操作仍需人工确认。
      </p>
      {error ? <div className="module-error">{error}</div> : null}

      <section className="module-stack">
        <div className="task-board-head">
          <h3>任务清单</h3>
          <span>最后刷新 {lastRefreshedAt || "--"}</span>
        </div>
        <div className="task-filter-bar" role="group" aria-label="任务筛选">
          {(Object.keys(FILTER_LABEL) as TaskFilter[]).map((key) => (
            <button
              className={filter === key ? "task-filter active" : "task-filter"}
              key={key}
              type="button"
              onClick={() => setFilter(key)}
            >
              {FILTER_LABEL[key]} {counts[key]}
            </button>
          ))}
        </div>
        {filteredTasks.length ? (
          <div className="strategy-list">
            {filteredTasks.map((task) => {
              const verification = task.verification;
              const focusLabel = verification?.focus_label || verification?.focus_metric?.toUpperCase() || "指标";
              const tenMinute = formatWindow(verification?.window_10m, focusLabel);
              const thirtyMinute = formatWindow(verification?.window_30m, focusLabel);
              return (
                <article className="strategy-card" key={task.id}>
                  <header>
                    <div>
                      <strong>{task.title}</strong>
                      <span className="monitor-signal">
                        {task.owner || "未分配负责人"} ·{" "}
                        {task.priority === "high"
                          ? "高优先级"
                          : task.priority === "low"
                            ? "低优先级"
                            : "中优先级"}
                      </span>
                    </div>
                    <span className={`verdict-badge verdict-${task.status}`}>
                      {STATUS_LABEL[task.status] ?? task.status}
                    </span>
                  </header>
                  {task.description ? <p>{task.description}</p> : null}
                  <div className="execution-meta">
                    <span>
                      截止{" "}
                      {task.due_at
                        ? new Date(task.due_at).toLocaleString("zh-CN")
                        : "未设置"}
                    </span>
                    <span>成功标准 {task.success_criteria || "未填写"}</span>
                  </div>
                  {task.source_type === "live_watch" ? (
                    <div className="task-verification">
                      <div className="task-verification-head">
                        <span>验证证据</span>
                        <strong className={`task-verification-${verification?.suggested_verdict || "pending"}`}>
                          {VERDICT_LABEL[verification?.suggested_verdict || "pending"] || "等待验证"}
                        </strong>
                      </div>
                      <small className="task-verification-caveat">
                        仅比较同场次动作前后数据，不自动认定因果；保留或回滚由人工确认。
                      </small>
                      {tenMinute ? <code>{tenMinute}</code> : <code>10 分钟：等待同场次可信数据</code>}
                      {thirtyMinute ? <code>{thirtyMinute}</code> : <code>30 分钟：等待同场次可信数据</code>}
                      {verification?.message ? <p>{verification.message}</p> : null}
                      {verification?.suggested_verdict === "success" && task.status !== "done" ? (
                        <button
                          className="button-primary"
                          disabled={busy === task.id}
                          onClick={() => void run(task.id, () => confirmVerdict(task, "success"))}
                          type="button"
                        >
                          验证通过并完成
                        </button>
                      ) : null}
                      {verification?.suggested_verdict === "failure" &&
                      task.status !== "dismissed" ? (
                        <button
                          className="button-outline"
                          disabled={busy === task.id}
                          onClick={() => void run(task.id, () => confirmVerdict(task, "failure"))}
                          type="button"
                        >
                          验证未通过，生成回滚任务
                        </button>
                      ) : null}
                    </div>
                  ) : null}
                  <div className="strategy-actions">
                    {task.status === "open" ? (
                      <button
                        className="button-outline"
                        disabled={busy === task.id}
                        onClick={() =>
                          void run(task.id, () =>
                            updateOpsTask(task.id, { status: "in_progress" })
                          )
                        }
                        type="button"
                      >
                        开始处理
                      </button>
                    ) : null}
                    {task.status === "in_progress" ? (
                      <button
                        className="button-primary"
                        disabled={busy === task.id}
                        onClick={() =>
                          void run(task.id, () => updateOpsTask(task.id, { status: "done" }))
                        }
                        type="button"
                      >
                        标记完成
                      </button>
                    ) : null}
                    {task.status === "open" || task.status === "in_progress" ? (
                      <button
                        className="button-outline"
                        disabled={busy === task.id}
                        onClick={() =>
                          void run(task.id, () =>
                            updateOpsTask(task.id, { status: "dismissed" })
                          )
                        }
                        type="button"
                      >
                        关闭任务
                      </button>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="module-empty-state">
            <strong>当前筛选下暂无任务</strong>
            <span>切换筛选，或把需要跟进的问题落成有负责人、验证窗口和止损条件的任务。</span>
          </div>
        )}
      </section>
      <details className="ops-task-create">
        <summary>手动新建任务</summary>
      <form className="ops-task-form" onSubmit={(event) => void submit(event)}>
        <div className="module-toolbar">
          <div>
            <strong>新建运营任务</strong>
            <span>明确负责人、截止时间、成功标准和止损条件。</span>
          </div>
        </div>
        <div className="ops-task-form-grid">
          <label>
            任务标题
            <input
              className="form-control"
              value={form.title}
              onChange={(event) => setForm({ ...form, title: event.target.value })}
              placeholder="例如：复核低 ROI 素材"
            />
          </label>
          <label>
            负责人
            <input
              className="form-control"
              value={form.owner}
              onChange={(event) => setForm({ ...form, owner: event.target.value })}
              placeholder="姓名 / 岗位"
            />
          </label>
          <label>
            优先级
            <select
              className="form-select"
              value={form.priority}
              onChange={(event) => setForm({ ...form, priority: event.target.value })}
            >
              <option value="high">高</option>
              <option value="medium">中</option>
              <option value="low">低</option>
            </select>
          </label>
          <label>
            截止时间
            <input
              className="form-control"
              type="datetime-local"
              value={form.due_at}
              onChange={(event) => setForm({ ...form, due_at: event.target.value })}
            />
          </label>
          <label>
            成功标准
            <input
              className="form-control"
              value={form.success_criteria}
              onChange={(event) => setForm({ ...form, success_criteria: event.target.value })}
              placeholder="例如：30 分钟内完成归因"
            />
          </label>
          <label>
            止损条件
            <input
              className="form-control"
              value={form.stop_condition}
              onChange={(event) => setForm({ ...form, stop_condition: event.target.value })}
              placeholder="例如：数据未通过校验则暂停"
            />
          </label>
          <label className="ops-task-wide">
            任务说明
            <textarea
              className="form-control"
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
              rows={2}
            />
          </label>
          <label className="ops-task-check">
            <input
              type="checkbox"
              checked={form.notify_feishu}
              onChange={(event) => setForm({ ...form, notify_feishu: event.target.checked })}
            />
            创建后推送到飞书
          </label>
        </div>
        <button className="button-primary" disabled={busy === "new"} type="submit">
          创建任务
        </button>
      </form>
      </details>
    </div>
  );
}
