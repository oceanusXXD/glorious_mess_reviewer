# 存储层

这个目录负责 SQLite 持久化。

## 当前表

- `review_runs`
- `event_logs`
- `agent_runs`
- `retry_records`
- `workflow_sessions`
- `workflow_steps`
- `workflow_artifacts`
- `schema_metadata`

`workflow_sessions` 单独保存 `manuscript_id`，不要只依赖 `request_payload_json` 里的嵌套字段。
当前 schema version 写入 `schema_metadata`，用于本地数据库检查和后续迁移。

## 当前查询入口

- `get_review()`
- `list_reviews()`
- `get_workflow_session()`
- `list_workflow_sessions()`
- `healthcheck()`

`list_workflow_sessions()` 用于操作员浏览风险审计、venue-fit 审计和完整评审的历史会话摘要。
它支持按 `workflow_id`、`manuscript_id`、`status` 和 `limit` 查询；`limit` 会限制在 `1..100`。
失败工作流会把 `workflow_sessions.status` 标记为 `failed`，并在 `event_logs`
中写入 `workflow_failed` 事件。

## 查询索引

初始化数据库时会创建这些查询索引：

- `idx_review_runs_manuscript_created`
- `idx_event_logs_run_type`
- `idx_workflow_sessions_browse`

## 维护约定

- 改表结构时，同步更新 storage tests 和文档。
- 改持久化 payload 时，确认 review 记录与工作流会话记录都保持一致。
- 如果新增列，需要保留旧 SQLite 文件的轻量迁移路径。
