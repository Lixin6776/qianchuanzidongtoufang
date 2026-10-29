# 策略与执行闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 完成策略建议激活/评估/保留/回滚，以及执行任务回流数据资产。

**Architecture:** 复用现有 `StrategyProfile`、`StrategySuggestion`、`StrategyEvaluation`、`ExecutionJob`、`LearningCase` 和 `watch_analysis` 投影；增加生命周期字段、评估方法和统一执行回流 API，再挂载到数据资产 UI。

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, Alembic, pytest, React, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-29-strategy-execution-closed-loop-design.md`

## Global Constraints

- 不自动激活策略，不自动回滚，不自动执行账户操作。
- 评估样本不足时不给方向。
- 所有效果均为观察性相关，不是因果。
- 执行任务无法精确关联时只能标“候选关联”。

## Task 1: Schema and Profile Lifecycle

**Files:** `backend/app/models.py`, `backend/app/schemas.py`, `backend/app/services/profiles.py`, `backend/alembic/versions/0003_strategy_execution_loop.py`, `backend/app/db_schema.py`, `backend/tests/test_learning_api.py`, `backend/tests/test_profiles.py`

- [x] Add lifecycle fields and idempotent runtime column migration.
- [x] Add profile activation and rollback service methods.
- [x] Test accept → activate → rollback.

## Task 2: Suggestion Evaluation

**Files:** `backend/app/api/learning.py`, `backend/app/services/evaluation.py`, `backend/app/services/learning.py`, tests.

- [x] Add `evaluate_watch_window`.
- [x] Add activate/evaluate/keep/rollback endpoints.
- [x] Test sample insufficient and positive/negative/neutral.
- [x] Ensure evaluation is observation-only.

## Task 3: Execution Feedback

**Files:** new `backend/app/services/execution_feedback.py`, `backend/app/api/learning.py`, tests.

- [x] Build execution rows from `ExecutionJob` + `LearningCase`.
- [x] Match platform operation cases by action/time, exact IDs first, candidate otherwise.
- [x] Expose `/api/learning/execution-cases`.
- [x] Test linked/candidate/unlinked/failed.

## Task 4: Data Asset UI

**Files:** `frontend/src/components/DataAssetPanel.tsx`, new strategy/execution panels, `frontend/src/lib/api.ts`, tests, `frontend/src/styles/tokens.css`.

- [x] Add “策略建议” tab with lifecycle actions.
- [x] Add “执行回流” tab with source/status/link evidence.
- [x] Add API client types/functions.
- [x] Test empty, insufficient, linked and candidate states.

## Task 5: Verification

- [x] Backend full pytest.
- [x] Frontend Vitest and production build.
- [x] Impeccable detect.
- [x] Real DB smoke: evaluate current history and read execution cases.
- [x] Commit and push.
