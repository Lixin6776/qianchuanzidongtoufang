import { render, screen } from "@testing-library/react";

import { ChatReportCard } from "../components/ChatReportCard";

const REPORT = `## 直播盯盘报表 · 10-20 14:25

> 质润官方旗舰店　|　综合营销ROI目标 2.80　|　数据源 cdp

### 实时数据

| 指标 | 数值 |
| --- | ---: |
| 综合营销 ROI | 2.19 |
| 综合成本 | ¥52,388.57 |
| 实时在线人数 | 33 |

### 发现的问题

- **综合营销 ROI 未达标** — 当前 2.19，目标 2.80，先看承接和素材效率。

### 调整方案（需你确认）

1. 先暂停低效追投，10～20 分钟后复核 ROI。

### 操作日志

- 14:14 新建素材追投。
`;

test("chat report card keeps the operator summary visible and details collapsed", () => {
  const { container } = render(<ChatReportCard content={REPORT} />);

  expect(screen.getByText("5 分钟盯盘")).toBeInTheDocument();
  expect(screen.getAllByText("直播盯盘报表 · 10-20 14:25").length).toBeGreaterThan(0);
  expect(screen.getAllByText("综合营销 ROI").length).toBeGreaterThan(0);
  expect(screen.getAllByText("2.19").length).toBeGreaterThan(0);
  expect(screen.getAllByText(/综合营销 ROI 未达标/).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/先暂停低效追投/).length).toBeGreaterThan(0);
  expect(screen.getByText("展开完整报表")).toBeInTheDocument();

  const details = container.querySelector("details");
  expect(details).not.toBeNull();
  expect(details?.open).toBe(false);
  expect(container.querySelector(".report-message")).not.toBeNull();
});
