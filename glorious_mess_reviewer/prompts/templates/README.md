# Prompt 模板

这个目录保存四个 Jinja2 模板。

## 模板映射

### `precheck_agent.j2`

- 对应 Agent：`HanCeGateAgent`
- 主要输出模型：`PrecheckOutput`
- 关键测试：
  `tests/test_prompts.py::test_precheck_prompt_renders_manuscript_and_venue`

### `evidence_agent.j2`

- 对应 Agent：`EvidenceSludgeEngineAgent`
- 主要输出模型：`EvidenceAgentOutput`
- 关键测试：
  `tests/test_prompts.py::test_evidence_prompt_mentions_argument_and_evidence_distinction`

### `value_agent.j2`

- 对应 Agent：`AbsurdityButMakeItRigorousAgent`
- 主要输出模型：`ValueAgentOutput`
- 关键测试：
  `tests/test_prompts.py::test_value_prompt_contains_funny_but_empty_guardrail`

### `meta_agent.j2`

- 对应 Agent：`FinalSedimentCouncilAgent`
- 主要输出模型：`FinalMetaReviewOutput`
- 关键测试：
  `tests/test_prompts.py::test_meta_prompt_includes_upstream_review_context`

## 维护约定

- 模板字段变化要同步数据契约、Agent 调用参数和测试。
- `supporting_evidence` / `evidence_snippets` 使用结构化对象，
  不回退到裸字符串数组。
- Prompt 版本由 loader 注入；改模板导致输出契约变化时，
  记得同步版本与测试。
