import { useEffect, useRef, useState } from "react";

import {
  createStrategyProfile,
  getActiveProfile,
  getKnowledgeOverview,
  uploadKnowledgeFile,
  type KnowledgeOverview
} from "../lib/api";

type Profile = {
  version: number;
  name: string;
  business_direction: string;
  primary_objective: string;
  secondary_objectives?: string[];
  hard_constraints?: Record<string, unknown>;
  monitoring_config?: Record<string, unknown>;
  allowed_actions?: string[];
  notification_policy?: Record<string, unknown>;
};

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const value = String(reader.result || "");
      const [, base64 = ""] = value.split(",", 2);
      if (!base64) {
        reject(new Error("empty file"));
        return;
      }
      resolve(base64);
    };
    reader.onerror = () => reject(reader.error || new Error("file read failed"));
    reader.readAsDataURL(file);
  });
}

/** 可自定义的判断标准（留空 = 自动） */
const FIELDS: Array<{ key: string; label: string; unit: string; hint: string }> = [
  { key: "exposure_view_rate", label: "曝光观看率", unit: "%", hint: "低于它算「进人不行」" },
  { key: "view_conversion_rate", label: "观看成交转化率", unit: "%", hint: "低于它算「承接不行」" },
  { key: "gpm", label: "GPM", unit: "元", hint: "低于它算「单位观看产出不够」" },
  { key: "cpm", label: "CPM", unit: "元", hint: "高于它算「拿量成本偏高」" },
  { key: "assist_share", label: "追投/调控占比", unit: "%", hint: "高于它算「结构偏重」（官方建议约 25%）" },
];

/**
 * 判断标准（阈值）：你来定。
 * 留空 = 自动（先用本账户历史分位，样本不足再退回通用参考线）。
 * 保存 = 生成策略新版本（可回溯），不会悄悄改掉旧版本。
 */
