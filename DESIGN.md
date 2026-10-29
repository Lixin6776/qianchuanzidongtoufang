---
name: 千川直播运营 Agent
description: 面向直播运营投手的本地实时运营台
colors:
  canvas: "#eef3f9"
  surface: "#ffffff"
  surface-muted: "#f7f8fa"
  navy: "#081a33"
  navy-raised: "#0b2142"
  ink: "#1d2129"
  text-secondary: "#646a73"
  border: "#e5e6eb"
  primary: "#2563eb"
  cyan: "#22d3ee"
  success: "#16a34a"
  warning: "#f59e0b"
  danger: "#e5484d"
typography:
  body:
    fontFamily: "Inter, system-ui, Noto Sans SC, Microsoft YaHei, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  heading:
    fontFamily: "Inter, system-ui, Noto Sans SC, Microsoft YaHei, sans-serif"
    fontSize: "28px"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.02em"
  data:
    fontFamily: "JetBrains Mono, SFMono-Regular, Consolas, monospace"
    fontSize: "21px"
    fontWeight: 600
    lineHeight: 1.25
rounded:
  sm: "4px"
  md: "8px"
  lg: "12px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
    padding: "6px 12px"
  tool-nav:
    backgroundColor: "{colors.navy}"
    textColor: "#dce9fa"
    rounded: "{rounded.lg}"
    padding: "10px"
  metric-card:
    backgroundColor: "{colors.navy-raised}"
    textColor: "#f8fbff"
    rounded: "{rounded.md}"
    padding: "10px 12px"
---

# Design System: 千川直播运营 Agent

## Overview

**Creative North Star: "Live Telemetry Desk"**

The interface should feel like a trusted live operations desk: calm enough to read under pressure, technical enough to signal real telemetry, and restrained enough that alert color is reserved for decisions. The dark navigation and telemetry strip frame a brighter working canvas where evidence, problem, action, and verification are read in that order.

This is an Operate surface, not a marketing surface. Familiar dashboard and chat patterns are intentional. Craft comes from precise hierarchy, compact data grouping, consistent iconography, explicit states, and a clear separation between read-only analysis and approval-based automation.

**Key Characteristics:**
- Dark operational frame around a light data workspace.
- Dense but grouped telemetry, never a wall of cards.
- ROI and GPM first; supporting metrics second.
- Semantic status color only when it changes a decision.
- Chinese operational language, tabular numerals, explicit units.
- Human confirmation remains visible at every write boundary.

## Colors

The palette combines a deep navy control surface with a cool neutral workspace and a small set of semantic accents.

### Primary
- **Operations Blue** (`#2563eb`): primary actions, active navigation, links, and key interactive emphasis.
- **Telemetry Cyan** (`#22d3ee`): live signal, active status, and system-level indicators. Used sparingly.

### Neutral
- **Deep Navy** (`#081a33`): global navigation and the live telemetry frame.
- **Raised Navy** (`#0b2142`): nested live metrics and control surfaces.
- **Canvas Blue-Gray** (`#eef3f9`): application background.
- **Work Surface** (`#ffffff`): reports, forms, and reading surfaces.
- **Muted Surface** (`#f7f8fa`): low-emphasis grouping and rows.
- **Primary Ink** (`#1d2129`): headings and primary values.
- **Secondary Ink** (`#646a73`): labels, metadata, and supporting copy.
- **Divider** (`#e5e6eb`): borders and separators.

### Semantic
- **Healthy Green** (`#16a34a`): normal state and successful completion.
- **Attention Amber** (`#f59e0b`): warnings requiring review.
- **Action Red** (`#e5484d`): blocking or immediate-action states.

**The Scarcity Rule.** Cyan and semantic colors are signals, not decoration. Do not color a component merely to make it look technical.

## Typography

**Display Font:** Inter / system UI with Noto Sans SC and Microsoft YaHei fallbacks  
**Body Font:** Inter / system UI with Noto Sans SC and Microsoft YaHei fallbacks  
**Data Font:** JetBrains Mono with SFMono-Regular and Consolas fallbacks

**Character:** The typography is operational rather than editorial: compact labels, confident headings, and tabular numerals that align across changing values.

### Hierarchy
- **Display** (600, 28–32px, 1.2): page-level operational headings.
- **Headline** (600, 18–24px, 1.3): module and major panel headings.
- **Title** (600, 14–17px, 1.4): report titles and section groups.
- **Body** (400, 13–15px, 1.55–1.7): evidence, explanations, and recommendations.
- **Label** (500–600, 10–12px, 1.4): metric names, metadata, and compact state labels.
- **Data** (600, 18–26px, tabular): ROI, GPM, spend, CPM, orders, and other measured values.

