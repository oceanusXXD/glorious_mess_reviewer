# S.H.I.T 审稿口径手册

这份手册描述的是一个很具体的判断标准：
一篇稿件可以很怪、很梗、很像学术 cosplay，
但它仍然要拿得出 claim、evidence、reasoning 或 payload，
才值得进入下一轮评审。

## 一句话口径

**S.H.I.T 喜欢有结构的怪稿，喜欢能转化成论点的梗，也喜欢能留下讨论价值的怪想法。**

## 评审桌的业务任务

这套口径服务的是初筛，不是最终录用。评审桌要把稿件分成几类：

- 值得进入下一轮的荒诞但有 payload 的稿件；
- 有 venue-native 能量但需要补结构、证据或论点的稿件；
- 认真但放错 venue 的稿件；
- 有梗但空心的稿件；
- 混乱到无法评审的稿件；
- 必须先人工安全复核的风险稿件。

因此输出不能只写“好笑”或“不好笑”，而要说明下一步该做什么。

## 三段流转

这套工具把社区出版流程拆成三个可执行阶段：

- `Petri Dish / 培养皿`：想法或初稿是否有标题、摘要、正文、基本 claim 和安全声明。
- `Fermentation / 发酵区`：可以进入讨论、初筛、风险审计和 venue fit 分诊。
- `Real S.H.*.T / 构石`：候选进入更深人工评审或展示归档。

机器输出只能建议阶段，不代表最终录用。

## 双轨投稿

- `rigorous_argument`：荒诞设定下仍然要有问题、方法、结果、讨论、局限和引用。
- `joyful_zhenghuo`：表达可以更强整活，但仍要把梗转成观察、论点或讨论价值。

当前轨道信息放在 `ManuscriptInput.metadata.submission_track`，避免破坏现有 schema。

## 看重什么

### 1. 先看稿件是不是可评审

- 有没有 `title`、`abstract`、`body`
- 结构是否足够支撑一次初筛
- 是否有最基本的 core claim
- 是否存在明显风险项

### 2. 再看怪得有没有内容

好稿件常见的样子：

- 设定离谱，但论点清楚
- 表达有梗，但 evidence 能落地
- 结果未必严肃，讨论价值很高
- 读完后，评审知道作者到底想证明什么

### 3. 最后看它是否适合这个 venue

SHIT 风格稿件通常要同时满足几件事：

- 有足够的 venue 适配度
- 有整活质量，不只是猎奇
- 能把 meme、比喻、段子转成 argument
- 至少能留下一个可讨论的观点或观察

## 常见拒稿模式

### 空洞 gimmick

典型症状：

- 标题响亮，正文很薄
- 大量笑点堆叠，没有可验证信息
- 论证链断裂，结论只靠语气撑着

这种稿件通常会走向：

- `REJECT_AS_EMPTY_GIMMICK`
- 或 `REVISION_REQUIRED_BEFORE_REVIEW`

### 混乱 sludge

典型症状：

- 有词，没有论证
- 有章节，没有逻辑
- 有姿态，没有结论

这种稿件通常会走向：

- `REJECT_AS_INCOHERENT_SLUDGE`

### 风险内容

典型症状：

- 滥用、仇恨、骚扰、非自愿色情等内容
- 可执行犯罪指令
- 明显越过 venue guidance 的法律边界

这种稿件会先被打上 `risk_flags`，完整初筛会走向
`ESCALATE_FOR_HUMAN_RISK_CHECK`，venue-fit 审计会走向
`BLOCKED_BY_RISK`。风险内容不能因为“很会整活”而得到正向 venue-fit 奖励。

## 常见推进模式

### 值得进下一轮

常见特征：

- core claim 能复述
- 结构清晰
- evidence 或 reasoning 至少有一条主线可追
- funny / absurd 的部分服务于观点表达

### 值得保留但要补 payload

常见特征：

- 创意很强
- venue 适配度很高
- 讨论价值明显
- 结果或 evidence 还需要补强

## preset 的用法

- `shit-screening-default`：默认口径，平衡结构、payload 和 venue 适配度
- `shit-hardcore-screening`：更看重 claim、method、evidence、result
- `shit-abstract-screening`：更看重整活质量、原创性和讨论价值

## 维护建议

需要调整 venue 口径时，优先同步这些地方：

- `docs/venue-profile.md`
- `glorious_mess_reviewer/prompts/`
- `glorious_mess_reviewer/scoring/`
- `tests/test_scoring.py`
