# Prompt 设计

这个仓库的 Prompt 设计围绕四个内置 Agent 展开。
模板位于 `glorious_mess_reviewer/prompts/templates/`，统一由 `loader.py` 渲染。

## 统一规则

所有 Agent Prompt 都遵守这些硬约束：

- 只输出 JSON
- 不能编造稿件中不存在的事实
- 缺失信息必须明确标成 `unknown` 或 `missing`
- 证据优先引用 manuscript 原文
- `supporting_evidence` / `evidence_snippets` 使用结构化 `EvidenceItem`
- 奇怪的稿件可以保留，但空洞 gimmick 不会直接得到高分
- 低置信度判断必须解释原因
- 明确包含 SHIT-native venue guidance 与 few-shot 校准示例

## Agent 分工

| 模板 | Agent | 关注点 |
| --- | --- | --- |
| `precheck_agent.j2` | `HanCeGateAgent` | intake、结构缺失、风险项、最小可评审性 |
| `evidence_agent.j2` | `EvidenceSludgeEngineAgent` | claim、reasoning、evidence、payload |
| `value_agent.j2` | `AbsurdityButMakeItRigorousAgent` | venue 适配度、整活质量、原创性、社区讨论价值 |
| `meta_agent.j2` | `FinalSedimentCouncilAgent` | 汇总上游结果并给出最终 panel 结论 |

## 额外上下文

每次渲染 Prompt 时，除了 manuscript 和 venue profile，还会补充：

- `venue_guidance_text`：法律边界、SHIT 风格口径、危险内容约束
- `venue_examples_text`：按 preset 变化的校准示例
- `minimum_reviewable_characters`：预检查阶段使用
- `precheck_json` / `evidence_json` / `value_json`：meta Prompt 使用

## 维护约定

- 改模板时，同步看 `tests/test_prompts.py` 和 `tests/test_prompt_assets.py`。
- 改 JSON 字段时，同步看 `glorious_mess_reviewer/schemas/README.md`。
- recommendation 逻辑放在 `scoring/`，不要塞回 Prompt 模板里。
