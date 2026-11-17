import { useEffect, useState } from "react";

import { getSystemDoctor, type SystemDoctorReport } from "../lib/api";

const STATUS_LABEL = {
  ok: "通过",
  warning: "提醒",
  blocked: "阻断"
} as const;

function headline(report: SystemDoctorReport): string {
  if (report.status === "blocked") {
    return `部署存在 ${report.summary.blocked} 个阻断项`;
  }
  if (report.status === "attention") {
    return `基础部署可用，有 ${report.summary.warning} 项提醒`;
  }
  return "部署就绪";
}

export function SystemHealthPanel({
  onOpenWindow
}: {
  onOpenWindow?: (windowId: string) => void;
}) {
  const [report, setReport] = useState<SystemDoctorReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    setBusy(true);
    setError("");
    try {
      setReport(await getSystemDoctor());
    } catch {
      setError("自检接口暂时不可用，请确认本地服务正在运行。");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <section className="system-health-panel">
      <div className={`system-health-summary status-${report?.status || "loading"}`}>
        <div>
          <p className="eyebrow">DEPLOYMENT DOCTOR</p>
          <h3>{report ? headline(report) : "正在检查本机部署"}</h3>
          <p className="system-health-caption">
            {report
              ? `版本 ${report.environment.app_version} · Python ${report.environment.python} · ${report.environment.platform}`
              : "检查运行环境、数据目录、数据库、数据连接与首次报表状态"}
          </p>
        </div>
        <button className="button-primary" type="button" onClick={refresh} disabled={busy}>
          {busy ? "检查中..." : "重新自检"}
        </button>
      </div>

      {error ? <p className="system-health-error">{error}</p> : null}

      {report ? (
        <>
          <div className="system-health-counts" aria-label="自检汇总">
            <span><strong>{report.summary.ok}</strong> 通过</span>
            <span><strong>{report.summary.warning}</strong> 提醒</span>
            <span><strong>{report.summary.blocked}</strong> 阻断</span>
          </div>

          <ol className="system-health-list">
            {report.checks.map((check) => (
              <li className={`system-health-check status-${check.status}`} key={check.key}>
                <span className="system-health-status">{STATUS_LABEL[check.status]}</span>
                <div className="system-health-check-copy">
                  <div className="system-health-check-heading">
                    <strong>{check.label}</strong>
                    {check.optional ? <span>可选</span> : null}
                  </div>
                  <p>{check.message}</p>
                </div>
                {check.action_label && check.action_target && onOpenWindow ? (
                  <button
                    className="button-outline"
                    type="button"
                    onClick={() => onOpenWindow(check.action_target)}
                  >
                    {check.action_label}
                  </button>
                ) : null}
              </li>
            ))}
          </ol>

          <p className="system-health-caption">
            自检只读取本机环境与连接状态，不会返回 Token、Secret、Cookie，也不会修改账户。
          </p>
        </>
      ) : (
        <div className="module-loading" role="status">
          <span className="module-spinner" aria-hidden="true" />
          正在检查本机部署，请稍候...
        </div>
      )}
    </section>
  );
}
