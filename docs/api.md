# API 文档

本文档说明 `glorious_mess_reviewer.api.app:create_app` 暴露的 HTTP 接口。
所有路由都围绕 `ReviewRuntimeService` 构建，输入模型统一为
`ManuscriptInput` 或 `VenueProfile`，输出模型定义在
`glorious_mess_reviewer.schemas`。

## 基本约定

- `GET /health` 与 `POST /review/dry-run` 不依赖 provider。
- `POST /review`、`POST /review/risk-audit`、
  `POST /review/venue-fit-audit` 需要可用 provider。
- 正式评审在 provider 缺失时会直接返回 `502 provider_failure`。
- `manuscript_id` 会在 schema 校验前去掉首尾空白；去掉后为空会返回 `422 invalid_request`。
- 列表接口的 `limit` 范围是 `1..100`，CLI 查询命令使用同样边界。
- FastAPI 自带 `/docs` 与 `/redoc` 页面，可直接查看 OpenAPI 文档。

## 路由总览

### 核心执行接口

| Method | Path | 请求体 | 返回体 | 说明 |
| --- | --- | --- | --- | --- |
| `GET` | `/health` | 无 | `HealthResponse` | 查看服务、数据库和 provider 状态 |
| `POST` | `/review` | `ManuscriptInput` | `ReviewOutput` | 执行完整初筛工作流 |
| `POST` | `/review/risk-audit` | `ManuscriptInput` | `RiskAuditOutput` | 只做风险审计 |
| `POST` | `/review/venue-fit-audit` | `ManuscriptInput` | `VenueFitAuditOutput` | 只做 venue 适配审计 |
| `POST` | `/review/dry-run` | `ManuscriptInput` | `DryRunOutput` | 只做确定性预检查 |

### 查询与辅助接口