**The Unit Rule.** Every operational number must keep its unit or ratio context visible. Never display a bare value when the metric could be confused with another ROI or cost measure.

## Layout

- Desktop workspace width tracks the application frame with 32px side gutters; it is not capped at a narrow content column.
- Navigation uses a clamp between 220px and 280px; the main work surface takes the remaining width.
- Desktop navigation and the active main window fill the remaining viewport height. Internal content scrolls, not the whole page.
- The layout collapses to one column below 980px; navigation becomes a three-column tool grid and the chat/report workspace follows naturally.
- Spacing rhythm: 4, 8, 12, 16, 24, 32px. Tight grouping is used inside telemetry cards; larger separation separates decisions and supporting evidence.
- Chat reports keep the newest message in view; the stream scrolls to the latest incoming report.

## Elevation & Depth

Depth is created primarily with tonal separation: deep navy control surfaces, white reading surfaces, and cool-gray canvas. A single soft shadow is allowed for floating or currently active surfaces. Borders remain light and structural rather than decorative.

**The Two-Layer Rule.** Control and telemetry may be dark; evidence and editable content remain light. Do not introduce additional competing surface colors without a workflow reason.

## Shapes

- Small controls and inputs: 4px radius.
- Data tiles, reports, and standard panels: 8px radius.
- Major navigation and telemetry frames: 12px radius.
- Avoid pill shapes except for status badges and compact mode selectors.
- Use a consistent 1px structural border; do not use thick colored side tabs as card accents.

## Components

### Buttons
- **Shape:** 4px radius, minimum 32px height.
- **Primary:** Operations Blue background, white text, 6px 12px padding.
- **Outline:** white or transparent surface with 1px neutral border.
- **Focus:** visible 2px Operations Blue/cyan focus ring with 2px offset.
- **Disabled:** reduced opacity with a stable cursor; do not rely on color alone.

### Chips
- **Style:** compact 10–12px labels, 1px border, light tinted background.
- **Use:** mode, data source, state, and constraints.
- **Rule:** chips describe state; they do not replace headings.

### Cards / Containers
- **Corner Style:** 8–12px radius.
- **Background:** white workspace or raised navy telemetry.
- **Shadow Strategy:** soft single-level shadow for active/floating surfaces.
- **Border:** 1px neutral; no thick left/right accent bars.
- **Internal Padding:** 12–20px depending on information density.

### Inputs / Fields
- **Style:** white or near-white fill, 1px border, 4px radius.
- **Focus:** blue border plus 3px tinted focus halo.
- **Error:** explicit message with warning/danger color and recovery instruction.

### Navigation
- **Desktop:** dark navy vertical rail, SVG icons, text labels, active blue/cyan highlight.
- **Active state:** left-side signal cannot rely on a thick decorative border; use background tint, icon state, and text contrast together.
- **Footer:** operation mode switch with read-only and approval-based automation choices.
- **Mobile:** 3-column tool grid with the same icon and label vocabulary.

### Live Telemetry Card
- Dark navy frame with five compact metrics: comprehensive marketing ROI, GPM, recent spend, live viewers, CPM.
- ROI and GPM carry the strongest visual weight.
- Problems and recommendations are summarized in one compact diagnostic row and expand on demand.
- Status is communicated with label plus color, never color alone.
- When a session ends, the card stops live animation and states that polling has stopped.

### Report Cards
- White reading surface with a clear report type, time, status, and three key metrics.
- Full report details are collapsed by default.
- Problems and actions use tinted rows rather than side-tab borders.
- Reports must clearly distinguish comprehensive marketing ROI from material ROI.

### Mode Switch
- Read-only mode is the default.
- Approval-based automation is visibly distinct but not celebratory.
- Automation copy explicitly says execution still requires human confirmation.

## Do's and Don'ts

### Do
- **Do** keep ROI and GPM first in the telemetry hierarchy.
- **Do** use authored SVG icons with one consistent stroke system.
- **Do** show units, targets, time windows, and data sources next to values.
- **Do** keep the newest live report visible in the chat stream.
- **Do** make read-only versus approval-based automation obvious.
- **Do** use 1px structural borders and tonal layering for depth.
- **Do** preserve tabular numerals for all changing operational metrics.

### Don't
- **Don't** use Chinese characters or emoji as substitute icon systems.
- **Don't** use decorative grid-line backgrounds as a signal of “technology.”
- **Don't** use thick colored side tabs on cards or alerts.
- **Don't** put eyebrow/kicker labels above headings.
- **Don't** use color as the only indicator of success, warning, or failure.
- **Don't** mix comprehensive marketing ROI, material ROI, and payment ROI.
- **Don't** imply that approval-based automation executes without confirmation.
- **Don't** fill empty states with fabricated live data.
