type ToolIconName =
  | "live_watch"
  | "decisions"
  | "jobs"
  | "llm"
  | "learning"
  | "evaluation"
  | "feishu"
  | "advanced"
  | "api"
  | "asset";

export function ToolIcon({ name }: { name: ToolIconName }) {
  const props = {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true
  };

  if (name === "live_watch") {
    return <svg {...props}><path d="M3 12h4l2.2-7 4.1 14 2.2-7H21" /></svg>;
  }
  if (name === "decisions") {
    return <svg {...props}><path d="M4 7h10M18 7h2M4 17h2M10 17h10" /><circle cx="16" cy="7" r="2" /><circle cx="8" cy="17" r="2" /></svg>;
  }
  if (name === "jobs") {
    return <svg {...props}><path d="M5 5h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H9l-5 3v-13a2 2 0 0 1 2-2Z" /><path d="M8 10h8M8 13h5" /></svg>;
  }
  if (name === "llm") {
    return <svg {...props}><rect x="7" y="7" width="10" height="10" rx="2" /><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3" /><path d="M10 10h4v4h-4z" /></svg>;
  }
  if (name === "learning") {
    return <svg {...props}><path d="M6 4h12a2 2 0 0 1 2 2v14H8a4 4 0 0 1-4-4V6a2 2 0 0 1 2-2Z" /><path d="M8 8h8M8 12h8M8 16h5" /></svg>;
  }
  if (name === "evaluation") {
    return <svg {...props}><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="9" cy="9" r="2" /><path d="m21 15-5-5L5 20" /></svg>;
  }
  if (name === "feishu") {
    return <svg {...props}><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></svg>;
  }
  if (name === "advanced" || name === "api") {
    return <svg {...props}><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5" /><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" /></svg>;
  }
  return <svg {...props}><path d="m12 2 9 5-9 5-9-5Z" /><path d="m3 12 9 5 9-5M3 17l9 5 9-5" /></svg>;
}