| Method | Path | 返回体 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/review/{run_id}` | `PersistedReviewRecord` | 查询一条持久化 review 记录 |
| `GET` | `/review/{run_id}/display` | `ReviewDisplayOutput` | 查询一条面向展示层的轻量 review 投影 |
| `GET` | `/reviews` | `list[ReviewRunSummary]` | 查询 review 摘要列表，支持 `manuscript_id` 与 `limit` |
| `GET` | `/reviews/display` | `list[ReviewDisplaySummary]` | 查询面向后台队列页的轻量展示摘要 |
| `GET` | `/reviews/display/overview` | `ReviewDisplayQueueOverview` | 汇总队列车道、gate pressure、平均分/置信度和 repair hotspots |
| `GET` | `/workflows` | `list[WorkflowInfo]` | 查询已注册工作流元数据 |
| `GET` | `/workflow-sessions` | `list[WorkflowSessionSummary]` | 查询已持久化工作流会话摘要，支持 `workflow_id`、`manuscript_id`、`status` 与 `limit` |
| `GET` | `/workflow/{session_id}` | `WorkflowSessionRecord` | 查询一条工作流会话 |
| `GET` | `/venue/default` | `VenueProfile` | 获取默认或指定 preset 的 venue profile |
| `POST` | `/venue/validate` | `VenueValidationResponse` | 校验自定义 venue profile |

## 关键返回模型

### `HealthResponse`

主要字段：

- `status`
- `service`
- `provider_backend`
- `default_model`
- `database_ok`
- `provider_configured`

### `ReviewOutput`

主要字段：

- `workflow_session_id`
- `paper_summary`
- `extracted_core_claim`
- `resolved_venue_profile`
- `scores_by_dimension`
- `hard_failures`
- `major_strengths`
- `major_weaknesses`
- `required_revisions`
- `optional_revisions`
- `risk_flags`
- `rule_hits`
- `agent_failures`
- `final_score`
- `final_recommendation`
- `final_rationale`
- `human_readable_review`
- `community_facing_blurb`
- `raw_agent_outputs`
- `created_at`

### `ReviewDisplayOutput`

`GET /review/{run_id}/display` 返回从持久化 `ReviewOutput` 派生的展示 payload，
用于后台列表页、详情卡片或轻量前端组件。它不包含 `raw_agent_outputs`，
也不要求前端自己解析 12 维完整 schema。

`gates` 当前包含两类信息：

- review health：`risk_flags`、`hard_failures`、`agent_failures`、`rule_trace`
- submission readiness：`format_compliance`、`citation_traceability`、`ai_disclosure_integrity`、`safety_notice_presence`

主要字段：

- `run_id`
- `manuscript_id`
- `recommendation`
- `final_score`
- `weighted_confidence`
- `calibration_status`
- `suggested_stage`
- `triage`
- `gates`
- `low_confidence_dimensions`
- `score_matrix`
- `score_groups`
- `repair_targets`
- `required_revisions`
- `strengths`
- `weaknesses`

`triage` 是编辑台排序摘要，当前使用 `queue_priority` 数字和 `lane`
说明下一步应走哪条处理车道。高优先级依次覆盖风险复核、硬失败、agent 降级、
低信心高分、弱 score group、投稿 readiness、作者修订和可推进状态。

`repair_targets` 是最多 5 个 venue-weighted 修复目标。排序分由分数缺口、
置信度缺口和当前 `VenueProfile.scoring_weights` 派生，用于作者页或编辑台展示
“先修哪几项”。

### `ReviewDisplaySummary`

`GET /reviews/display` 返回后台队列页可以直接排序的轻量列表。它支持：

- `manuscript_id`
- `limit`
- `lane`
- `sort=created_at|queue_priority|repair_priority`

它不包含
`score_matrix`、完整修订列表或 raw agent payload，只保留单行卡片常用字段：

- `run_id`
- `manuscript_id`
- `recommendation`
- `final_score`
- `weighted_confidence`
- `calibration_status`
- `suggested_stage`
- `triage`
- `top_repair_target`
- `needs_review_gates`

这个接口适合先渲染队列列表；进入详情页时再调用 `/review/{run_id}/display`。

### `ReviewDisplayQueueOverview`

`GET /reviews/display/overview` 返回后台首页可直接使用的队列聚合摘要。它支持：

- `manuscript_id`
- `limit`

主要字段：

- `total_reviews`
- `lane_counts`
- `gate_counts`
- `needs_human_review`
- `ready_for_next_stage`
- `average_final_score`
- `average_weighted_confidence`
- `top_repair_hotspots`

`top_repair_hotspots` excludes `human_risk_review`, `blocked_before_review`, and `degraded_review` rows so safety/blocking pressure does not pollute author-repair priorities.

### `RawAgentOutputEnvelope`

`raw_agent_outputs` 使用稳定 envelope：

```json
{
  "HanCeGateAgent": {
    "status": "success",
    "artifact_type": "precheck_output",
    "payload": {}
  }
}
```

### `RiskAuditOutput` / `VenueFitAuditOutput` / `DryRunOutput`

这三类输出都保留类型化数据契约，不走自由 JSON：

- `RiskAuditOutput`：强调 `hard_failures`、`missing_sections`、
  `risk_flags` 和有效预检查结果
- `VenueFitAuditOutput`：强调 venue 适配度、长处、短板和最终 fit 结论
- `DryRunOutput`：强调 `accepted_for_full_review`
  与确定性预检查结果

### `WorkflowSessionSummary`

`GET /workflow-sessions` 返回轻量摘要，方便操作员找到风险审计、
venue-fit 审计和完整评审的历史会话：

- `session_id`
- `workflow_id`
- `status`
- `manuscript_id`
- `created_at`
- `updated_at`
- `final_output_type`

常用查询：

```bash
curl "http://127.0.0.1:8000/workflow-sessions?workflow_id=screening.risk_audit.v1&limit=10"
curl "http://127.0.0.1:8000/workflow-sessions?manuscript_id=absurd-rigorous-001"
curl "http://127.0.0.1:8000/workflow-sessions?status=failed"
```

### 展示投影

```bash
curl "http://127.0.0.1:8000/review/<run_id>/display"
```

代表性返回字段：

```json
{
  "recommendation": "ADVANCE_TO_FULL_REVIEW",
  "suggested_stage": "real_shit_candidate",
  "weighted_confidence": 0.86,
  "calibration_status": "high_confidence",
  "triage": {
    "queue_priority": 10,
    "lane": "ready_for_next_stage",
    "primary_gate": null,
    "primary_revision": "Clarify the observational protocol.",
    "primary_score_group": null,
    "action": "Advance to full review; carry the first revision into the next-stage brief."
  },
  "score_groups": [
    {
      "group_id": "structure_and_evidence",
      "mean_score": 4.67,
      "status": "strong",
      "weakest_dimension": "method_or_reasoning_legibility",
      "recommended_action": "Preserve the current structure and evidence trail."
    }
  ],
  "repair_targets": [
    {
      "dimension": "method_or_reasoning_legibility",
      "score": 4,
      "confidence": 0.86,
      "venue_weight": 1.1,
      "priority_score": 1.1,
      "issue": "polish",
      "reason": "Merged panel judgment.",
      "action": "Polish method_or_reasoning_legibility; it is close but still below the top band."
    }
  ],
  "gates": [
    {"name": "risk_flags", "status": "pass", "detail": "none"},
    {"name": "format_compliance", "status": "pass", "detail": "title, abstract, body, and venue-required sections present"}
  ]
}
```

### `WorkflowInfo`

`GET /workflows` 返回工作流图元数据，便于外部后台展示执行计划：

- `node_ids`：稳定节点 ID
- `edges`：有向依赖边，可带 `condition`
- `parallel_groups`：可并行执行的节点组
- `artifact_keys`：该工作流可能写入的 artifact key

完整初筛中，`panel.evidence` 与 `panel.value` 属于同一并行组。
如果 precheck 已经发现风险标记，工作流会沿
`precheck_blocked_or_risk_flagged` 条件边直接进入 `projection.review`。

## 请求示例

### 生成 starter payload

CLI 可以生成一份可直接用于 API 的 `ManuscriptInput`：

```bash
glorious_mess_reviewer new-manuscript --output sample-manuscript.json
```

### dry-run

```bash
curl -X POST http://127.0.0.1:8000/review/dry-run ^
  -H "Content-Type: application/json" ^
  --data @sample-manuscript.json
