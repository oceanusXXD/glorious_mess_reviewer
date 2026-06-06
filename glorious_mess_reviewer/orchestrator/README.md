# 编排层

`review_pipeline.py` 保存核心业务编排逻辑。
它负责确定性预检查、Agent 调用、fallback、projection
和审计写入辅助逻辑。

## 正式评审主链路

1. 记录 `review_requested` event
2. 解析或补全 venue profile
3. 执行确定性预检查
4. 调用 `HanCeGateAgent`
5. 并行调用 evidence / value Agent
6. 调用 meta Agent 或走 deterministic merge fallback
7. 应用 scoring 与 recommendation 逻辑
8. 构造 `ReviewOutput` 并协助持久化

## fallback 规则

- precheck Agent 失败：退回确定性预检查
- evidence / value Agent 部分失败：使用 surviving signals 继续 panel 汇总
- meta Agent 失败：退回 deterministic merge
- provider 缺失：正式评审直接抛 `ProviderError`

## `raw_agent_outputs` 语义

| status | 含义 | payload 来源 |
| --- | --- | --- |
| `success` | Agent 正常返回 | 真实 Agent 输出 |
| `failed` | Agent 调用失败，没有可用 payload | 错误信息会进入 `agent_failures` / retry / event |
| `fallback` | 上游失败后使用本地替代结果继续流程 | 确定性预检查或 merge 结果 |

## 维护约定

- 改 fallback 行为时，同步确认 `agent_failures`、`raw_agent_outputs`
  和 SQLite 写入。
- 改 projection 字段时，同步确认 API 返回、golden 和 storage tests。
