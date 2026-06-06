# 数据契约

这个目录保存 API、CLI、Agent IO
和持久化使用的核心 Pydantic 数据契约。

## 关键模型

- `ManuscriptInput`
- `VenueProfile`
- `RecommendationPolicy`
- `PrecheckOutput`
- `EvidenceItem`
- `EvidenceAgentOutput`
- `ValueAgentOutput`
- `FinalMetaReviewOutput`
- `ReviewOutput`
- `ReviewDisplayOutput`
- `ReviewDisplaySummary`
- `ReviewDisplayQueueOverview`
- `ReviewDisplayRepairHotspot`
- `ReviewDisplayRepairTarget`
- `ReviewDisplayTriage`
- `RiskAuditOutput`
- `VenueFitAuditOutput`
- `RawAgentOutputEnvelope`
- `WorkflowEdge`
- `WorkflowInfo`
- `WorkflowSessionRecord`
- `WorkflowSessionSummary`
- `HealthResponse`

## 当前约束

- 所有数据契约统一继承 `ContractModel`
- `extra="forbid"`，拒绝未声明字段
- `RecommendationPolicy` 是类型化模型，不再使用散乱 dict
- `supporting_evidence` / `evidence_snippets` 使用 `EvidenceItem`
- `raw_agent_outputs` 使用稳定 envelope，并带 `artifact_type`
- `WorkflowInfo` 暴露 `edges`、`parallel_groups` 和 `artifact_keys`，用于描述工作流图结构
- `ReviewDisplayOutput` 是从持久化 review 派生的展示投影，不替代 `ReviewOutput`
- `ReviewDisplaySummary` 是后台队列列表使用的单行展示投影，不包含完整 score matrix
- `ReviewDisplayQueueOverview` 汇总 lane counts、gate pressure、平均分/置信度和 repair hotspots，供后台首页直接使用
- `ReviewDisplayOutput.score_groups` 给前端提供结构证据、整活转论证、社区价值三组摘要
- 每个 score group 包含最弱维度和推荐动作，便于编辑台直接排序处理
- `ReviewDisplayOutput.repair_targets` 按 venue 权重、分数缺口和置信度缺口给出最多 5 个优先修复维度
- `ReviewDisplayOutput.triage` 给编辑台提供 `queue_priority`、处理车道和单个 next action

## 维护约定

- 改任何对外数据契约时，同步更新 API、CLI、docs 和 tests。
- 新增 recommendation 字段前，先确认是否应该进入 `RecommendationPolicy`。
