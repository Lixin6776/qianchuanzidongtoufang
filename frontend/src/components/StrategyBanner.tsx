export type StrategyBannerProfile = {
  version: number;
  business_direction: string;
  primary_objective: string;
  hard_constraints: Record<string, unknown>;
  data_time: string;
  freshness: "fresh" | "stale";
  created_at?: string;
  effective_at?: string;
};

function constraintLabels(constraints: Record<string, unknown>) {
  const labels: string[] = [];
  if (constraints.automation_mode === "confirm_required") labels.push("全自动·需确认");
  else if (constraints.read_only === true) labels.push("只读");
  const assist = constraints.assist_share_max;
  if (typeof assist === "number") labels.push(`追投 ≤${assist}%`);
  const roi = constraints.roi_target;
  if (typeof roi === "number") labels.push(`综合营销ROI参考 ${roi}`);
  const budget = constraints.daily_budget_max;
  if (typeof budget === "number") labels.push(`日预算 ≤¥${budget.toLocaleString("zh-CN")}`);
  if (!labels.length) labels.push("策略约束待配置");
  return labels;
}

function formatTimestamp(value: string | undefined) {
  if (!value) return "时间未提供";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "时间未提供" : date.toLocaleString("zh-CN");
}

export function StrategyBanner({ profile }: { profile: StrategyBannerProfile }) {
  const timestamp = profile.data_time || profile.effective_at || profile.created_at;
  return (
    <header className="strategy-banner">
      <div className="app-brand">
        <span className="brand-mark">川</span>
        <strong>直播运营助手</strong>
      </div>
      <div className="strategy-banner-content">
        <strong className="strategy-version">盯盘策略 v{profile.version}</strong>
        <span className="strategy-direction" title={profile.business_direction}>{profile.business_direction}</span>
        <span className="strategy-objective" title={profile.primary_objective}>{profile.primary_objective}</span>
        <div className="strategy-constraints" aria-label="策略约束" title={JSON.stringify(profile.hard_constraints)}>
          {constraintLabels(profile.hard_constraints).map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>
        <span className={`strategy-freshness ${profile.freshness === "fresh" ? "status-fresh" : "status-stale"}`}>
          {profile.freshness === "fresh" ? "数据最新" : "数据未刷新"}
        </span>
        <time dateTime={timestamp}>{formatTimestamp(timestamp)}</time>
      </div>
    </header>
  );
}
