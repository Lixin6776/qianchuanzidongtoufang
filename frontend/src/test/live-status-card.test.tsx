import { render, screen } from "@testing-library/react";

import { LiveStatusCard } from "../components/LiveStatusCard";
import type { LiveWatchReport } from "../lib/api";

const report: LiveWatchReport = {
  id: "watch-1",
  created_at: "2026-10-20T14:25:20+08:00",
  captured_at: "2026-10-20T14:24:49+08:00",
  level: "normal",
  source: "cdp",
  roi: 2.19,
  spend: 52388.57,
  gmv: 114836.1,
  gpm: 3912.69,
  cpm: 86.88,
  online_viewers: 33,
  orders: 696,
  spend_delta: 50,
  roi_target: 2.8,
  exposure_view_rate: 3.48,
  room_name: "质润官方旗舰店",
  session_status: "active",
  verify_passed: true,
  problems: ["ROI 未达标：当前 2.19，目标 2.80，缺口 0.61"],
  adjustments: ["先收缩低效素材，10～20 分钟后复核 ROI"],
  operations: [],
  report_markdown: "## 直播盯盘报表"
};

test("live status card surfaces the latest room and operator metrics", () => {
  render(<LiveStatusCard report={report} refreshMs={0} />);

  expect(screen.getByText("质润官方旗舰店")).toBeInTheDocument();
  expect(screen.getByText("需要关注")).toBeInTheDocument();
  expect(screen.getByText("¥10/分")).toBeInTheDocument();
  expect(screen.getByText("2.19")).toBeInTheDocument();
  expect(screen.getByText("¥86.88")).toBeInTheDocument();
  expect(screen.getByText("3.48%")).toBeInTheDocument();
  expect(screen.getByText(/ROI 未达标/)).toBeInTheDocument();
  expect(screen.getByText(/先收缩低效素材/)).toBeInTheDocument();
});
