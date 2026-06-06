# 运行时

这个目录提供工作流运行时的控制平面。

## 文件说明

- `wiring.py`：统一构建 provider / store / orchestrator / runtime / 评审服务
- `registry.py`：`WorkflowSpec` 与 `WorkflowRegistry`，包括节点、条件边、并行组和产物 key
- `executor.py`：`WorkflowRuntime`，负责执行工作流并持久化会话 / 步骤 / 产物
- `session.py`：`WorkflowRunContext` 与 `WorkflowExecutionResult`
- `service.py`：面向 API / CLI 的 `ReviewRuntimeService`，包含 workflow session 查询封装

## 职责边界

- runtime 负责工作流注册、执行和会话记录
- runtime 在工作流失败时会把 session 标记为 `failed`，并写入 `workflow_failed` 事件
- workflow 负责节点顺序、条件边、并行组、产物 key 和标签
- orchestrator 负责业务判断、precheck merge、projection 和 agent-level fallback

## Workflow metadata

`list_workflows()` 返回的不只是节点列表，还包含：

- `edges`：有向依赖边，可带 `condition`
- `parallel_groups`：可并行执行的节点组，例如完整 review 中的 evidence / value panel
- `artifact_keys`：该工作流可能写入的 artifact key

这些字段用于外部后台、调试工具和文档生成，不作为 runtime 调度器的唯一来源。

## 当前已注册工作流

- `screening.review.v1`
- `screening.risk_audit.v1`
- `screening.venue_fit_audit.v1`

## 查询能力

- `list_workflows()`：列出已注册 workflow metadata
- `get_workflow_session(session_id)`：读取一条完整 session、steps 和 artifacts
- `list_workflow_sessions(...)`：按 `workflow_id`、`manuscript_id`、`status` 和 `limit`
  查询 session 摘要，供 API `/workflow-sessions` 和 CLI `list-workflow-sessions` 使用

## 维护约定

- 新增工作流时，先在 `workflows/` 写 spec，再在 `wiring.py` 注册。
- 新增可并行节点时，把 `parallel_groups` 和条件边一起写进 `WorkflowSpec`。
- 改步骤 / 产物结构时，同步确认 `tests/test_runtime.py`、
  `tests/test_workflow_runtime.py`、`tests/test_storage.py`。
- recommendation 逻辑不要放进 runtime，保持在 `scoring/`。
