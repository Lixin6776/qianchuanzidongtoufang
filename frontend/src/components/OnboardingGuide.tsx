import { useEffect, useState } from "react";

import {
  connectCdp,
  getApiConnectionStatus,
  getCdpConnection,
  getLiveWatchLogs,
  getLlmConnectionStatus,
  getLocalConfig,
  getSystemDoctor
} from "../lib/api";

type Step = {
  key: string;
  title: string;
  done: boolean;
  hint: string;
  optional?: boolean;
  action?: { label: string; kind: "connect" | "open" | "tick" | "doctor"; target?: string };
};

/**
 * 新手上路：把“客户能自己跑出第一份报表”要做的几件事串成清单。
 * 每项自动检测状态；全部完成就自动隐藏，系统自检入口始终保留在左侧导航。
 */
export function OnboardingGuide({
  onOpenWindow,
  onTick
}: {
  onOpenWindow?: (windowId: string) => void;
  onTick?: () => void;
}) {
  const [steps, setSteps] = useState<Step[]>([]);
  const [busy, setBusy] = useState(false);
  const [hidden, setHidden] = useState(
    () => window.localStorage.getItem("qca_onboarding_hidden") === "1"
  );

  async function refresh() {
    const [cfg, cdp, api, doctor, llm, logs] = await Promise.all([
      getLocalConfig().catch(() => null),
      getCdpConnection().catch(() => null),
      getApiConnectionStatus().catch(() => null),
      getSystemDoctor().catch(() => null),
      getLlmConnectionStatus().catch(() => null),
      getLiveWatchLogs(1).catch(() => [])
    ]);
    const roomName = (cfg as { effective?: { room_name?: string } } | null)?.effective?.room_name || "";
    const cdpOn = Boolean((cdp as { connected?: boolean } | null)?.connected);
    const apiStatus = api as { configured?: boolean; advertiser_id?: number } | null;
    const apiOn = Boolean(apiStatus?.configured && Number(apiStatus?.advertiser_id) > 0);
    const dataSourceOn = cdpOn || apiOn;
    const doctorBlocked = (doctor as { status?: string } | null)?.status === "blocked";
    const doctorDone = Boolean(doctor) && !doctorBlocked;
    const llmOn = Boolean(
      (llm as { configured?: boolean; api_key_configured?: boolean } | null)?.configured ||
        (llm as { api_key_configured?: boolean } | null)?.api_key_configured
    );
    const hasReport = Array.isArray(logs) && logs.length > 0;

    setSteps([
      {
        key: "config",
        title: "填写直播间名称（和账户 ID）",
        done: Boolean(roomName),
        hint: roomName ? `当前：${roomName}` : "在「数据源」里填，不用改配置文件",
        action: { label: "去填写", kind: "open", target: "advanced" }
      },
      {
        key: "data_source",
        title: "连接数据源（本机浏览器）",
        done: dataSourceOn,
        hint: dataSourceOn
          ? apiOn
            ? "开放平台连接已配置"
            : "本机浏览器已连接"
          : "点这里自动拉起连接；第一次要在弹出的窗口登录千川",
        action: { label: dataSourceOn ? "查看连接" : "连接数据源", kind: dataSourceOn ? "open" : "connect", target: "advanced" }
      },
      {
        key: "doctor",
        title: "运行一键自检",
        done: doctorDone,
        hint: doctorDone ? "部署检查通过，可查看具体提醒" : "检查运行环境、数据库、数据连接和客户界面",
        action: { label: doctorDone ? "重新自检" : "运行自检", kind: "doctor", target: "system" }
      },
      {
        key: "llm",
        title: "填大模型 Key（运营助手对话要用）",
        done: llmOn,
        optional: true,
        hint: llmOn ? "已配置" : "可选：不填也能盯盘 / 复盘，只是运营助手聊不了天",
        action: { label: "去配置", kind: "open", target: "llm" }
      },
      {
        key: "report",
        title: "跑出第一份盯盘报表",
        done: hasReport,
        hint: hasReport ? "已有报表，报表会发到左侧聊天框" : "点这里立刻读一次",
        action: { label: "立即读取", kind: "tick" }
      }
    ]);
  }

  const required = steps.filter((s) => !s.optional);
  const requiredDone = required.length > 0 && required.every((s) => s.done);

  useEffect(() => {
    if (hidden || requiredDone) return;
    refresh();
    const timer = window.setInterval(refresh, 20000);
    return () => window.clearInterval(timer);
  }, [hidden, requiredDone]);

  if (hidden || steps.length === 0 || requiredDone) return null;

  const doneCount = required.filter((s) => s.done).length;

  async function run(step: Step) {
    if (!step.action) return;
    if (step.action.kind === "open" || step.action.kind === "doctor") {
      onOpenWindow?.(step.action.target || "");
      return;
    }
    if (step.action.kind === "tick") {
      onTick?.();
      return;
    }
    setBusy(true);
    try {
      await connectCdp("auto");
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="onboarding-guide">
      <header>
        <strong>新手上路（{doneCount}/{required.length}）</strong>
        <button
          className="button-outline"
          type="button"
          onClick={() => {
            window.localStorage.setItem("qca_onboarding_hidden", "1");
            setHidden(true);
          }}
        >
          我知道了
        </button>
      </header>
      <ol>
        {steps.map((step) => (
          <li key={step.key} className={step.done ? "is-done" : ""}>
            <span className="onboarding-mark">{step.done ? "✓" : "○"}</span>
            <span className="onboarding-title">
              {step.title}
              {step.optional ? "（可选）" : ""}
            </span>
            <span className="onboarding-hint">{step.hint}</span>
            {(!step.done || step.key === "doctor") && step.action ? (
              <button className="button-outline" type="button" onClick={() => run(step)} disabled={busy}>
                {step.action.label}
              </button>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
