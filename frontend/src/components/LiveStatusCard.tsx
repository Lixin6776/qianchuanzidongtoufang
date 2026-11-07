import { useEffect, useState } from "react";

import type { LiveWatchDataQuality, LiveWatchReport, LiveWatchStatus } from "../lib/api";
import { createOpsTaskFromLiveWatch, getLiveWatchStatus } from "../lib/api";

type Tone = "success" | "warning" | "danger" | "muted";

type StatusMetric = {
  label: string;
  value: string;
  detail: string;
  tone: Tone;
  primary?: boolean;
  progress?: number;
};

const numberFormat = new Intl.NumberFormat("zh-CN", {
  maximumFractionDigits: 2
});

type LiveStatusSnapshot = {
  report: LiveWatchReport | null;
  status: LiveWatchStatus | null;
};

type LiveStatusLoadResult = LiveWatchReport | LiveStatusSnapshot | null;

function isSnapshot(value: LiveStatusLoadResult): value is LiveStatusSnapshot {
  return Boolean(value && typeof value === "object" && "report" in value);
}

async function loadLatestSnapshot(): Promise<LiveStatusSnapshot> {
  // 状态接口和最新报表必须来自同一次读取，避免并发时把上一场报表当成当前场次。
  const status = await getLiveWatchStatus();
  return { report: status.latest ?? null, status };
}

function formatRatio(value: number | null | undefined) {
  return value === null || value === undefined ? "--" : value.toFixed(2);
}

function formatMoney(value: number | null | undefined) {
  return value === null || value === undefined ? "--" : `¥${numberFormat.format(value)}`;
}

