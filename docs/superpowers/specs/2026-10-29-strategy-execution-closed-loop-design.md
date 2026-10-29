# 策略与执行闭环设计

## 目标

把现有工作台从“建议、确认、执行、审计”推进到可验证的运营闭环：

1. 策略建议可进入草案、激活、观察、评估、保留或回滚。
2. 已执行任务与操作流水建立强关联，执行结果自动回流数据资产。
3. 所有判断保持观察性，不把相关性写成因果。
4. 不自动修改账户；激活策略和回滚仍由人工触发。

## 当前问题

- `StrategySuggestion` 可采纳，但采纳只生成 inactive 草案，没有激活和后续评估。
- `StrategyProfileService` 只支持创建新活跃版本，没有显式激活、退役和回滚。
- `LearningCase` 已记录执行 job，但数据资产主要读取平台操作日志，执行任务与操作流水没有统一视图。
- 前端已有 `StrategySuggestionCard`，但没有挂到数据资产主窗口。

## 范围

### 策略建议生命周期

状态：

`proposed -> accepted -> active -> evaluated -> kept | rolled_back`

规则：

- `accept`：根据建议生成 inactive 草案，记录 `draft_profile_id`。
- `activate`：人工触发，将草案设为 active，旧版本设为 inactive，并记录 `activated_at`、`effective_at`。
- `evaluate`：人工触发，读取当前策略变更前后的盯盘快照，生成 `StrategyEvaluation`。
- `keep`：人工确认评估结果，建议状态改为 `kept`。
- `rollback`：人工触发，把上一版本重新设为 active，建议状态改为 `rolled_back`。
- 任何阶段都不自动修改千川账户。

### 评估口径

- 变更前窗口：`effective_at - 60 分钟`。
- 变更后窗口：`effective_at + 60 分钟`，或当前可用的最新窗口。
- 最少有效样本：20 条盯盘记录。
- 指标：综合营销 ROI、GPM、消耗、ROI 达标率。
- `effect_size = 变更后 ROI 中位数 - 变更前 ROI 中位数`。
- 判定：
  - 样本不足：`insufficient`
  - `effect_size > 0.1`：`positive`
  - `effect_size < -0.1`：`negative`
  - 其他：`neutral`
- 结论必须写“观察性相关，不是因果”，并展示样本数、窗口和缺失数据。

### 执行结果回流

- `ExecutionJob` 保留 `confirmation_id`、`action_name`、`result.before`、`result.after`、状态和完成时间。
- `LearningCase` 继续记录 `execution_job_id`、`confirmation_id`、上下文和结果。
- 数据资产操作流水增加执行来源信息：
  - `source = platform | execution | linked`
  - `confirmation_id`
  - `execution_job_id`
  - `execution_status`
  - `execution_before`
  - `execution_after`
- 关联规则：
  1. 优先使用 `confirmation_id` / `execution_job_id` 精确关联。
  2. 没有精确 ID 时，按动作类型和时间窗口做候选关联，但标为“候选关联”，不冒充精确关联。
  3. 只有平台日志、没有执行任务的记录继续显示为 `platform`。
  4. 只有执行任务、没有平台日志的记录显示为 `execution`，并提示“平台日志尚未回流”。
- 同一动作在平台日志和执行任务中重复出现时，只保留一条主记录，另一条作为关联证据附上。

## 后端接口

- `POST /api/learning/suggestions/{id}/accept`
  - 返回 suggestion，包含 `draft_profile_id`。
- `POST /api/learning/suggestions/{id}/activate`
  - 激活草案，返回 profile 和 suggestion。
- `POST /api/learning/suggestions/{id}/evaluate`
  - 生成评估，返回 evaluation。
- `POST /api/learning/suggestions/{id}/keep`
  - 标记策略保留。
- `POST /api/learning/suggestions/{id}/rollback`
  - 激活父版本并标记回滚。
- `GET /api/learning/execution-cases`
  - 返回执行任务、学习案例和结果的统一视图。

## 前端

数据资产增加两个页签：

1. “策略建议”
   - 建议类型、证据、置信度、草案版本、状态。
   - 操作：采纳、激活、评估、保留、回滚、拒绝。
   - 展示评估窗口、样本数、效果值、判定和“观察性相关”声明。

2. “执行回流”
   - 展示执行任务、确认单、动作、执行前后、状态、是否有平台日志。
   - 与操作流水互相链接。

## 安全和失败处理

- 未激活草案不能用于执行。
- 评估样本不足时，不显示“有效/无效”方向。
- 回滚需要明确目标版本，不能直接覆盖历史。
- 执行状态为 `failed`、`unknown`、`cancelled` 时，数据资产只展示事实，不推断业务效果。
- 关联不明确时必须显示“候选关联”。
- 所有状态变更写审计日志。

## 测试与验收

- 后端单元/集成测试：
  - 建议 accept、activate、evaluate、keep、rollback 状态流转。
  - 样本不足、正/负/中性评估。
  - 执行任务与平台日志的精确/候选/无关联。
  - 执行失败不生成虚假结果。
- 前端测试：
  - 策略建议按钮和状态展示。
  - 执行回流和候选关联提示。
  - 样本不足不出现方向性结论。
- 真实数据冒烟：
  - 用当前 2592 条历史数据跑一次评估。
  - 确认执行 job 出现在数据资产中。
  - 确认不触发任何千川写操作。

## 非目标

- 不自动激活策略。
- 不自动回滚策略。
- 不自动执行账户操作。
- 不把 60 分钟观察窗口包装成因果证明。
- 不引入多用户和云端权限系统。
