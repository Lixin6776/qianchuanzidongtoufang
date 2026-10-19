import { useEffect, useState } from "react";

import { getOpsOutcomeOverview } from "../lib/api";
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

  useEffect(() => {
    getOpsOutcomeOverview()
      .then((value) => setOverview(value as Overview))
      .catch(() => setOverview(null));
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

      <p className="monitor-signal">
        ⚠️ 所有结论都是**观察性相关，不是因果**；样本少于一类的门槛时只标「样本不足」，不给方向。
      </p>
    </section>
  );
}
