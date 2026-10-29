# 素材实验闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 把素材分析从报告延伸到可追踪的素材实验和结果评估。

**Architecture:** 素材分析报告增加结构化 `material_actions` 和当时的素材快照；新增 `material_experiments` 表记录建议、观察窗口和结果；数据资产新增“素材实验”页签。实验只通过人工操作开始/停止/评估，不自动修改账户。

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, pytest, React, Vitest.

## Global Constraints

- 不自动上传、替换、绑定、删除素材或修改预算。
- 评估只使用下一份素材分析快照；没有新快照时标记数据不足。
- 结论是观察性相关，不写成因果。
- 实验结果必须可追溯到素材 ID、分析日期、动作和观察窗口。

## Task 1: Structured Material Actions

- [x] Add `material_actions` and material snapshot to `build_material_analysis`.
- [x] Test real material rows produce actionable, deduplicated suggestions.
- [x] Keep the existing Markdown report unchanged.

## Task 2: Material Experiment Persistence and Service

- [x] Add `MaterialExperiment` model/schema and migration.
- [x] Add create/list/start/evaluate/stop service methods.
- [x] Test insufficient snapshot, positive result, negative result and stop.

## Task 3: API and Data Asset UI

- [x] Add `/api/material-experiments` endpoints.
- [x] Add `getMaterialExperiments/create/start/evaluate/stop` client functions.
- [x] Add “素材实验” tab with action suggestions and experiment lifecycle.
- [x] Add empty, insufficient and evaluated states.

## Task 4: Verification

- [x] Backend full pytest and Ruff.
- [x] Frontend Vitest and production build.
- [x] Impeccable detection.
- [x] Real API smoke without creating fake account actions.
- [x] Commit and push.
