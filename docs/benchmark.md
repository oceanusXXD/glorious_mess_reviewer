# Benchmark 指南

这个仓库现在有两层 benchmark：

- `dry-run`：不调用模型，只验证确定性 intake gate、结构检查、风险标记和报告格式。
- `review`：调用配置好的 provider，验证完整多面板初筛输出，并和一个简单 intake-only baseline 对比。

默认 suite 在 [docs/examples/benchmark-suite.json](examples/benchmark-suite.json)。它覆盖 7 类样本：强 fit、空心梗、认真但错 venue、薄但可评审、缺摘要、风险门、以及安全提醒不应误报。

## 本地离线运行

```bash
glorious_mess_reviewer benchmark \
  --mode dry-run \
  --output benchmark-report.json \
  --markdown-output benchmark-report.md
```

离线模式适合 CI。它不需要 API key，硬指标是：

- `accepted_match_rate`：是否和 suite 里期望的 `expected_accepted_for_full_review` 一致。
- `risk_flags_match_rate`：本地风险标记是否精确匹配期望，防止漏报和误报。
- `ok_cases`：case 是否都正常执行。

## 真实模型运行

先配置 provider，再运行：

```bash
set GLORIOUS_MESS_PROVIDER_BACKEND=openai
set GLORIOUS_MESS_OPENAI_API_KEY=your_key_here
set GLORIOUS_MESS_DEFAULT_MODEL=your_model_here

glorious_mess_reviewer benchmark \
  --mode review \
  --limit 3 \
  --output benchmark-review.json \
  --markdown-output benchmark-review.md
```

OpenAI-compatible chat endpoint 示例：

```bash
set GLORIOUS_MESS_PROVIDER_BACKEND=openai
set GLORIOUS_MESS_OPENAI_API_STYLE=chat_completions
set GLORIOUS_MESS_OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
set GLORIOUS_MESS_OPENAI_API_KEY=your_key_here
set GLORIOUS_MESS_DEFAULT_MODEL=qwen-plus

glorious_mess_reviewer benchmark --mode review --limit 1
```

[DashScope 的 OpenAI-compatible Chat 文档](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)列出了 `/compatible-mode/v1` base URL 和 `/chat/completions` endpoint；本项目只需要配置 base URL，SDK 会拼接具体路径。

## Baseline 解释

`baseline_recommendation` 是一个很弱的 intake-only baseline：只看明显缺项、正文长度和少量本地风险词。它故意不理解 venue fit、payload、meme-to-argument，也不做面板交叉检查。

完整 `review` 模式会报告：

- `recommendation_accuracy`
- `baseline_recommendation_accuracy`
- `recommendation_accuracy_lift`
- `risk_gate_match_rate`
- `baseline_delta_counts`
- `workflow_win_cases`
- `baseline_win_cases`
- `both_missed_cases`
- `mean_workflow_step_count`
- `mean_skipped_step_count`

这些指标的用途不是证明模型“永远正确”，而是让维护者看到多面板工作流相对简单 gate 是否有实际收益。
`baseline_delta_counts` 会把 review case 分成 `both_correct`、`workflow_win`、`baseline_win`、
`both_missed` 和 `unmeasured`，便于定位算法收益和回归点。

## 验证快照

2026-06-07 本地验证结果：

| 模式 | Provider | Case | 结果 |
| --- | --- | --- | --- |
| `dry-run` | none | 7/7 | `accepted_match_rate=1.0`，`risk_flags_match_rate=1.0` |
| `review` | OpenAI-compatible Responses endpoint | 1/1 | `recommendation_accuracy=1.0`，`baseline_recommendation_accuracy=0.0` |

真实 provider smoke test 使用私有环境完成，具体 endpoint 和 key 已脱敏。样例 case 的完整工作流命中预期推荐；同一 case 的 intake-only baseline 未命中，说明多面板评审在这个样例上提供了有效增益。

## Suite 格式

```json
{
  "suite_name": "S.H.I.T screening fixture benchmark",
  "minimum_reviewable_characters": 200,
  "cases": [
    {
      "case_id": "absurd_rigorous_should_advance",
      "input_path": "../../tests/fixtures/absurd_but_rigorous.json",
      "description": "A venue-native absurd manuscript with a concrete claim and payload.",
      "expected_recommendation": "ADVANCE_TO_FULL_REVIEW",
      "expected_accepted_for_full_review": true,
      "expected_risk_flags": [],
      "expected_risk_gate": false
    }
  ]
}
```

`overrides` 可以覆盖 fixture 字段，用于构造缺摘要、风险注入、声明缺失等边界样本。

## 维护要求

- 改风险检测时，至少跑 `benchmark --mode dry-run`。
- 改 scoring 或 prompt 时，跑 full pytest，并用真实 provider 跑 `benchmark --mode review --limit 3`。
- 新增公开 claim 时，把对应 case 写进 suite，不要只在 README 里描述。
