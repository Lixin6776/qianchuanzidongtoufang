import { useEffect, useState } from "react";

import { getOpsOutcomeCases, getOpsOutcomeOverview, opsCasesCsvUrl } from "../lib/api";
import { OpsOutcomePanel } from "./OpsOutcomePanel";

type Overview = {
  asset_days: number;
  span: { start: string; end: string };
  watch_reports: number;
  operation_events: number;
  operation_types: number;
  conclusions: number;
  reviews: number;
  analyses: number;
  health: {
    last_24h_total: number;
    last_24h_valid: number;
    valid_rate: number | null;
    cdp_errors: number;
  };
};

/**
 * 数据资产：数据证明了什么。
 *
 * 和「决策」分工：
 *   决策   = 我定的规则（阈值 / 策略 / ROI 目标）
 *   数据资产 = 本账户实测出来的证据（哪些操作被正向反馈、在什么流速下有效）
 */
export function DataAssetPanel() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [cases, setCases] = useState<Array<Record<string, unknown>>>([]);

  useEffect(() => {
    getOpsOutcomeOverview()
      .then((value) => setOverview(value as Overview))
      .catch(() => setOverview(null));
    getOpsOutcomeCases(100)
      .then((value) => setCases(value as Array<Record<string, unknown>>))
      .catch(() => setCases([]));
  }, []);

  return (
    <section className="panel data-asset-panel">
      <div className="panel-heading">
        <p className="eyebrow">Data asset</p>
        <h2>数据资产</h2>
      </div>

      <p className="ops-role-desc">
        这里回答的是「**数据证明了什么**」——不是你的阈值和策略（那些在「决策」里），
        而是本账户实测出来的：哪些操作被数据正向反馈、在什么流速下更有效、结论是否在变稳。
      </p>

      {overview ? (
        <>
          <div className="asset-overview-grid">
            <div className="asset-card">
              <span>资产年龄</span>
              <strong>{overview.asset_days} 天</strong>
            </div>
            <div className="asset-card">
              <span>盯盘记录</span>
              <strong>{overview.watch_reports.toLocaleString()} 条</strong>
            </div>
            <div className="asset-card">
              <span>操作笔数</span>
              <strong>{overview.operation_events} 笔</strong>
            </div>
            <div className="asset-card">
              <span>已下结论</span>
              <strong>{overview.conclusions} 类</strong>
            </div>
          </div>
          <p className="monitor-signal">
            数据跨度：{overview.span.start} ~ {overview.span.end}
            　|　复盘 {overview.reviews} 份 · 素材分析 {overview.analyses} 份
            　|　操作类型 {overview.operation_types} 种
          </p>
          <p className="monitor-signal">
            数据健康：最近 24h 有效 <strong>{overview.health.last_24h_valid}</strong>/
            {overview.health.last_24h_total}
            {overview.health.valid_rate !== null
              ? `（${Math.round(overview.health.valid_rate * 100)}%）`
              : ""}
            　|　累计 CDP 失败 {overview.health.cdp_errors} 次
            {overview.health.valid_rate !== null && overview.health.valid_rate < 0.7
              ? "　⚠️ 有效率偏低，本页结论仅供参考"
              : ""}
          </p>
        </>
      ) : null}

      <OpsOutcomePanel />

      <h4 style={{ marginTop: 18 }}>操作流水（逐笔可追溯）</h4>
      <p className="monitor-signal">
        这是数据资产的原始凭证：每笔操作 + 操作前 / 10 分钟后 / 20 分钟后的边际 ROI。
        <a href={opsCasesCsvUrl()} download> 导出 CSV</a>
      </p>
      {cases.length ? (
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>操作</th>
              <th>操作前 ROI</th>
              <th>10 分钟后</th>
              <th>20 分钟后</th>
              <th>10 分 Δ</th>
              <th>判定</th>
            </tr>
          </thead>
          <tbody>
            {cases.slice(0, 30).map((row, index) => (
              <tr key={`${row.at}-${index}`}>
                <td>{String(row.at ?? "")}</td>
                <td>{String(row.operation ?? "")}</td>
                <td>{row.before_roi === null ? "--" : Number(row.before_roi).toFixed(2)}</td>
                <td>{row.after_10m_roi === null ? "--" : Number(row.after_10m_roi).toFixed(2)}</td>
                <td>{row.after_20m_roi === null ? "--" : Number(row.after_20m_roi).toFixed(2)}</td>
                <td>
                  {row.delta_10m === null
                    ? "--"
                    : `${Number(row.delta_10m) > 0 ? "+" : ""}${Number(row.delta_10m).toFixed(2)}`}
                </td>
                <td>
                  {{ positive: "✅ 正向", negative: "⚠️ 负向", flat: "➖ 持平", unknown: "数据不足" }[
                    String(row.verdict ?? "unknown")
                  ] ?? String(row.verdict ?? "")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="monitor-signal">还没有可追溯的操作流水。</p>
      )}

      <p className="monitor-signal">
        ⚠️ 所有结论都是**观察性相关，不是因果**；样本少于一类的门槛时只标「样本不足」，不给方向。
      </p>
    </section>
  );
}
