# 数据资产增量预计算 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 让数据资产四个页签不再反复解析完整盯盘 payload，并将常用计算稳定压到几秒内。

**Architecture:** 在 SQLite 中新增轻量分析投影表，只保存时间、来源、消耗、成交和预解析操作；写入时增量维护，旧数据启动时自动回填。分析接口读取投影，不再读取包含大素材数组和 Markdown 的完整 payload。

**Tech Stack:** Python, SQLite, FastAPI, pytest, React/Vitest。

**Spec:** 上一轮已验证的“操作流水增量预计算”方向及用户要求：数据准确优先、没读到不伪造、口径不变。

## Global Constraints

- 不改变操作反馈、决策场景、操作流水的统计口径。
- 分析投影必须由原始 payload 派生，不能手填。
- 新记录写入时自动维护投影；旧记录自动回填。
- 任何读取失败都返回可识别空值，不伪造 0。
- 保留现有 20000 条滚动窗口和按时间倒序行为。

## Review Focus

- 旧 JSON 导入和已有 SQLite 历史数据必须自动回填。
- 同 ID 覆盖写入必须同步覆盖投影。
- 滚动删除必须同步删除投影，避免幽灵操作。
- 预解析操作必须保留任务、素材、预算、ROI 目标和原始摘要。
- 分析接口结果必须与旧实现逐字段一致。

---

### Task 1: SQLite 分析投影

**Files:**
- Modify: `backend/app/services/watch_log_store.py`
- Test: `backend/tests/test_watch_log_store.py`

**Interfaces:**
- Produces: `SqliteWatchLogStore.list_analysis_logs(limit: int = 20000) -> list[dict]`
- Produces: analysis rows shaped as `{id, created_at, source, spend, gmv, platform_operations, report_markdown}`

- [x] Write failing tests for incremental projection, same-ID replacement, legacy backfill, and retention deletion.
- [x] Run tests and confirm failure.
- [x] Add `watch_analysis` table and write/delete/read methods.
- [x] Run tests and confirm pass.

### Task 2: Reuse Pre-parsed Operations

**Files:**
- Modify: `backend/app/services/ops_outcome.py`
- Test: `backend/tests/test_ops_outcome.py`

**Interfaces:**
- Consumes: analysis rows from `list_analysis_logs`.
- Produces: identical `compute_ops_outcome`, `compute_scenarios`, `compute_op_cases`, `compute_asset_overview` outputs.

- [x] Write failing test proving `_operations` projection is honored and raw summaries survive.
- [x] Run test and confirm failure.
- [x] Teach operation extraction to use precomputed `_operations`.
- [x] Run tests and confirm pass.

### Task 3: Wire APIs and Verify Performance

**Files:**
- Modify: `backend/app/api/ops_outcome.py`
- Modify: `backend/app/services/live_watch.py` where ledger reads logs.
- Test: `backend/tests/test_ops_outcome.py`

- [x] Write failing API/store integration test if needed.
- [x] Switch analytics-only API reads to `list_analysis_logs`.
- [x] Run backend suite.
- [x] Benchmark all four endpoints on the real database.
- [x] Run frontend tests/build, impeccable, commit and push.
