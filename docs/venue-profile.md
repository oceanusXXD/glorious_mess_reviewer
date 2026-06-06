# Venue Profile 说明

默认 venue 是 `S.H.I.T Initial Screening Desk`。
该 profile 用于判断一篇稿件是否值得进入下一轮 review，
不是最终录用决策。

内置 preset：

- `shit-screening-default`
- `shit-hardcore-screening`
- `shit-abstract-screening`

## 核心字段

`VenueProfile` 当前包含这些核心部分：

- `preset_name`
- `venue_name`
- `tone`
- `required_sections`
- `minimum_reviewable_characters`
- `scoring_weights`
- `rejection_rules`
- `recommendation_policy`

## 评审维度

当前使用 12 个维度：

- `venue_fit`
- `core_claim_clarity`
- `structural_integrity`
- `method_or_reasoning_legibility`
- `evidence_checkability`
- `result_payload`
- `limitation_honesty`
- `zhenghuo_execution`
- `absurd_originality`
- `meme_to_argument_conversion`
- `community_discussion_value`
- `overall_merit`

## 默认规则

默认 profile 会启用这些 rejection / cap 规则：

- 缺 `title` / `abstract` / `body` 记为 hard failure
- 没有 core claim 时，`overall_merit` 封顶为 2
- 没有可核查 evidence 时，`evidence_checkability` 封顶为 2
- gimmick 明显但 payload 很弱时，`overall_merit` 封顶为 3
- 发现安全或滥用风险时打 `risk_flag`
- 推进关键维度高分但低置信时，触发 `low_confidence_advancement_gate`，转入人工复核或修订车道

## 推荐策略

`RecommendationPolicy` 当前字段如下：

- `advance_to_full_review_min_final_score`
- `advance_with_payload_reservations_min_final_score`
- `borderline_for_full_review_min_final_score`
- `payload_floor_for_advance`
- `venue_fit_floor_for_advance`

这些阈值共同决定：

- `ADVANCE_TO_FULL_REVIEW`
- `ADVANCE_WITH_PAYLOAD_RESERVATIONS`
- `BORDERLINE_FOR_FULL_REVIEW`
- `REVISION_REQUIRED_BEFORE_REVIEW`
- `REJECT_AS_EMPTY_GIMMICK`
- `REJECT_AS_INCOHERENT_SLUDGE`
- `ESCALATE_FOR_HUMAN_RISK_CHECK`

## 推荐标签的运营含义

| 标签 | 操作建议 |
| --- | --- |
| `ADVANCE_TO_FULL_REVIEW` | 进入下一轮人工或深度评审 |
| `ADVANCE_WITH_PAYLOAD_RESERVATIONS` | 可以进入下一轮，但下一轮必须重点检查 payload 密度 |
| `BORDERLINE_FOR_FULL_REVIEW` | 不要直接拒绝，交给人工判断 venue-native 价值是否足够 |
| `REVISION_REQUIRED_BEFORE_REVIEW` | 退回作者补结构、claim、method、evidence 或 limitations |
| `REJECT_AS_EMPTY_GIMMICK` | 拒绝空心梗稿；除非作者能补出实际论点，否则不进入下一轮 |
| `REJECT_AS_INCOHERENT_SLUDGE` | 拒绝无法形成可追踪论证的稿件 |
| `ESCALATE_FOR_HUMAN_RISK_CHECK` | 先做人工安全复核，不奖励 venue fit 或整活质量 |

这些标签是初筛决策，不是最终录用结论。

## 三个内置 preset

### `shit-screening-default`

- 目标：平衡型初筛
- 最小字数：继承运行时默认值，默认是 `1200`
- 主要高权重维度：
  - `overall_merit`
  - `result_payload`
  - `core_claim_clarity`
- 主要阈值：`4.2 / 3.7 / 2.8`

### `shit-hardcore-screening`

- 目标：更强调论证与证据
- 最小字数：`1500`
- 主要高权重维度：
  - `result_payload`
  - `core_claim_clarity`
  - `method_or_reasoning_legibility`
  - `evidence_checkability`
- 主要阈值：`4.2 / 3.7 / 2.9`

### `shit-abstract-screening`

- 目标：更强调创意与传播讨论度
- 最小字数：`800`
- 主要高权重维度：
  - `zhenghuo_execution`
  - `meme_to_argument_conversion`
  - `absurd_originality`
- 主要阈值：`4.0 / 3.5 / 2.8`

