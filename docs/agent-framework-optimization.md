# 架构分层说明

这份文档说明当前代码为什么采用
`runtime -> workflow -> orchestrator -> scoring / storage` 的分层方式。
重点是解释现状，方便继续维护，而不是提供一次性的迁移脚本。

## 当前分层

| 层 | 目录 | 责任 |
| --- | --- | --- |
| runtime | `glorious_mess_reviewer/runtime/` | 注册工作流、执行工作流、持久化会话 / 步骤 / 产物 |
| workflow | `glorious_mess_reviewer/workflows/` | 定义节点顺序、条件边、并行组和产物形状 |
| orchestrator | `glorious_mess_reviewer/orchestrator/` | 负责预检查、Agent 调用、fallback、projection |
| scoring | `glorious_mess_reviewer/scoring/` | 负责 rule caps、加权分数与 recommendation |
| storage | `glorious_mess_reviewer/storage/` | 负责 SQLite 表结构和查询接口 |

## 这样拆分的原因

- workflow 需要稳定描述“先做什么、哪些节点可并行、哪些条件会跳过下游节点”。
- orchestrator 需要专注在业务判断、fallback 和输出投影。
- scoring 需要保持纯规则函数，方便测试与 golden 回归。
- storage 需要单独管理工作流会话与 review 记录的持久化。

## 当前收益

- `screening.review.v1`、`screening.risk_audit.v1`、`screening.venue_fit_audit.v1`
  可以独立注册和查询。
- `/workflows` 会暴露 `edges`、`parallel_groups` 和 `artifact_keys`，外部系统可以按图结构理解执行计划。
- 完整初筛在 precheck 已经发现风险标记时会走 `risk_gate`，跳过 evidence / value / meta 面板，直接生成升级到人工风险复核的结构化结果。
- CLI 和 API 通过同一套 runtime wiring 运行，行为更一致。
- fallback 逻辑有稳定的 `raw_agent_outputs` envelope，利于审计和测试。
- 工作流会话 / 步骤 / 产物已经进入 SQLite，可直接做复盘。
- `benchmark` 把 fixture、真实 provider、baseline、workflow/baseline delta 诊断和 Markdown report 放到同一条验证链路中。
- Markdown intake report、`ReviewDisplayOutput` 和 `ReviewDisplaySummary` 已经展示 stage flow、queue triage、gate checklist、confidence map、score groups、venue-weighted repair targets、score matrix 和 revisions；展示投影还保留 submission readiness gates，前端不必直接解释完整 `ReviewOutput`。

## 借鉴 OpenClaw 的边界

[OpenClaw 官方文档](https://openclawdoc.com/docs/getting-started/what-is-openclaw/)把平台拆成 Agent Core、Channel Adapters、Skill Engine 和 Sandbox。
这个仓库不是多渠道聊天平台，所以不需要复制它的 channel marketplace。
更适合借鉴的是四个工程原则：

| OpenClaw 概念 | 本仓库对应点 | 当前处理 |
| --- | --- | --- |
| Agent Core | `runtime/` + `orchestrator/` | 统一处理状态、provider、workflow 和产物 |
| Channel Adapters | CLI / FastAPI | 入口薄，业务逻辑不写在 API 或 CLI 内 |
| Skill Engine | `agents/` + `prompts/` | 面板职责固定，输出都进 Pydantic schema |
| Sandbox | risk-first gate + local dry-run | 高风险稿件先阻断，不让下游面板奖励 venue fit |

后续如果接 Slack、Discord、投稿站后台或浏览器插件，应先做 adapter 层，不要把渠道逻辑写进 orchestrator。

## 算法优化路线

当前不是靠单个 prompt 决策，而是把问题拆成几步：

1. 本地 precheck 先判断结构、字数、风险和明显缺项。
2. provider-backed precheck 补充模型判断。
3. evidence / value / meta 面板并行或按 workflow 执行。
4. scoring 层做 rule caps 和推荐标签，风险标记优先于分数。
5. scoring 层同时看 `confidence`：高分但低置信的推进关键维度会触发 `low_confidence_advancement_gate`，避免把不稳的判断直接推到 full review。
6. benchmark 把结果和 intake-only baseline 对比，避免“看起来更复杂但没有收益”。

下一步可以优先做这些增强：

- 给 `VenueProfile` 加 `routing_stage` 和 `submission_track` 说明，用于展示页和后台筛选。
- 增加 single-call structured reviewer baseline，用真实模型比较多面板工作流的准确率、延迟和成本。
- 增加 single-call structured reviewer baseline 的成本/延迟统计，用真实模型比较多面板工作流的收益。

## 变更入口建议

- 改节点顺序：先看 `workflows/`
- 改图元数据或并行关系：先看 `WorkflowSpec` 与对应 `build_*_workflow_spec()`
- 改 Agent 调用或 fallback：先看 `orchestrator/review_pipeline.py`
- 改 recommendation 规则：先看 `scoring/payload_vs_vibes.py`
- 改工作流持久化：先看 `runtime/` 与 `storage/sqlite_store.py`