export function ThresholdPanel() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [knowledge, setKnowledge] = useState<KnowledgeOverview | null>(null);
  const [knowledgeLoading, setKnowledgeLoading] = useState(true);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [knowledgeNotice, setKnowledgeNotice] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  async function refreshKnowledge() {
    const next = await getKnowledgeOverview();
    setKnowledge(next);
  }

  useEffect(() => {
    let active = true;
    refreshKnowledge()
      .catch(() => {
        if (active) setKnowledgeNotice("知识文件读取失败，检查本地服务是否在运行。");
      })
      .finally(() => {
        if (active) setKnowledgeLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    getActiveProfile()
      .then((p) => {
        const data = p as Profile;
        setProfile(data);
        const saved = (data.hard_constraints?.thresholds || {}) as Record<string, unknown>;
        const next: Record<string, string> = {};
        for (const field of FIELDS) {
          const value = saved[field.key];
          next[field.key] = typeof value === "number" ? String(value) : "";
        }
        setValues(next);
      })
      .catch(() => setNotice("读取当前策略失败，检查本地服务是否在跑。"));
  }, []);

  async function handleSave() {
    if (!profile) return;
    setBusy(true);
    setNotice("");
    const thresholds: Record<string, number> = {};
    for (const field of FIELDS) {
      const raw = (values[field.key] || "").trim();
      if (!raw) continue;
      const num = Number(raw);
      if (!Number.isFinite(num)) {
        setNotice(`${field.label} 填的不是数字：${raw}`);
        setBusy(false);
        return;
      }
      thresholds[field.key] = num;
    }
    try {
      const saved = (await createStrategyProfile({
        name: profile.name,
        business_direction: profile.business_direction,
        primary_objective: profile.primary_objective,
        secondary_objectives: profile.secondary_objectives || [],
        hard_constraints: { ...(profile.hard_constraints || {}), thresholds },
        monitoring_config: profile.monitoring_config || { interval_minutes: 5 },
        allowed_actions: profile.allowed_actions || [],
        notification_policy: profile.notification_policy || { dedupe_minutes: 10 }
      })) as Profile;
      setProfile(saved);
      setNotice(`已保存为策略 v${saved.version}（旧的保留，可回溯）`);
    } catch {
      setNotice("保存失败，检查本地服务。");
    } finally {
      setBusy(false);
    }
  }

  async function handleUploadKnowledge() {
    if (!selectedFiles.length || uploading) return;
    setUploading(true);
    setKnowledgeNotice("");
    try {
      for (const file of selectedFiles) {
        const contentBase64 = await readFileAsBase64(file);
        await uploadKnowledgeFile({
          name: file.name,
          content_base64: contentBase64,
          content_type: file.type
        });
      }
      setSelectedFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = "";
      await refreshKnowledge();
      setKnowledgeNotice("知识文件已上传，运营助手后续会优先引用这些文件。");
    } catch {
      setKnowledgeNotice("上传失败，请检查文件大小（最多 10MB）和本地服务。");
    } finally {
      setUploading(false);
    }
  }

  function resetAll() {
    const next: Record<string, string> = {};
    for (const field of FIELDS) next[field.key] = "";
    setValues(next);
    setNotice("已清空（点「保存」后生效：全部改回自动）");
  }

  return (
    <section className="threshold-panel">
      <p className="eyebrow">Trader knowledge base</p>
      <h3>知识文件</h3>
      <p className="ops-role-desc">
        上传投手自己的规则、复盘、SOP 或数据文件后，直播运营助手会优先参考这些内容，但不会自动覆盖下方的账户判断标准。
        没有上传文件时，自动使用本账户历史有效采样的平均值作为参考。
      </p>
      <div className="knowledge-upload-row">
        <label className="knowledge-file-picker">
          <span>选择知识文件</span>
          <input
            ref={fileInputRef}
            aria-label="上传知识文件"
            type="file"
            multiple
            accept=".txt,.md,.markdown,.csv,.json,.yaml,.yml,.pdf,.doc,.docx,.png,.jpg,.jpeg,.webp"
            onChange={(event) => {
              setSelectedFiles(Array.from(event.target.files || []));
              setKnowledgeNotice("");
            }}
          />
        </label>
        <button
          className="button-primary"
          type="button"
          disabled={!selectedFiles.length || uploading}
          onClick={() => void handleUploadKnowledge()}
        >
          {uploading ? "上传中" : "上传到知识库"}
        </button>
      </div>
      {selectedFiles.length ? (
        <p className="monitor-signal">
          待上传：{selectedFiles.map((file) => file.name).join("、")}
        </p>
      ) : null}
      {knowledgeNotice ? <p className="monitor-signal">{knowledgeNotice}</p> : null}

      {knowledgeLoading ? (
        <div className="module-loading">
          <span className="module-spinner" aria-hidden="true" />
          正在读取知识文件…
        </div>
      ) : knowledge?.files.length ? (
        <div className="knowledge-file-list">
          {knowledge.files.map((file) => (
            <article key={file.id}>
              <div>
                <strong>{file.name}</strong>
                <span>
                  {(file.size / 1024).toFixed(1)} KB ·{" "}
                  {file.parse_status === "parsed" ? "文本已解析" : "已存储，暂不提取文本"}
                </span>
              </div>
              {file.preview ? <p>{file.preview}</p> : null}
            </article>
          ))}
        </div>
      ) : knowledge?.mode === "historical_average" && knowledge.historical_reference ? (
        <section className="knowledge-history-reference" aria-label="账户历史参考">
          <header>
            <div>
              <strong>账户历史参考</strong>
              <span>
                {knowledge.historical_reference.sample_count} 次有效采样平均值
                {knowledge.historical_reference.window_start
                  ? ` · ${new Date(knowledge.historical_reference.window_start).toLocaleDateString("zh-CN")} 至 ${new Date(knowledge.historical_reference.window_end || knowledge.historical_reference.window_start).toLocaleDateString("zh-CN")}`
                  : ""}
              </span>
            </div>
            <em>历史参考，不是规则</em>
          </header>
          <div className="knowledge-history-metrics">
            {knowledge.historical_reference.metrics.map((metric) => (
              <article key={metric.key}>
                <strong>
                  {metric.label} {metric.average}
                  {metric.unit ? ` ${metric.unit}` : ""}
                </strong>
                <small>n={metric.samples}</small>
              </article>
            ))}
          </div>
          <p>{knowledge.historical_reference.note}</p>
        </section>
      ) : (
        <div className="module-empty-state">
          <strong>暂无知识文件和历史参考</strong>
          <span>先上传文件，或积累足够的有效盯盘采样。</span>
        </div>
      )}

      <h3 className="knowledge-threshold-title">账户判断标准</h3>
      <p className="ops-role-desc">
        这里沉淀你自己的运营判断标准、指标口径和可复用规则。当前先开放“账户判断标准”，后续的策略经验和有效动作也在这里沉淀。
      </p>
      <p className="ops-role-desc">
        填了就用你填的值；留空则自动：先用本账户历史分位，样本不足再退回通用参考线
        （并在报告里标明"非本账户"）。
        {profile ? ` 当前策略 v${profile.version}。` : ""}
      </p>

      <div className="threshold-table-wrap">
        <table className="threshold-table">
        <thead>
          <tr>
            <th>指标</th>
            <th>你设定的值</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          {FIELDS.map((field) => (
            <tr key={field.key}>
              <td>{field.label}</td>
              <td>
                <input
                  aria-label={field.label}
                  inputMode="decimal"
                  placeholder="留空=自动"
                  value={values[field.key] ?? ""}
                  onChange={(event) =>
                    setValues((current) => ({ ...current, [field.key]: event.target.value }))
                  }
                />
                <span className="threshold-unit">{field.unit}</span>
              </td>
              <td>{field.hint}</td>
            </tr>
          ))}
        </tbody>
        </table>
      </div>

      <div className="live-watch-actions">
        <button className="button-outline" type="button" onClick={handleSave} disabled={busy || !profile}>
          {busy ? "保存中" : "保存为新版本"}
        </button>
        <button className="button-outline" type="button" onClick={resetAll} disabled={busy}>
          全部改回自动
        </button>
      </div>

      {notice ? <p className="monitor-signal">{notice}</p> : null}
      <p className="monitor-signal">
        说明：ROI 目标不在这里设——它跟着千川计划里的「综合营销ROI目标」走，避免盯盘和复盘用到两个目标。
      </p>
    </section>
  );
}
