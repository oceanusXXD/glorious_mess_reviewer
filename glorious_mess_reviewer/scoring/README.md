# 评分与建议

`payload_vs_vibes.py` 负责把 panel 输出转成最终分数和初筛建议。

## 主要职责

- 合并 panel 输出
- 计算 weighted final score
- 计算 weighted confidence
- 应用 post-review rule caps
- 根据 venue policy 决定最终 recommendation

## 当前流程

1. 用 `merge_sludge_panel_reviews()` 汇总 panel 结果
2. 用 `apply_post_review_rules()` 处理缺 section、缺 claim、
   缺 evidence、gimmick、risk flag、低置信推进门等规则
3. 用 `compute_weighted_final_score()` 计算最终分数
4. 用 `compute_weighted_confidence()` 计算报告里的加权置信度
5. 用 `compute_screening_recommendation()` 输出 recommendation 和理由

`low_confidence_advancement_gate` 负责处理“高分但低置信”的情况：
如果 payload、evidence、core claim、meme-to-argument 或 overall merit 这些推进关键维度给了高分，
但对应 confidence 低于门槛，系统不会直接给 full-review advance，而是进入人工复核或修订车道。

## 当前 recommendation 分支

- `ADVANCE_TO_FULL_REVIEW`
- `ADVANCE_WITH_PAYLOAD_RESERVATIONS`
- `BORDERLINE_FOR_FULL_REVIEW`
- `REVISION_REQUIRED_BEFORE_REVIEW`
- `REJECT_AS_EMPTY_GIMMICK`
- `REJECT_AS_INCOHERENT_SLUDGE`

## 维护约定

- 改阈值、rule cap 或 recommendation 分支时，
  同步更新 `tests/test_scoring.py`。
- 改会影响完整输出的字段时，同步更新
  `tests/test_golden_samples.py` 和相关文档。
