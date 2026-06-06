# S.H.*.T 站点对齐分析

本项目不是 S.H.*.T 官方项目，也不复制其品牌资产。这里记录的是产品形态上的参考：如何把一个荒诞学术稿件的初筛结果展示得更像社区鉴稿，而不是普通 LLM 审稿摘要。

参考页面：

- [S.H.*.T Space](https://shitjournal.org/)
- [Acceptance Criteria / 录用标准](https://shitjournal.org/criteria)
- [Submission Restrictions / 投稿限制](https://shitjournal.org/subres)
- [Fermentation / 发酵区](https://shitjournal.org/articles)
- [Real SH*T / 构石](https://shitjournal.org/realshit)
- [Petri Dish / 培养皿](https://shitjournal.org/questions)
- [鉴稿流转规则与身份标签体系](https://shitjournal.org/news/40bafa2e-b8ae-463f-9f7d-daf2b1c71545)

## 产品判断

S.H.*.T / 构石不是“笑话生成器”。它更像一个社区出版流程：课题池提供想法，发酵区承接鉴稿和讨论，构石档案沉淀见刊内容。稿件可以怪，但仍要交代问题、方法、结果、局限、引用和安全边界。

因此本仓库应该靠近三个能力：

- 投稿 intake：先判断可不可评、缺什么、是否碰到风险红线。
- 鉴稿路由：把风险、venue fit、payload 和空心梗分开处理。
- 展示报告：给编辑、作者和平台后台一份能复查的结论，而不是只给一段模型评论。

## 已落地的对齐点

- `review --dry-run` 对应投稿前预检。
- `risk-audit` 对应风险优先队列。
- `venue-fit-audit` 对应“怪得有没有内容”的分诊。
- `ReviewOutput` 保留 rule trace、score 和 agent artifacts，便于复盘。
- `benchmark` 用固定样本验证好稿、空心梗、错 venue、风险门和误报边界。
- `new-manuscript` 模板在 `metadata` 中加入 `submission_track`、`routing_stage`、`ai_use_statement` 和 `safety_notice`。
- `review --report-output` 会生成 Markdown intake report，包含 stage flow、queue triage、gate checklist、confidence map、score groups、repair targets、score matrix、修订项和优缺点。
- `GET /reviews/display` 和 `list-review-displays` 会返回后台队列页可直接排序的展示摘要，并支持按 `queue_priority`、`repair_priority` 排序与 `lane` 筛选。
- `GET /reviews/display/overview` 和 `review-display-overview` 会汇总 lane counts、gate pressure、平均分/置信度和 repair hotspots，方便后台首页直接渲染队列压力。
- `GET /review/{run_id}/display` 和 `show-review-display` 会把完整 `ReviewOutput` 转成展示层可直接使用的轻量投影。
- display projection 已经派生 `format_compliance`、`citation_traceability`、`ai_disclosure_integrity` 和 `safety_notice_presence` 四个投稿 readiness gate。
- display projection 已经把 12 维评分分成 `structure_and_evidence`、`zhenghuo_conversion` 和 `community_signal` 三个 score group。
- display projection 已经派生 `repair_targets`，按 venue 权重、分数缺口和置信度缺口排序，给作者页和编辑台提供“先修哪几项”。
- display projection 已经派生 `triage`，把风险、硬失败、agent 失败、低信心高分、弱 score group、readiness gate 和 revision 排成一个编辑台 next action。
- scoring 层启用 `low_confidence_advancement_gate`，防止“高分但低置信”的稿件直接进入 full-review advance。

## 推荐展示页结构

页面名可以叫 `Venue-Fit Intake Report`。

首屏：

- 稿件标题、生成时间、venue preset、最终处置标签。
- 三段流转：`Petri Dish -> Fermentation -> Real S.H.*.T`，高亮当前建议阶段。
- gate checklist：结构、摘要、正文长度、AI 使用声明、引用、安全说明、风险标记。
- confidence map：展示加权置信度、低置信推进维度和是否需要人工复核。

正文：

- 左栏：核心论点、payload 摘要、meme-to-argument 判断。
- 中栏：12 维度评分矩阵，分为结构证据、整活转论证、社区讨论价值。
- 右栏：必须修改、可选修改、人工复核原因。
- 底部：社区展示卡预览、机器可读 JSON、policy source links。

这类页面应像评审工作台，不像营销 landing page。

## 双轨投稿口径

可以把公开站点里的投稿风格抽象成两条轨道：

| 轨道 | 适合内容 | 最低要求 |
| --- | --- | --- |
| `rigorous_argument` | 荒诞设定下有清楚论点、方法、证据和局限 | title、abstract、body、method/result/discussion/limitations、references |
| `joyful_zhenghuo` | 更强整活表达，但仍能转成观察或论证 | title、abstract、body、claim、discussion value、safety notice |

当前 schema 不新增顶层字段，轨道先放在 `ManuscriptInput.metadata.submission_track`，这样不破坏已有调用方。

## 不应该模仿的部分

- 不复制 logo、字体组合、页面资产或暗示官方合作关系。
- 不把社区投票当成自动质量裁判；工具只能给“进入下一阶段可能性”。
- 不声称能自动识别 AI 作弊；只能提示声明缺失、证据不足或模板化风险。
- 不让整活质量覆盖安全红线；风险内容必须先升级人工复核。
- 不引入成人化、攻击真人、隐私泄露、医学法律误导或近期社会事件消费。

## 下一步可做

- 继续打磨 report renderer，把 `ReviewOutput` 转成更接近上面结构的 intake report。
- 在 `VenueProfile` 中显式描述 `routing_stage` 和 `submission_track`。
- 让 Markdown intake report 继续复用展示投影新增字段，减少报告和后台卡片的解释差异。
