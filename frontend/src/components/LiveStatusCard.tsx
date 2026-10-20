import { useEffect, useState } from "react";

import type { LiveWatchReport } from "../lib/api";
import { getLiveWatchLogs } from "../lib/api";

type Tone = "success" | "warning" | "danger" | "muted";

type StatusMetric = {
  label: string;
  value: string;
  detail: string;
  tone: Tone;
};

const numberFormat = new Intl.NumberFormat("zh-CN", {
  maximumFractionDigits: 2
});

async function loadLatestReport(): Promise<LiveWatchReport | null> {
  const logs = await getLiveWatchLogs(1);
  return logs[0] ?? null;
}

function formatRatio(value: number | null | undefined) {
  return value === null || value === undefined ? "--" : value.toFixed(2);
}

function formatMoney(value: number | null | undefined) {
  return value === null || value === undefined ? "--" : `¥${numberFormat.format(value)}`;
}

function formatPercent(value: number | null | undefined) {
  return value === null || value === undefined ? "--" : `${value.toFixed(2)}%`;
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
    report.level === "action" ||
    report.session_status === "ended"
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
  load = loadLatestReport,
  refreshMs = 30_000
}: {
  /** 测试或上层注入时使用；不传则由组件每 30 秒读取最新盯盘记录。 */
  report?: LiveWatchReport | null;
  load?: () => Promise<LiveWatchReport | null>;
  refreshMs?: number;
}) {
  const [report, setReport] = useState<LiveWatchReport | null>(providedReport ?? null);
  const [loading, setLoading] = useState(providedReport === undefined);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (providedReport !== undefined) {
      setReport(providedReport ?? null);
      setLoading(false);
      setError(null);
      return;
    }

    let active = true;
    const refresh = async () => {
      try {
        const next = await load();
        if (!active) return;
        setReport(next);
        setError(null);
      } catch {
        if (!active) return;
        setError("最新盯盘数据读取失败");
      } finally {
        if (active) setLoading(false);
      }
    };

    void refresh();
    const timer = refreshMs > 0 ? window.setInterval(refresh, refreshMs) : null;
    return () => {
      active = false;
      if (timer !== null) window.clearInterval(timer);
    };
  }, [providedReport, load, refreshMs]);

  const flowPerMinute = report?.spend_delta === null || report?.spend_delta === undefined
    ? null
    : report.spend_delta / 5;

  const metrics: StatusMetric[] = [
    {
      label: "消耗流速",
      value: flowPerMinute === null ? "--" : `¥${numberFormat.format(flowPerMinute)}/分`,
      detail: report?.spend_delta === null || report?.spend_delta === undefined
        ? "暂无增量数据"
        : `5 分钟增量 ${formatMoney(report.spend_delta)}`,
      tone: flowPerMinute === null ? "muted" : flowPerMinute <= 0 ? "danger" : "success"
    },
    {
      label: "实时在线",
      value: report ? numberFormat.format(report.online_viewers) : "--",
      detail: "当前快照",
      tone: issueTone(report, /在线|人数/)
    },
    {
      label: "ROI",
      value: formatRatio(report?.roi),
      detail: report?.roi_target == null ? "未配置目标" : `目标 ${formatRatio(report.roi_target)}`,
      tone: report?.roi == null || report.roi_target == null
        ? "muted"
        : report.roi < report.roi_target
          ? "danger"
          : "success"
    },
    {
      label: "CPM",
      value: formatMoney(report?.cpm),
      detail: "千次曝光成本",
      tone: issueTone(report, /CPM/i)
    },
    {
      label: "曝光观看率",
      value: formatPercent(report?.exposure_view_rate),
      detail: "进入效率",
      tone: issueTone(report, /曝光观看率/)
    }
  ];

  const tone = error ? "danger" : overallTone(report);
  const problem = plainText(report?.problems?.find((item) => item.trim()));
  const adjustment = plainText(report?.adjustments?.find((item) => item.trim()));
  const roomName = report?.room_name || "直播间待读取";
  const observedAt = report?.captured_at || report?.created_at;

  return (
    <section className={`live-status-card live-status-${tone}`} aria-label="实时盯盘状态">
      <header className="live-status-head">
        <div className="live-status-heading">
          <span className="live-status-kicker">LIVE OPS · 5 分钟盯盘</span>
          <div className="live-status-titleline">
            <h2>实时盯盘状态</h2>
            <span>{roomName}</span>
          </div>
        </div>
        <div className="live-status-meta">
          <span className={`live-status-badge live-status-badge-${tone}`}>{toneLabel(tone)}</span>
          <time>{loading ? "读取中" : `更新于 ${formatTime(observedAt)}`}</time>
        </div>
      </header>

      <div className="live-status-grid">
        {metrics.map((metric) => (
          <article className="live-status-metric" key={metric.label}>
            <div className="live-status-metric-head">
              <span>{metric.label}</span>
              <i className={`live-status-dot live-status-dot-${metric.tone}`} aria-label={toneLabel(metric.tone)} />
            </div>
            <strong>{metric.value}</strong>
            <small>{metric.detail}</small>
          </article>
        ))}
      </div>

      <div className="live-status-insights">
        <div>
          <span>当前发现</span>
          <p>{error || problem || "本轮未返回异常项"}</p>
        </div>
        <div>
          <span>建议动作</span>
          <p>{adjustment || "暂无调整建议，继续观察下一周期"}</p>
        </div>
      </div>
    </section>
  );
}