阈值顺序分别是：

- `advance_to_full_review_min_final_score`
- `advance_with_payload_reservations_min_final_score`
- `borderline_for_full_review_min_final_score`

## 选择建议

- 需要默认初筛口径时，使用 `shit-screening-default`
- 需要更高论证门槛时，使用 `shit-hardcore-screening`
- 需要放宽篇幅并突出创意表达时，使用 `shit-abstract-screening`

## 自定义 venue profile

你可以通过 API `POST /venue/validate` 校验自定义 `VenueProfile`。
自定义 profile 需要保证：

- 所有阈值关系合法
- scoring weights 与维度名有效
- recommendation policy 能覆盖现有 recommendation 分支

完整示例见：

- [examples/custom-venue-profile.json](examples/custom-venue-profile.json)

使用方式：

1. 从 `glorious_mess_reviewer show-default-venue` 导出一个内置 profile。
2. 修改 `venue_name`、`tone`、`minimum_reviewable_characters`、权重和阈值。
3. 通过 `POST /venue/validate` 校验。
4. 把校验后的对象放入 `ManuscriptInput.venue_profile`。

最小嵌入示例：

```json
{
  "manuscript_id": "custom-profile-001",
  "title": "Example",
  "abstract": "Example abstract.",
  "body": "Introduction\n...\nConclusion\n...\nLimitations\n...",
  "venue_profile": {
    "preset_name": null,
    "venue_name": "Custom S.H.I.T Desk",
    "tone": "Custom screening tone.",
    "required_sections": ["title", "abstract", "body", "conclusion", "limitations"],
    "minimum_reviewable_characters": 900,
    "scoring_weights": {
      "venue_fit": 1.0,
      "core_claim_clarity": 1.2,
      "structural_integrity": 1.0,
      "method_or_reasoning_legibility": 1.0,
      "evidence_checkability": 0.9,
      "result_payload": 1.3,
      "limitation_honesty": 0.8,
      "zhenghuo_execution": 1.1,
      "absurd_originality": 1.0,
      "meme_to_argument_conversion": 1.2,
      "community_discussion_value": 1.0,
      "overall_merit": 1.3
    },
    "rejection_rules": [
      "missing_title_or_abstract_or_body_is_hard_failure",
      "no_core_claim_caps_overall_at_two",
      "no_checkable_evidence_caps_evidence_at_two",
      "gimmick_without_payload_caps_overall_at_three",
      "unsafe_or_abusive_content_sets_risk_flag",
      "low_confidence_advancement_gate"
    ],
    "recommendation_policy": {
      "advance_to_full_review_min_final_score": 4.1,
      "advance_with_payload_reservations_min_final_score": 3.6,
      "borderline_for_full_review_min_final_score": 2.8,
      "payload_floor_for_advance": 3,
      "venue_fit_floor_for_advance": 3
    }
  }
}
```

## venue-fit 审计规则

`VenueFitAuditOutput.action` 是轻量审计结论，不等同于完整 `ReviewOutput.final_recommendation`。

当前 `STRONG_FIT` 要求：

- `venue_fit_score >= 4`
- `meme_to_argument_score >= 4`
- `zhenghuo_execution_score >= 4`
- `community_discussion_value >= 3`

如果存在 `risk_flags`，venue-fit 审计会返回 `BLOCKED_BY_RISK`，
不会因为“很像 S.H.I.T”而奖励风险内容。

## 当前 rubric 边界

`academic_camouflage` 与 `emotional_social_payload` 是 prompt guidance 中的重要口径，
目前通过 `structural_integrity`、`venue_fit`、`result_payload`、
`community_discussion_value` 等维度间接表达。若未来要把它们做成一等分数维度，
需要同步更新 schema、prompt 模板、preset 权重、scoring、fixtures 和 golden 回归。

## 相关文件

- Schema：
  [../glorious_mess_reviewer/schemas/contracts.py](../glorious_mess_reviewer/schemas/contracts.py)
- CLI 查询入口：
  [../glorious_mess_reviewer/cli/main.py](../glorious_mess_reviewer/cli/main.py)
- API 查询入口：
  [../glorious_mess_reviewer/api/app.py](../glorious_mess_reviewer/api/app.py)
- Scoring 逻辑：
  [../glorious_mess_reviewer/scoring/payload_vs_vibes.py](../glorious_mess_reviewer/scoring/payload_vs_vibes.py)
