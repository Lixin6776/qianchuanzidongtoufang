import { ReportMessage } from "./ReportMessage";

type ReportSection = {
  title: string;
  lines: string[];
};

type ReportMetric = {
  label: string;
  value: string;
};

type ReportSummary = {
  title: string;
  kind: string;
  subtitle: string;
  metrics: ReportMetric[];
  issue: string;
  action: string;
  sectionCount: number;
};

const METRIC_LABEL = /ROI|消耗|成本|成交|订单|在线|GMV|GPM|CPM|曝光/i;

function stripInline(value: string) {
  return value
    .replace(/\*\*/g, "")
    .replace(/`/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .trim();
}

function firstListValue(section: ReportSection | undefined) {
  if (!section) return "";
  const line = section.lines.find((item) => /^[-*]\s+/.test(item) || /^\d+[.)]\s+/.test(item));
  if (!line) return "";
  return stripInline(line.replace(/^[-*]\s+/, "").replace(/^\d+[.)]\s+/, ""));
}

function parseSections(lines: string[]): ReportSection[] {
  const sections: ReportSection[] = [];
  let current: ReportSection | null = null;
  for (const raw of lines) {
    const line = raw.trim();
    const heading = /^###\s+(.+)$/.exec(line);
    if (heading) {
      if (current) sections.push(current);
      current = { title: heading[1].trim(), lines: [] };
      continue;
    }
    if (/^##\s+/.test(line)) continue;
    if (current) current.lines.push(line);
  }
  if (current) sections.push(current);
  return sections;
}

function parseMetrics(lines: string[]): ReportMetric[] {
  const metrics: ReportMetric[] = [];
  const seen = new Set<string>();

  const add = (label: string, value: string) => {
    const cleanLabel = stripInline(label).replace(/[（(].*?[）)]/g, "").trim();
    const cleanValue = stripInline(value);
    if (!cleanLabel || !cleanValue || !METRIC_LABEL.test(cleanLabel)) return;
    const key = cleanLabel.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    metrics.push({ label: cleanLabel, value: cleanValue });
  };

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index].trim();
    if (!line.startsWith("|")) continue;
    const cells = line.replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
    if (cells.length >= 2) add(cells[0], cells[1]);
  }

  for (const raw of lines) {
    const line = raw.trim();
    const bold = /^[-*]\s+\*\*(.+?)\*\*\s*[：:]\s*(.+)$/.exec(line);
    if (bold) {
      add(bold[1], bold[2]);
      continue;
    }
    const plain = /^[-*]\s+(.+?)[：:]\s*(.+)$/.exec(line);
    if (plain && METRIC_LABEL.test(plain[1])) add(plain[1], plain[2]);
  }

  return metrics.slice(0, 5);
}

function reportKind(title: string) {
  if (/素材分析/.test(title)) return "素材分析";
  if (/复盘/.test(title)) return "直播复盘";
  if (/盯盘/.test(title)) return "5 分钟盯盘";
  return "运营报表";
}

function summarize(content: string): ReportSummary {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const titleLine = lines.find((line) => /^##\s+/.test(line.trim()));
  const title = titleLine ? stripInline(titleLine.trim().replace(/^##\s+/, "")) : "运营报表";
  const subtitle = stripInline(lines.find((line) => /^>\s+/.test(line.trim()))?.trim().replace(/^>\s+/, "") ?? "");
  const sections = parseSections(lines);
  const issueSection = sections.find((section) => /发现的问题|问题|异常|诊断/.test(section.title));
  const actionSection = sections.find((section) => /调整方案|执行方案|建议|明日投放策略/.test(section.title));
  const issue = firstListValue(issueSection);
  const action = firstListValue(actionSection);
  return {
    title,
    kind: reportKind(title),
    subtitle,
    metrics: parseMetrics(lines),
    issue: /暂无|未发现|无异常/.test(issue) ? "" : issue,
    action,
    sectionCount: sections.length
  };
}

export function ChatReportCard({ content }: { content: string }) {
  const summary = summarize(content);
  const hasIssue = Boolean(summary.issue);
  const statusLabel = hasIssue
    ? "需要关注"
    : summary.kind === "直播复盘"
      ? "复盘完成"
      : "未见异常";

  return (
    <article className={`chat-report-card${hasIssue ? " chat-report-has-issue" : ""}`}>
      <header className="chat-report-head">
        <div>
          <span className="chat-report-kind">{summary.kind}</span>
          <h3>{summary.title}</h3>
        </div>
        <span className={`chat-report-status${hasIssue ? " is-issue" : ""}`}>{statusLabel}</span>
      </header>

      {summary.subtitle ? <p className="chat-report-subtitle">{summary.subtitle}</p> : null}

      {summary.metrics.length ? (
        <div className="chat-report-metrics">
          {summary.metrics.map((metric) => (
            <div key={metric.label}>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
            </div>
          ))}
        </div>
      ) : null}

      {hasIssue ? (
        <div className="chat-report-callout chat-report-issue">
          <span>发现</span>
          <p>{summary.issue}</p>
        </div>
      ) : null}

      {summary.action ? (
        <div className="chat-report-callout chat-report-action">
          <span>建议</span>
          <p>{summary.action}</p>
        </div>
      ) : null}

      <details className="chat-report-details">
        <summary>
          <span>展开完整报表</span>
          <small>{summary.sectionCount ? `${summary.sectionCount} 个章节 · 查看明细` : "查看明细"}</small>
        </summary>
        <div className="chat-report-full">
          <ReportMessage content={content} />
        </div>
      </details>
    </article>
  );
}
