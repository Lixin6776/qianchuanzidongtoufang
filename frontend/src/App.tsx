import { useEffect, useRef, useState } from "react";

import { ActionParameterForm } from "./components/ActionParameterForm";
import { ApiConnectionPanel } from "./components/ApiConnectionPanel";
import { ChatPanel, type ActionPreview, type ChatReply } from "./components/ChatPanel";
import { LiveReviewList, type LiveReview } from "./components/LiveReviewList";
import { LiveStatusCard } from "./components/LiveStatusCard";
import { OnboardingGuide } from "./components/OnboardingGuide";
import { DataAssetPanel } from "./components/DataAssetPanel";
import { OpsChatPanel } from "./components/OpsChatPanel";
import { MaterialAnalysisList, type MaterialAnalysis } from "./components/MaterialAnalysisList";
import { FeishuConnectionPanel } from "./components/FeishuConnectionPanel";
import { ConfirmationDialog } from "./components/ConfirmationDialog";
import { DataSourcePanel } from "./components/DataSourcePanel";
import { DecisionPanel } from "./components/DecisionPanel";
import { type LiveMonitorEvent } from "./components/LiveMonitorPanel";
import { LlmConnectionPanel } from "./components/LlmConnectionPanel";
import { StrategyBanner, type StrategyBannerProfile } from "./components/StrategyBanner";
import { ThresholdPanel } from "./components/ThresholdPanel";
import { ToolIcon } from "./components/ToolIcon";
import {
  connectMonitor,
  createActionConfirmation,
  executeActionConfirmation,
  getActiveProfile,
  createStrategyProfile,
  getExecutionJobs,
  getApiConnectionStatus,
  getLiveReviews,
  getLiveWatchLogs,
  getMaterialAnalyses,
  generateMaterialAnalysis,
  connectNotifications,
  previewAction,
  sendChat,
  tickLiveWatch
} from "./lib/api";

type ActiveStrategyProfile = StrategyBannerProfile & {
  name?: string;
  secondary_objectives?: string[];
  monitoring_config?: Record<string, unknown>;
  allowed_actions?: string[];
  notification_policy?: Record<string, unknown>;
};

type OperationMode = "read_only" | "confirm_automation";

const AUTOMATION_ACTIONS = [
  "pause_plan",
  "enable_plan",
  "update_plan_budget",
  "create_plan",
  "copy_plan",
  "edit_plan",
  "update_plan_bid",
  "update_targeting",
  "update_schedule",
  "bind_existing_material",
  "unbind_existing_material"
];

function normalizeStrategyProfile(value: unknown): ActiveStrategyProfile {
  const raw = (value ?? {}) as Partial<ActiveStrategyProfile>;
  return {
    version: raw.version ?? 0,
    name: raw.name,
    business_direction: raw.business_direction ?? "未加载",
    primary_objective: raw.primary_objective ?? "等待本地服务返回投放策略",
    secondary_objectives: raw.secondary_objectives ?? [],
    hard_constraints: raw.hard_constraints ?? {},
    monitoring_config: raw.monitoring_config ?? { interval_minutes: 5 },
    allowed_actions: raw.allowed_actions ?? [],
    notification_policy: raw.notification_policy ?? { dedupe_minutes: 10 },
    data_time: raw.data_time ?? raw.effective_at ?? raw.created_at ?? new Date().toISOString(),
    freshness: "fresh"
  };
}

const fallbackProfile: ActiveStrategyProfile = normalizeStrategyProfile({
  version: 0,
  business_direction: "未加载",
  primary_objective: "等待本地服务返回投放策略",
  hard_constraints: {},
  data_time: new Date().toISOString()
});
fallbackProfile.freshness = "stale";

type ExecutionJob = {
  id: string;
  action_name: string;
  status: string;
  created_at: string;
};

type ToolWindow = "live_watch" | "decisions" | "jobs" | "llm" | "api" | "learning" | "evaluation" | "feishu" | "advanced" | "asset";

const tools: Array<{ id: ToolWindow; label: string }> = [
  { id: "live_watch", label: "直播盯盘" },
  { id: "decisions", label: "决策" },
  { id: "jobs", label: "直播运营助手" },
  { id: "llm", label: "大模型" },
  { id: "learning", label: "直播复盘" },
  { id: "evaluation", label: "素材分析" },
  { id: "feishu", label: "飞书" },
  { id: "advanced", label: "数据源" },
  { id: "asset", label: "数据资产" }
];

