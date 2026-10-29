import { useEffect, useState } from "react";

import type { LiveWatchReport, LiveWatchStatus } from "../lib/api";
import { getLiveWatchLogs, getLiveWatchStatus } from "../lib/api";

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
  const logs = await getLiveWatchLogs(1);
  let status: LiveWatchStatus | null = null;
  try {
    status = await getLiveWatchStatus();
  } catch {
    status = null;
  }
  return { report: logs[0] ?? null, status };
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

export function LiveStatusCard({
  report: providedReport,
  load = loadLatestSnapshot,
  refreshMs = 30_000
}: {
  /** 测试或上层注入时使用；不传则由组件每 30 秒读取最新盯盘记录和运行状态。 */
  report?: LiveWatchReport | null;
  load?: () => Promise<LiveStatusLoadResult>;
  refreshMs?: number;
}) {
  const [report, setReport] = useState<LiveWatchReport | null>(providedReport ?? null);
  const [status, setStatus] = useState<LiveWatchStatus | null>(null);
  const [loading, setLoading] = useState(providedReport === undefined);
  const [error, setError] = useState<string | null>(null);

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

  const problem = plainText(report?.problems?.find((item) => item.trim()));
  const adjustment = plainText(report?.adjustments?.find((item) => item.trim()));
  const roomName = report?.room_name || "直播间待读取";
  const observedAt = report?.captured_at || report?.created_at;
  const statusNote = status?.latest?.note ?? "";
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
  const isStale =
    status !== null &&
    !isEnded &&
    staleMinutes !== null &&
    staleMinutes > staleAfterMinutes;
  const snapshotOnly = isEnded || watchStopped || isStale;
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
      label: snapshotOnly ? "最后在线" : "实时在线",
      value: report ? numberFormat.format(report.online_viewers) : "--",
      detail: snapshotOnly ? "最后一次成功采集" : "当前快照",
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
      : isStale
        ? "danger"
        : overallTone(report);
  const badgeLabel = isEnded
    ? "直播已结束"
    : watchStopped
      ? "盯盘已停止"
      : isStale
        ? "数据已过期"
        : toneLabel(tone);
  const snapshotNote = isEnded
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
      : isStale
        ? "先检查数据源连接或点击「立即读取一次」；恢复前不要根据这组数据做投放动作。"
        : adjustment || "暂无调整建议，继续观察下一周期";
  const summaryTitle = isEnded
    ? "直播已结束，停止实时判断"
    : watchStopped
      ? "盯盘已停止，不再判断实时状态"
      : isStale
        ? "数据已过期，暂停实时判断"
        : problem || error
          ? `发现 ${report?.problems?.filter((item) => item.trim()).length ?? 1} 项问题`
          : "本周期未发现异常";
  const observedLabel = isEnded
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