function formatTime(value: string | undefined) {
  if (!value) return "等待首次读取";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function plainText(value: string | undefined) {
  return (value ?? "")
    .replace(/\*\*/g, "")
    .replace(/`/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .trim();
}

function sessionComparison(report: LiveWatchReport | null, status: LiveWatchStatus | null) {
  if (!report?.live_started_at || !status?.live_started_at) return null;
  const reportTime = new Date(report.live_started_at).getTime();
  const statusTime = new Date(status.live_started_at).getTime();
  if (Number.isNaN(reportTime) || Number.isNaN(statusTime)) {
    return report.live_started_at === status.live_started_at;
  }
  return reportTime === statusTime;
}

function qualityLabel(quality: LiveWatchDataQuality | null, sessionMismatch: boolean) {
  if (sessionMismatch) return "场次不一致";
  if (quality?.label) return quality.label;
  if (quality?.status === "good") return "数据可信";
  if (quality?.status === "partial") return "字段不完整";
  if (quality?.status === "stale") return "数据已过期";
  if (quality?.status === "unconfirmed") return "场次待确认";
  if (quality?.status === "invalid") return "来源异常";
  return "待校验";
}

function qualityTone(quality: LiveWatchDataQuality | null, sessionMismatch: boolean): Tone {
  if (sessionMismatch || quality?.status === "stale" || quality?.status === "invalid") {
    return "danger";
  }
  if (quality?.status === "partial" || quality?.status === "unconfirmed") return "warning";
  if (quality?.status === "good") return "success";
  return "muted";
}

function freshnessLabel(value: string | undefined) {
  if (value === "fresh") return "新鲜";
  if (value === "stale") return "已过期";
  if (value === "unknown") return "未知";
  return value || "待校验";
}

function issueMentions(report: LiveWatchReport | null, pattern: RegExp) {
  return (report?.problems ?? []).some((problem) => pattern.test(problem));
}

function issueTone(report: LiveWatchReport | null, pattern: RegExp): Tone {
  if (!report) return "muted";
  return issueMentions(report, pattern) ? "danger" : "success";
}

function overallTone(report: LiveWatchReport | null): Tone {
  if (!report) return "muted";
  if (
    report.source === "cdp-error" ||
    report.verify_passed === false ||
    report.level === "action"
  ) {
    return "danger";
  }
  if (
    report.level === "watch" ||
    (report.source && report.source !== "cdp" && report.source !== "api") ||
    (report.problems?.length ?? 0) > 0 ||
    (report.adjustments?.length ?? 0) > 0
  ) {
    return "warning";
  }
  return "success";
}

function toneLabel(tone: Tone) {
  if (tone === "danger") return "立即处理";
  if (tone === "warning") return "需要关注";
  if (tone === "success") return "运行正常";
  return "等待数据";
}

type CreatedTask = {
  id: string;
  status: string;
  due_at?: string | null;
};

export function LiveStatusCard({
  report: providedReport,
  load = loadLatestSnapshot,
  createTask = createOpsTaskFromLiveWatch,
  refreshMs = 30_000
}: {
  /** 测试或上层注入时使用；不传则由组件每 30 秒读取最新盯盘记录和运行状态。 */
  report?: LiveWatchReport | null;
  load?: () => Promise<LiveStatusLoadResult>;
  createTask?: (reportId: string, priorityIndex: number) => Promise<CreatedTask>;
  refreshMs?: number;
}) {
  const [report, setReport] = useState<LiveWatchReport | null>(providedReport ?? null);
  const [status, setStatus] = useState<LiveWatchStatus | null>(null);
  const [loading, setLoading] = useState(providedReport === undefined);
  const [error, setError] = useState<string | null>(null);
  const [taskBusyIndex, setTaskBusyIndex] = useState<number | null>(null);
  const [createdTasks, setCreatedTasks] = useState<Record<number, CreatedTask>>({});
  const [taskError, setTaskError] = useState("");

  useEffect(() => {
    if (providedReport !== undefined) {
      setReport(providedReport ?? null);
      setStatus(null);
      setLoading(false);
      setError(null);
      return;
    }

    let active = true;
    let stopped = false;
    let timer: number | null = null;
    const refresh = async () => {
      if (stopped) return;
      try {
        const loaded = await load();
        if (!active) return;
        const snapshot = isSnapshot(loaded) ? loaded : { report: loaded, status: null };
        const next = snapshot.report;
        setReport(next);
        setStatus(snapshot.status);
        setError(null);
        if (next?.session_status === "ended" || next?.session_status === "stopped") {
          stopped = true;
          if (timer !== null) window.clearInterval(timer);
          timer = null;
        }
      } catch {
        if (!active) return;
        setError("最新盯盘数据读取失败");
      } finally {
        if (active) setLoading(false);
      }
    };

    timer = refreshMs > 0 ? window.setInterval(refresh, refreshMs) : null;
    void refresh();
    return () => {
      active = false;
      stopped = true;
      if (timer !== null) window.clearInterval(timer);
    };
  }, [providedReport, load, refreshMs]);

  useEffect(() => {
    setCreatedTasks({});
    setTaskBusyIndex(null);
    setTaskError("");
  }, [report?.id, providedReport]);

  const problem = plainText(report?.problems?.find((item) => item.trim()));
  const adjustment = plainText(report?.adjustments?.find((item) => item.trim()));
  const roomName = report?.room_name || "直播间待读取";
  const observedAt = report?.captured_at || report?.created_at;
  const statusNote = status?.latest?.note ?? "";
  const dataQuality = report?.data_quality ?? null;
  const reportSessionMatches = sessionComparison(report, status);
  const sessionMismatch = reportSessionMatches === false;
  const sessionConfirmed =
    !sessionMismatch &&
    (dataQuality?.session_confirmed ?? Boolean(report?.live_started_at));
  const qualityStatus = sessionMismatch ? "mismatch" : dataQuality?.status ?? "unknown";
  const currentQualityLabel = qualityLabel(dataQuality, sessionMismatch);
  const currentQualityTone = qualityTone(dataQuality, sessionMismatch);
  const averageOnline =
    report?.average_online_viewers ?? dataQuality?.average_online_viewers ?? null;
  const onlineSamples =
    report?.online_samples ?? dataQuality?.average_online_samples ?? 0;
  const isEnded =
    report?.session_status === "ended" ||
    report?.session_status === "stopped" ||
    /本场已结束|直播已结束/.test(`${report?.note ?? ""} ${statusNote}`);
  const watchStopped = status !== null && !status.running;
  const staleAfterMinutes = Math.max(
    10,
    Math.ceil(((status?.interval_seconds ?? 300) * 2) / 60)
  );
  const observedTime = observedAt ? new Date(observedAt).getTime() : Number.NaN;
  const staleMinutes = Number.isNaN(observedTime)
    ? null
    : Math.max(0, Math.floor((Date.now() - observedTime) / 60_000));
  const qualityStale = dataQuality?.status === "stale";
  const isStale =
    qualityStale ||
    (status !== null &&
      !isEnded &&
      staleMinutes !== null &&
      staleMinutes > staleAfterMinutes);
  const qualityBlocksLive =
    qualityStale ||
    dataQuality?.status === "unconfirmed" ||
    dataQuality?.status === "invalid";
  const snapshotOnly =
    isEnded || watchStopped || isStale || sessionMismatch || qualityBlocksLive;
  const metricTone = (tone: Tone): Tone => (snapshotOnly ? "muted" : tone);
  const deltaAvailable =
    !snapshotOnly && report?.spend_delta !== null && report?.spend_delta !== undefined;
  const roiProgress =
    !snapshotOnly && report?.roi != null && report.roi_target
      ? Math.max(0, Math.min(100, (report.roi / report.roi_target) * 100))
      : undefined;

  const metrics: StatusMetric[] = [
    {
      label: "综合营销 ROI",
      value: formatRatio(report?.roi),
      detail: report?.roi_target == null ? "综合营销ROI目标未配置" : `综合营销ROI目标 ${formatRatio(report.roi_target)}`,
      tone: metricTone(
        report?.roi == null || report.roi_target == null
          ? "muted"
          : report.roi < report.roi_target
            ? "danger"
            : "success"
      ),
      primary: true,
      progress: roiProgress
    },
    {
      label: "GPM",
      value: formatMoney(report?.gpm),
      detail: "千次观看成交",
      tone: metricTone(issueTone(report, /GPM/i)),
      primary: true
    },
    {
      label: "近5分钟消耗金额",
      value: deltaAvailable ? formatMoney(report?.spend_delta) : "--",
      detail: isEnded
        ? "已结束，不再计算实时增量"
        : watchStopped
          ? "盯盘未运行，不计算实时增量"
          : isStale
            ? `数据已 ${staleMinutes} 分钟未更新`
            : deltaAvailable
              ? "最近一个采样周期"
              : "暂无增量数据",
      tone: deltaAvailable
        ? (report?.spend_delta ?? 0) <= 0
          ? "danger"
          : "success"
        : "muted"
    },
    {
      label: "平均在线",
      value: averageOnline == null ? "--" : numberFormat.format(averageOnline),
      detail:
        averageOnline == null
          ? sessionConfirmed
            ? "本场暂无有效样本"
            : "场次未确认，不计算均值"
          : `本场均值 · ${onlineSamples} 个样本`,
      tone: metricTone(issueTone(report, /在线|人数/))
    },
    {
      label: "CPM",
      value: formatMoney(report?.cpm),
      detail: snapshotOnly ? "最后快照口径" : "千次曝光成本",
      tone: metricTone(issueTone(report, /CPM/i))
    }
  ];

  const tone: Tone = error
    ? "danger"
    : isEnded || watchStopped
      ? "muted"
      : sessionMismatch || isStale || qualityStatus === "invalid"
        ? "danger"
        : qualityStatus === "partial" || qualityStatus === "unconfirmed"
          ? "warning"
          : overallTone(report);
  const badgeLabel = isEnded
    ? "直播已结束"
    : watchStopped
      ? "盯盘已停止"
      : sessionMismatch
        ? "场次不一致"
        : qualityStatus === "unconfirmed"
          ? "场次待确认"
          : qualityStatus === "invalid"
            ? "数据源异常"
            : isStale
              ? "数据已过期"
              : qualityStatus === "partial"
                ? "字段不完整"
                : toneLabel(tone);
  const snapshotNote = sessionMismatch
    ? "最新数据不属于当前场次，已停止把它当作实时盘面；请重新读取当前场次数据。"
    : qualityStatus === "unconfirmed"
      ? "当前场次开播时间未确认，无法确认这份数据属于当前场次；不计算本场平均在线，也不做实时判断。"
      : qualityStatus === "invalid"
        ? "数据来源不可识别，已停止把这份读数当作实时盘面。"
        : isEnded
      ? "直播已结束，自动盯盘和数据轮询已停止，当前展示最终快照，不再代表实时数据。"
      : watchStopped
        ? "盯盘当前未运行，当前展示最后快照，数据可能已过期。"
        : isStale
          ? `盯盘仍在运行，但数据已 ${staleMinutes} 分钟未更新；当前读数只代表最后一次成功采集。`
          : "";
  const diagnosticProblem = snapshotOnly
    ? snapshotNote || plainText(status?.last_error) || "当前不是实时数据"
    : error || problem || "本轮未返回异常项";
  const diagnosticAdvice = isEnded
    ? "下一场开播后，在「直播盯盘」里手动开始。"
    : watchStopped
      ? "需要继续盯盘时，在「直播盯盘」里开始或恢复。"
      : sessionMismatch || qualityStatus === "unconfirmed" || qualityStatus === "invalid"
        ? "先重新读取当前场次；场次、来源和新鲜度确认前，不要根据这组数据做投放动作。"
        : isStale
          ? "先检查数据源连接或点击「立即读取一次」；恢复前不要根据这组数据做投放动作。"
          : adjustment || "暂无调整建议，继续观察下一周期";
  const actionText = adjustment || "";
  const reportPriorities = (report?.priority_actions ?? [])
    .filter((item) => item.problem?.trim() && item.action?.trim())
    .slice(0, 3);
  const priorityActions =
    reportPriorities.length > 0
      ? reportPriorities
      : actionText
        ? [
            {
              rank: 1,
              severity: report?.level === "action" ? "high" : "medium",
              problem: problem || "当前周期异常",
              action: actionText,
              action_title: actionText,
              steps: [],
              verify_minutes: 10
            }
          ]
        : [];
  const canCreateTask =
    Boolean(report?.id && priorityActions.length) &&
    !snapshotOnly &&
    qualityStatus !== "partial";

  async function handleCreateTask(priorityIndex: number) {
    if (!report?.id || !canCreateTask || taskBusyIndex !== null) return;
    const rank = priorityActions[priorityIndex]?.rank ?? priorityIndex + 1;
    setTaskBusyIndex(priorityIndex);
    setTaskError("");
    try {
      const task = await createTask(report.id, priorityIndex);
      setCreatedTasks((current) => ({ ...current, [rank]: task }));
    } catch {
      setTaskError(`生成 P${rank} 验证任务失败，请检查本地服务。`);
    } finally {
      setTaskBusyIndex(null);
    }
  }

  const summaryTitle = sessionMismatch
    ? "场次不一致，暂停实时判断"
    : isEnded
      ? "直播已结束，停止实时判断"
      : watchStopped
        ? "盯盘已停止，不再判断实时状态"
        : qualityStatus === "unconfirmed"
          ? "场次待确认，不计算本场均值"
          : qualityStatus === "invalid"
            ? "数据源异常，暂停实时判断"
            : isStale
              ? "数据已过期，暂停实时判断"
              : qualityStatus === "partial"
                ? "字段不完整，结论需要降级"
                : problem || error
                  ? (() => {
                      const totalProblems =
                        report?.problems?.filter((item) => item.trim()).length ?? 1;
                      return totalProblems > priorityActions.length
                        ? `发现 ${totalProblems} 项问题，已收敛为 ${priorityActions.length} 项优先处理`
                        : `发现 ${totalProblems} 项问题`;
                    })()
                  : "本周期未发现异常";
  const observedLabel = sessionMismatch
    ? "最后数据"
    : isEnded
      ? "最后更新"
      : watchStopped
        ? "最后数据"
        : isStale
          ? "数据已过期"
          : "更新于";

  return (
    <section className={`live-status-card live-status-${tone}`} aria-label="实时盯盘状态">
      <header className="live-status-head">
        <div className="live-status-heading">
          <div className="live-status-titleline">
            <h2>
              <i className={`live-status-pulse${snapshotOnly ? " is-ended" : ""}`} aria-hidden="true" />
              实时盯盘状态
            </h2>
            <span>{roomName}</span>
          </div>
        </div>
        <div className="live-status-meta">
          <span className="live-status-source">{report?.source ? report.source.toUpperCase() : "WAIT"}</span>
          <span className={`live-status-badge live-status-badge-${tone}`}>{badgeLabel}</span>
          <time>{loading ? "读取中" : `${isEnded ? "最后更新" : "更新于"} ${formatTime(observedAt)}`}</time>
        </div>
      </header>

      {snapshotOnly ? (
        <div className="live-status-ended-note">{snapshotNote}</div>
      ) : null}

      <div className="live-status-grid">
        {metrics.map((metric) => (
          <article
            className={`live-status-metric${metric.primary ? " live-status-metric-primary" : ""} live-status-metric-${metric.tone}`}
            key={metric.label}
          >
            <div className="live-status-metric-head">
              <div className="live-status-metric-label">
                <span>{metric.label}</span>
                {metric.primary ? <em>核心</em> : null}
              </div>
              <i className={`live-status-dot live-status-dot-${metric.tone}`} aria-label={toneLabel(metric.tone)} />
            </div>
            <strong>{metric.value}</strong>
            <small>{metric.detail}</small>
            {metric.progress !== undefined ? (
              <div
                className={`live-status-progress live-status-progress-${metric.tone}`}
                aria-label={`目标达成 ${Math.round(metric.progress)}%`}
              >
                <span style={{ width: `${metric.progress}%` }} />
              </div>
            ) : null}
          </article>
        ))}
      </div>

      {report ? (
        <div className="live-status-quality" aria-label="数据质量">
          <span className={`live-status-quality-main live-status-quality-${currentQualityTone}`}>
            数据质量 {currentQualityLabel}
          </span>
          <span>
            字段 {dataQuality ? `${dataQuality.fields_present}/${dataQuality.fields_total}` : "--"}
          </span>
          <span>新鲜度 {freshnessLabel(dataQuality?.freshness)}</span>
          <span>场次 {sessionMismatch ? "不一致" : sessionConfirmed ? "已确认" : "待确认"}</span>
          <span>平均在线样本 {onlineSamples}</span>
        </div>
      ) : null}

      {report && priorityActions.length > 0 ? (
        <section className="live-priority-board" aria-label="本轮决策闭环">
          <header className="live-priority-head">
            <div>
              <span>异常收敛</span>
              <strong>本轮先做 {priorityActions.length} 件事</strong>
            </div>
            <small>只保留最高优先级问题；每项只配一个动作和验证窗口。</small>
          </header>
          <div className="live-priority-list">
            {priorityActions.map((item, index) => (
              <article
                className={`live-priority-item live-priority-${item.severity}`}
                key={`${item.rank}-${item.problem}`}
              >
                <span className="live-priority-rank">P{item.rank}</span>
                <div className="live-priority-copy">
                  <strong>{item.problem}</strong>
                  <p className="live-priority-action-title">{item.action_title || item.action}</p>
                  {item.steps?.length ? (
                    <ol className="live-priority-steps">
                      {item.steps.slice(0, 3).map((step) => (
                        <li key={step}>{step}</li>
                      ))}
                    </ol>
                  ) : null}
                  <details className="live-priority-details">
                    <summary>依据与止损</summary>
                    <p>{item.action}</p>
                    {item.success_criteria ? (
                      <span>成功标准：{item.success_criteria}</span>
                    ) : null}
                    {item.stop_condition ? (
                      <span>止损条件：{item.stop_condition}</span>
                    ) : null}
                  </details>
                </div>
                <em>{item.verify_minutes} 分钟验证</em>
                <button
                  className={index === 0 ? "button-primary" : "button-outline"}
                  type="button"
                  disabled={
                    !canCreateTask ||
                    taskBusyIndex !== null ||
                    Boolean(createdTasks[item.rank])
                  }
                  onClick={() => void handleCreateTask(index)}
                >
                  {taskBusyIndex === index
                    ? "创建中"
                    : createdTasks[item.rank]
                      ? `已生成 P${item.rank} 任务`
                      : `生成 P${item.rank} 验证任务`}
                </button>
              </article>
            ))}
          </div>
          <footer className="live-priority-foot">
            <small>
              生成任务会保存动作前基线，并在 10 / 30 分钟核对数据；执行仍由你人工确认。
            </small>
            {Object.entries(createdTasks).map(([rank, task]) => (
              <em className="live-action-success" aria-live="polite" key={rank}>
                已生成 P{rank} 验证任务
                {task.due_at
                  ? ` · 截止 ${new Date(task.due_at).toLocaleTimeString("zh-CN", {
                      hour: "2-digit",
                      minute: "2-digit"
                    })}`
                  : ""}
              </em>
            ))}
            {taskError ? <em className="live-action-error">{taskError}</em> : null}
          </footer>
        </section>
      ) : null}

      <details className="live-status-diagnostics">
        <summary>
          <span className={`live-status-summary-dot live-status-summary-dot-${tone}`} aria-hidden="true" />
          <strong>{summaryTitle}</strong>
          <span className="live-status-summary-hint">
            {snapshotOnly ? "查看状态说明" : "查看归因与建议"}
          </span>
        </summary>
        <div className="live-status-insights">
          <div>
            <span>当前发现</span>
            <p>{diagnosticProblem}</p>
          </div>
          <div>
            <span>建议动作</span>
            <p>{diagnosticAdvice}</p>
          </div>
        </div>
      </details>
    </section>
  );
}