export default function App() {
  const [profile, setProfile] = useState<ActiveStrategyProfile>(fallbackProfile);
  const [selectedPreview, setSelectedPreview] = useState<ActionPreview | null>(null);
  const [jobs, setJobs] = useState<ExecutionJob[]>([]);
  const [reviews, setReviews] = useState<LiveReview[]>([]);
  const [materialAnalyses, setMaterialAnalyses] = useState<MaterialAnalysis[]>([]);
  const [apiStatus, setApiStatus] = useState({ configured: false, provider_preference: "cdp" as "api" | "cdp" });
  const [monitorEvent, setMonitorEvent] = useState<LiveMonitorEvent | null>(null);
  const [incomingMessage, setIncomingMessage] = useState<{ id: string; content: string } | null>(null);
  // 直播运营助手对话（跨场次保留，独立于本场聊天框）
  const [opsIncoming, setOpsIncoming] = useState<{ id: string; content: string } | null>(null);
  const [activeWindow, setActiveWindow] = useState<ToolWindow | null>(null);
  const [chatResetKey, setChatResetKey] = useState(0);
  const [modeBusy, setModeBusy] = useState(false);
  const [modeNotice, setModeNotice] = useState("");
  const navRef = useRef<HTMLElement | null>(null);
  const topContextRef = useRef<HTMLDivElement | null>(null);
  const workspaceRef = useRef<HTMLDivElement | null>(null);
  const [mainWindowHeight, setMainWindowHeight] = useState<number | null>(null);

  useEffect(() => {
    const topContext = topContextRef.current;
    const workspace = workspaceRef.current;
    if (!topContext || !workspace) return;
    const updateHeight = () => {
      if (window.innerWidth <= 980) {
        setMainWindowHeight(null);
        return;
      }
      const documentTop = workspace.getBoundingClientRect().top + window.scrollY;
      const available = window.innerHeight - documentTop - 40;
      setMainWindowHeight(Math.max(480, Math.ceil(available)));
    };
    updateHeight();
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(updateHeight) : null;
    observer?.observe(topContext);
    window.addEventListener("resize", updateHeight);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", updateHeight);
    };
  }, []);

  useEffect(() => {
    getActiveProfile()
      .then((value) => setProfile(normalizeStrategyProfile(value)))
      .catch(() => setProfile(fallbackProfile));
    getExecutionJobs().then((value) => setJobs(value as ExecutionJob[])).catch(() => undefined);
    getLiveReviews().then(setReviews).catch(() => undefined);
    getMaterialAnalyses()
      .then((value) => {
        setMaterialAnalyses(value);
        if (value[0]) setIncomingMessage({ id: value[0].id, content: value[0].report_markdown });
      })
      .catch(() => undefined);
    getApiConnectionStatus().then(setApiStatus).catch(() => undefined);
    const disconnectMonitor = connectMonitor((event) => setMonitorEvent(event as LiveMonitorEvent));
    const disconnectNotifications = connectNotifications((event) => {
      const payload = event as { type?: string; id?: string; message?: string; created_at?: string };
      if (payload.type === "session_started") {
        // 新场次开播：清空上一场的对话记录
        setChatResetKey((value) => value + 1);
        setIncomingMessage(null);
        return;
      }
      if (!payload.id || !payload.message) return;
      if (payload.type === "live_watch") {
        // 每 5 分钟一条盯盘报表 -> 只进聊天框
        setIncomingMessage({ id: payload.id, content: payload.message });
        return;
      }
      if (payload.type === "ops_chat") {
        // 运营助手：每日汇报 / 每场复盘 / 对话回答
        setOpsIncoming({ id: payload.id, content: payload.message });
        return;
      }
      if (payload.type !== "material_analysis") return;
      const analysis = {
        id: payload.id,
        date: new Date(payload.created_at ?? Date.now()).toISOString().slice(0, 10),
        created_at: payload.created_at ?? new Date().toISOString(),
        report_markdown: payload.message
      };
      setMaterialAnalyses((current) =>
        current.some((item) => item.id === analysis.id) ? current : [analysis, ...current]
      );
      setIncomingMessage({ id: analysis.id, content: analysis.report_markdown });
    });
    return () => {
      disconnectMonitor();
      disconnectNotifications();
    };
  }, []);

  // SSE 兜底：轮询最近的盯盘报表，保证每 5 分钟的报表一定进聊天框
  useEffect(() => {
    const seen = { id: "" };
    let first = true;
    let stopped = false;
    let timer: number | null = null;

    const poll = async () => {
      if (stopped) return;
      try {
        const logs = await getLiveWatchLogs(1);
        const latest = logs[0];
        if (!latest) return;
        if (latest.session_status === "ended" || latest.session_status === "stopped") {
          stopped = true;
          if (timer !== null) window.clearInterval(timer);
          timer = null;
        }
        if (first) {
          // 首次只记录，不把历史报表重新灌进聊天
          first = false;
          seen.id = latest.id;
          return;
        }
        if (seen.id === latest.id) return;
        seen.id = latest.id;
        setIncomingMessage({ id: latest.id, content: latest.report_markdown });
      } catch {
        // 网络异常时保留轮询，恢复后继续同步
      }
    };

    void (async () => {
      await poll();
      if (!stopped) timer = window.setInterval(poll, 20000);
    })();

    return () => {
      stopped = true;
      if (timer !== null) window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    const review = monitorEvent?.review as LiveReview | undefined;
    if (!review) return;
    setReviews((current) =>
      current.some((item) => item.id === review.id) ? current : [review, ...current]
    );
    setIncomingMessage({ id: review.id, content: review.report_markdown });
  }, [monitorEvent]);

  const operationMode: OperationMode =
    profile.hard_constraints.automation_mode === "confirm_required" &&
    (profile.allowed_actions?.length ?? 0) > 0
      ? "confirm_automation"
      : "read_only";

  async function switchOperationMode(targetMode: OperationMode) {
    if (targetMode === operationMode || modeBusy) return;
    setModeBusy(true);
    setModeNotice("");
    try {
      const created = await createStrategyProfile({
        name: profile.name || "质润官方旗舰店 · 直播运营策略",
        business_direction: profile.business_direction,
        primary_objective: profile.primary_objective,
        secondary_objectives: profile.secondary_objectives ?? [],
        hard_constraints: {
          ...profile.hard_constraints,
          read_only: targetMode === "read_only",
          automation_mode: targetMode === "read_only" ? "read_only" : "confirm_required"
        },
        monitoring_config: profile.monitoring_config ?? { interval_minutes: 5 },
        allowed_actions: targetMode === "read_only" ? [] : AUTOMATION_ACTIONS,
        notification_policy: profile.notification_policy ?? { dedupe_minutes: 10 }
      });
      setProfile(normalizeStrategyProfile(created));
      setModeNotice(
        targetMode === "read_only"
          ? "已切回只读模式"
          : "已启用自动投放，执行前需确认"
      );
      window.setTimeout(() => setModeNotice(""), 3500);
    } catch {
      setModeNotice("模式切换失败，请检查策略服务");
    } finally {
      setModeBusy(false);
    }
  }
  async function handleSend(message: string, images: string[] = []): Promise<ChatReply> {
    const result = await sendChat(message, images);
    return {
      message: result.message as string,
      preview: result.preview as ActionPreview | undefined
    };
  }

  async function handleAdvancedAction(actionName: string, params: Record<string, unknown>) {
    const targetId = String(params.target_id);
    const actionParams = Object.fromEntries(
      Object.entries(params).filter(([key]) => key !== "target_id")
    );
    const preview = await previewAction({
      action_name: actionName,
      target_id: targetId,
      params: actionParams
    });
    setSelectedPreview(preview as ActionPreview);
    setActiveWindow(null);
  }

  async function confirmAction(preview: ActionPreview) {
    const confirmation = await createActionConfirmation({
      action_name: preview.action_name,
      target_id: preview.target_id,
      params: preview.normalized_params
    });
    const job = await executeActionConfirmation(confirmation.id);
    setJobs((current) => [job as ExecutionJob, ...current]);
    setSelectedPreview(null);
  }

  function renderWindow() {
    if (activeWindow === "decisions") {
      // 「决策」= 判断标准（阈值由你来定）
      return <ThresholdPanel />;
    }
    if (activeWindow === "jobs") {
      // 直播运营助手 = 一个能对话的资深运营（执行记录折叠在下方）
      return <OpsChatPanel incomingMessage={opsIncoming} jobs={jobs} />;
    }
    if (activeWindow === "llm") return <LlmConnectionPanel />;
    if (activeWindow === "api") {
      return (
        <ApiConnectionPanel
          configured={apiStatus.configured}
          providerPreference={apiStatus.provider_preference}
        />
      );
    }
    if (activeWindow === "learning") return <LiveReviewList reviews={reviews} />;
    if (activeWindow === "evaluation") {
      return (
        <MaterialAnalysisList
          analyses={materialAnalyses}
          onGenerate={async () => {
            const analysis = await generateMaterialAnalysis();
            setMaterialAnalyses((current) =>
              current.some((item) => item.id === analysis.id) ? current : [analysis, ...current]
            );
            setIncomingMessage({ id: analysis.id, content: analysis.report_markdown });
          }}
        />
      );
    }
    if (activeWindow === "feishu") return <FeishuConnectionPanel />;
    if (activeWindow === "asset") {
      return <DataAssetPanel />;
    }
    if (activeWindow === "advanced") {
      // 「数据源」：CDP 与 API 两条读取链路统一在这里管
      return <DataSourcePanel />;
    }
    return null;
  }

  const activeLabel = tools.find((item) => item.id === activeWindow)?.label;

  return (
    <div className="app-shell">
      <div className="top-context" ref={topContextRef}>
        <StrategyBanner profile={profile} />
        <LiveStatusCard />
        <OnboardingGuide
          onOpenWindow={(windowId) => {
            if (!windowId) return;
            setActiveWindow(windowId === "live_watch" ? null : windowId as ToolWindow);
          }}
          onTick={() => {
            // 引导里的"立即读取"：直接触发一轮盯盘
            tickLiveWatch().catch(() => undefined);
          }}
        />
      </div>
      <div className="workspace byte-workspace" ref={workspaceRef}>
        <nav className="tool-nav panel" aria-label="功能导航" ref={navRef}>
          <div className="tool-nav-list">
            {tools.map((item) => {
              const isActive = activeWindow === item.id || (item.id === "live_watch" && activeWindow === null);
              return (
                <button
                  className={isActive ? "tool-nav-item active" : "tool-nav-item"}
                  key={item.id}
                  type="button"
                  onClick={() => setActiveWindow(item.id === "live_watch" ? null : item.id)}
                >
                  <span className="tool-nav-main">
                    <span className="tool-nav-short" aria-hidden="true"><ToolIcon name={item.id} /></span>
                    <span>{item.label}</span>
                  </span>
                </button>
              );
            })}
          </div>
          <div className={`tool-nav-footer mode-${operationMode}`}>
            <div className="tool-nav-mode-heading">
              <span className="tool-nav-status-dot" aria-hidden="true" />
              <div>
                <strong>{operationMode === "read_only" ? "只读运营模式" : "全自动化投放模式"}</strong>
                <span>
                  {operationMode === "read_only"
                    ? "只分析 · 不执行账户操作"
                    : "自动生成任务 · 执行前人工确认"}
                </span>
              </div>
            </div>
            <div className="tool-nav-mode-switch" role="group" aria-label="运营模式">
              <button
                type="button"
                className={operationMode === "read_only" ? "active" : ""}
                aria-pressed={operationMode === "read_only"}
                disabled={modeBusy}
                onClick={() => switchOperationMode("read_only")}
              >
                只读
              </button>
              <button
                type="button"
                className={operationMode === "confirm_automation" ? "active" : ""}
                aria-pressed={operationMode === "confirm_automation"}
                disabled={modeBusy}
                onClick={() => switchOperationMode("confirm_automation")}
              >
                全自动
              </button>
            </div>
            {modeNotice ? <span className="tool-nav-mode-notice">{modeNotice}</span> : null}
          </div>
        </nav>
        <main className="chat-main" style={mainWindowHeight ? { height: `${mainWindowHeight}px` } : undefined}>
          {activeWindow ? (
            <section className="main-tool-window panel" role="region" aria-label={activeLabel}>
              <header className="main-tool-window-header">
                <div>
                  <p className="eyebrow">LIVE OPS · MODULE</p>
                  <h1>{activeLabel}</h1>
                </div>
                <button className="button-outline" type="button" onClick={() => setActiveWindow(null)}>
                  返回直播盯盘
                </button>
              </header>
              <div className="main-tool-window-body">{renderWindow()}</div>
            </section>
          ) : (
            <ChatPanel
              incomingMessage={incomingMessage}
              resetKey={chatResetKey}
              operationMode={operationMode}
              onSend={handleSend}
              onOpenConfirmation={setSelectedPreview}
            />
          )}
        </main>
      </div>

      {selectedPreview ? (
        <ConfirmationDialog
          preview={{ ...selectedPreview, constraints: profile.hard_constraints }}
          onConfirm={confirmAction}
          onCancel={() => setSelectedPreview(null)}
        />
      ) : null}
    </div>
  );
}

