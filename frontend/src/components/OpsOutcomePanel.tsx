import { useEffect, useState } from "react";

import { getOpsOutcome, getOpsOutcomeSnapshots } from "../lib/api";

type Summary = {
  n: number;
  median_delta: number | null;
  positive_rate: number | null;
  net_effect: number | null;
};

type OpRow = Summary & { operation: string; verdict: string };
type Stratum = {
  label: string;
  treated: Summary;
  control: Summary;
  net_effect: number | null;
  verdict: string;
};

export type OpsOutcomePayload = {
  baseline: Summary & { operation: string };
  operations: OpRow[];
  velocity_strata: Stratum[];
  window_minutes: number;
  min_sample: number;
  note: string;
};

const VERDICT: Record<string, string> = {
  positive: "✅ 正向",
  negative: "⚠️ 负向",
  neutral: "➖ 中性",
  insufficient: "样本不足"
};

function pct(value: number | null) {
  return value === null ? "--" : `${Math.round(value * 100)}%`;
}

function signed(value: number | null) {
  return value === null ? "--" : `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

const SERIES_COLORS = ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4", "#ec4899"];

/**
 * 资产趋势折线：每种操作的净效应随每日快照怎么变。
 * 手写 SVG，不引图表库（保持安装零依赖）。
 */
function TrendChart({ snapshots }: { snapshots: Array<{ date: string; snapshot: OpsOutcomePayload }> }) {
  if (snapshots.length < 2) return null;

  const names = Array.from(
    new Set(snapshots.flatMap((item) => item.snapshot.operations.map((row) => row.operation)))
  );
  const values = snapshots.flatMap((item) =>
    item.snapshot.operations
      .map((row) => row.net_effect)
      .filter((v): v is number => v !== null)
  );
  if (!values.length) return null;

  const W = 640;
  const H = 220;
  const PAD = 36;
  const min = Math.min(0, ...values) - 0.05;
  const max = Math.max(0, ...values) + 0.05;
  const span = max - min || 1;
  const x = (index: number) => PAD + (index * (W - 2 * PAD)) / (snapshots.length - 1);
  const y = (value: number) => H - PAD - ((value - min) / span) * (H - 2 * PAD);
  const zeroY = y(0);

  return (
    <div className="asset-trend-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="资产趋势折线图">
        <line x1={PAD} y1={zeroY} x2={W - PAD} y2={zeroY} stroke="#cbd5e1" strokeDasharray="4 4" />
        {snapshots.map((item, index) => (
          <text key={item.date} x={x(index)} y={H - 12} fontSize="11" textAnchor="middle" fill="#64748b">
            {item.date.slice(5)}
          </text>
        ))}
        {names.map((name, seriesIndex) => {
          const points = snapshots
            .map((item, index) => {
              const row = item.snapshot.operations.find((op) => op.operation === name);
              if (!row || row.net_effect === null) return null;
              return `${x(index)},${y(row.net_effect)}`;
            })
            .filter((point): point is string => point !== null);
          if (points.length < 2) return null;
          const color = SERIES_COLORS[seriesIndex % SERIES_COLORS.length];
          return (
            <g key={name}>
              <polyline points={points.join(" ")} fill="none" stroke={color} strokeWidth="2" />
              {points.map((point, index) => {
                const [px, py] = point.split(",");
                return <circle key={index} cx={px} cy={py} r="3" fill={color} />;
              })}
            </g>
          );
        })}
      </svg>
      <div className="asset-trend-legend">
        {names.map((name, index) => (
          <span key={name}>
            <i style={{ background: SERIES_COLORS[index % SERIES_COLORS.length] }} />
            {name}
          </span>
        ))}
      </div>
      <p className="monitor-signal">
        纵轴 = 净效应（已扣掉账户自然漂移）。只看趋势方向，别抠小数点。
      </p>
    </div>
  );
}

/**
 * 《操作反馈表》：你手动做的操作，被数据正向反馈了吗？
 *
 * 口径（先用真实数据自检过）：
 *   净效应 = 操作组中位Δ − 无操作对照组中位Δ（扣掉账户自然漂移）
 *   不是因果结论；n<20 只标"样本不足"。
 */
export function OpsOutcomePanel({ data: initialData }: { data?: OpsOutcomePayload | null } = {}) {
  const [data, setData] = useState<OpsOutcomePayload | null>(initialData ?? null);
  const [snapshots, setSnapshots] = useState<Array<{ date: string; snapshot: OpsOutcomePayload }>>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (initialData) {
      setData(initialData);
    } else {
      getOpsOutcome()
        .then((value) => setData(value as OpsOutcomePayload))
        .catch(() => setError("读取失败，检查本地服务。"));
    }
    getOpsOutcomeSnapshots()
      .then((value) => setSnapshots(value as Array<{ date: string; snapshot: OpsOutcomePayload }>))
      .catch(() => setSnapshots([]));
  }, [initialData]);

  // 趋势：最新两份快照对比（看样本在不在长、结论在不在变）
  const latest = snapshots.length >= 1 ? snapshots[snapshots.length - 1] : null;
  const previous = snapshots.length >= 2 ? snapshots[snapshots.length - 2] : null;
  const trend = (() => {
    if (!latest || !previous) return [];
    const prevMap = new Map(previous.snapshot.operations.map((row) => [row.operation, row]));
    return latest.snapshot.operations
      .map((row) => {
        const before = prevMap.get(row.operation);
        if (!before) return null;
        return {
          operation: row.operation,
          nBefore: before.n,
          nNow: row.n,
          netBefore: before.net_effect,
          netNow: row.net_effect
        };
      })
      .filter((item): item is NonNullable<typeof item> => item !== null);
  })();

  if (error) return <p className="monitor-signal">{error}</p>;
  if (!data) return null;

  return (
    <section className="ops-outcome">
      <h4>操作反馈表（近 {data.window_minutes} 分钟）</h4>
      <p className="monitor-signal">
        基线（无操作时刻）中位Δ <strong>{signed(data.baseline.median_delta)}</strong>
        （n={data.baseline.n}）。净效应 = 操作组 − 这个基线，已扣掉账户自然漂移。
      </p>

      <table>
        <thead>
          <tr>
            <th>操作</th>
            <th>样本</th>
            <th>正反馈率</th>
            <th>净效应</th>
            <th>判定</th>
          </tr>
        </thead>
        <tbody>
          {data.operations.map((row) => (
            <tr key={row.operation}>
              <td>{row.operation}</td>
              <td>{row.n}</td>
              <td>{pct(row.positive_rate)}</td>
              <td>{signed(row.net_effect)}</td>
              <td>{VERDICT[row.verdict] ?? row.verdict}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h4>按流速分层（更有用的切法）</h4>
      <table>
        <thead>
          <tr>
            <th>流速</th>
            <th>操作 n</th>
            <th>对照 n</th>
            <th>净效应</th>
            <th>判定</th>
          </tr>
        </thead>
        <tbody>
          {data.velocity_strata.map((row) => (
            <tr key={row.label}>
              <td>{row.label}</td>
              <td>{row.treated.n}</td>
              <td>{row.control.n}</td>
              <td>{signed(row.net_effect)}</td>
              <td>{VERDICT[row.verdict] ?? row.verdict}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h4>资产趋势（每日 08:10 存档）</h4>
      {latest ? (
        <p className="monitor-signal">
          已有 <strong>{snapshots.length}</strong> 份快照，最新 {latest.date}。
          {previous ? ` 下面是最新（${latest.date}）对比上一份（${previous.date}）。` : " 再攒 1 天就能对比趋势。"}
        </p>
      ) : (
        <p className="monitor-signal">还没有快照，每天 08:10 自动存一份。</p>
      )}
      <TrendChart snapshots={snapshots} />

      {trend.length ? (
        <table>
          <thead>
            <tr>
              <th>操作</th>
              <th>样本（前 → 后）</th>
              <th>净效应（前 → 后）</th>
              <th>变化</th>
            </tr>
          </thead>
          <tbody>
            {trend.map((row) => {
              const delta =
                row.netBefore !== null && row.netNow !== null ? row.netNow - row.netBefore : null;
              return (
                <tr key={row.operation}>
                  <td>{row.operation}</td>
                  <td>
                    {row.nBefore} → {row.nNow}
                  </td>
                  <td>
                    {signed(row.netBefore)} → {signed(row.netNow)}
                  </td>
                  <td>{delta === null ? "--" : `${delta > 0 ? "+" : ""}${delta.toFixed(2)}`}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : null}

      <p className="monitor-signal">
        ⚠️ {data.note} 单类样本 &lt; {data.min_sample} 只标"样本不足"，不出结论。
      </p>
    </section>
  );
}
