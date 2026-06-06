# 工作流定义

这个目录保存 runtime 使用的工作流规范。

## 当前工作流

| 文件 | workflow ID | 作用 |
| --- | --- | --- |
| `screening_review_v1.py` | `screening.review.v1` | 完整初筛工作流 |
| `screening_risk_audit_v1.py` | `screening.risk_audit.v1` | 风险导向的 intake 审计 |
| `screening_venue_fit_audit_v1.py` | `screening.venue_fit_audit.v1` | venue 适配导向的审计 |

## 节点图

### `screening.review.v1`

1. `resolve_venue`
2. `precheck.local`
3. `precheck.llm`
4. `panel.evidence` 与 `panel.value` 并行执行
6. `panel.meta`
7. `projection.review`

如果 `precheck.llm` 合并后的有效 precheck 已经发现风险标记，工作流会走
`risk_gate`，跳过 `panel.evidence`、`panel.value`、`panel.meta`，直接生成
`ESCALATE_FOR_HUMAN_RISK_CHECK` 方向的结构化结果。

### `screening.risk_audit.v1`

1. `resolve_venue`
2. `precheck.local`
3. `precheck.llm`
4. `projection.risk_audit`

### `screening.venue_fit_audit.v1`

1. `resolve_venue`
2. `precheck.local`
3. `precheck.llm`
4. `panel.value`
5. `projection.venue_fit_audit`

## 维护约定

- 改节点顺序、条件边、并行组或 artifact key 时，优先改对应工作流规范里的 `WorkflowSpec`。
- 改 artifact key 或步骤结构时，同步更新 runtime / storage tests。
- recommendation 逻辑留在 `scoring/`，不要塞进工作流步骤。
