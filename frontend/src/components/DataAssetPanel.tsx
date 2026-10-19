import { OpsOutcomePanel } from "./OpsOutcomePanel";

/**
 * 数据资产：数据证明了什么。
 *
 * 和「决策」分工：
 *   决策   = 我定的规则（阈值 / 策略 / ROI 目标）
 *   数据资产 = 本账户实测出来的证据（哪些操作被正向反馈、在什么流速下有效）
 */
export function DataAssetPanel() {
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

      <OpsOutcomePanel />

      <p className="monitor-signal">
        ⚠️ 所有结论都是**观察性相关，不是因果**；样本少于一类的门槛时只标「样本不足」，不给方向。
      </p>
    </section>
  );
}