```

代表性返回字段：

```json
{
  "manuscript_id": "sample-microwave-diplomacy-001",
  "accepted_for_full_review": true,
  "precheck": {
    "decision": "pass",
    "minimum_reviewable": true,
    "hard_failures": [],
    "missing_sections": [],
    "risk_flags": []
  }
}
```

### 完整初筛

```bash
curl -X POST http://127.0.0.1:8000/review ^
  -H "Content-Type: application/json" ^
  --data @sample-manuscript.json
```

返回重点：

- `workflow_session_id`
- `scores_by_dimension`
- `final_score`
- `final_recommendation`
- `human_readable_review`
- `raw_agent_outputs`

### 风险审计与 venue fit 审计

```bash
curl -X POST http://127.0.0.1:8000/review/risk-audit ^
  -H "Content-Type: application/json" ^
  --data @sample-manuscript.json

curl -X POST http://127.0.0.1:8000/review/venue-fit-audit ^
  -H "Content-Type: application/json" ^
  --data @sample-manuscript.json
```

`risk-audit` 的 `action` 可能是：

- `CLEAR`
- `FLAG_FOR_HUMAN_REVIEW`
- `BLOCK_BEFORE_REVIEW`

`venue-fit-audit` 的 `action` 可能是：

- `STRONG_FIT`
- `BORDERLINE_FIT`
- `MISALIGNED`
- `BLOCKED_BY_RISK`
- `INSUFFICIENT_FOR_FIT_JUDGMENT`

## 错误语义

| 状态码 | `error_code` | 说明 |
| --- | --- | --- |
| `404` | `review_not_found` | `run_id` 未命中持久化记录 |
| `404` | `workflow_not_found` | `session_id` 未命中工作流会话 |
| `422` | `invalid_request` | 请求体不满足 schema |
| `502` | `provider_failure` | provider 缺失、调用失败或配置不完整 |
| `500` | `internal_error` | 未预期异常 |

## 相关文件

- 应用入口：
  [../glorious_mess_reviewer/api/app.py](../glorious_mess_reviewer/api/app.py)
- 依赖注入：
  [../glorious_mess_reviewer/api/dependencies.py](../glorious_mess_reviewer/api/dependencies.py)
- 错误封装：
  [../glorious_mess_reviewer/api/errors.py](../glorious_mess_reviewer/api/errors.py)
- 数据契约说明：
  [../glorious_mess_reviewer/schemas/README.md](../glorious_mess_reviewer/schemas/README.md)
