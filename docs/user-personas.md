# 用户画像与业务场景

glorious_mess_reviewer 的产品定位是 **S.H.I.T / 构石风格投稿的 initial screening desk**。
它不是替代最终编辑判断，而是把第一轮 intake、风险排查、venue fit 判断和审计记录标准化。

## 核心用户画像

### 1. 初筛编辑

- 目标：快速判断稿件是否值得进入下一轮。
- 痛点：投稿风格差异大，单靠直觉容易标准漂移。
- 使用入口：`review`、`list-reviews`、`show-review`。
- 成功标准：每篇稿件都有可解释推荐、分数、rule trace 和可复查记录。

### 2. 风险审核员

- 目标：先排除安全、滥用、违法或骚扰风险。
- 痛点：高整活度内容容易把风险包装成笑点。
- 使用入口：`risk-audit`、`/review/risk-audit`、`/workflow-sessions?workflow_id=screening.risk_audit.v1`。
- 成功标准：风险稿件先进入人工安全复核，不被 venue-fit 或幽默质量奖励。

### 3. 作者 / 投稿者

- 目标：投稿前确认稿件是否具备基本结构和 venue fit。
- 痛点：不知道“有梗”和“能被评审”之间差了什么。
- 使用入口：`new-manuscript`、`review --dry-run`、`show-default-venue`。
- 成功标准：在不调用 provider 的情况下先发现缺标题、缺摘要、正文太短或缺 limitations 等问题。

### 4. 平台工程师

- 目标：把初筛能力嵌入投稿后台、内部工具或审核面板。
- 痛点：需要稳定 API、类型化输出、查询接口和 SQLite audit trail。
- 使用入口：FastAPI `/review*`、`/reviews`、`/workflow-sessions`、`/workflow/{session_id}`。
- 成功标准：外部系统能按 `manuscript_id` 追踪 review、risk audit 和 venue-fit audit。

### 5. Rubric / Prompt 维护者

- 目标：调整 S.H.I.T 口径、preset 权重、prompt guidance 和 few-shot。
- 痛点：口径变化如果没有测试，很容易让推荐标签漂移。
- 使用入口：`docs/venue-profile.md`、`glorious_mess_reviewer/prompts/`、`glorious_mess_reviewer/scoring/`。
- 成功标准：每次 rubric 变化都有 fixture、scoring 或 golden 测试保护。

### 6. 开源采用者 / 部署评估者

- 目标：判断这个仓库是否能进入内部试点、二次开发或教学演示。
- 痛点：开源项目常见问题不是功能缺失，而是输入边界、查询性能、迁移策略和故障语义不清楚。
- 使用入口：`doctor --require-provider`、`python -m pytest -q`、`docs/api.md`、`docs/configuration.md`、`glorious_mess_reviewer/storage/README.md`。
- 成功标准：能在本地复现测试；能确认 `manuscript_id`、`limit`、SQLite schema 和 provider 配置的稳定边界。

### 7. 社区展示 / 运营维护者

- 目标：把初筛结果转成可读、可复查、适合社区流转的展示报告。
- 痛点：普通 LLM 审稿摘要很难解释“为什么进发酵区、为什么返修、为什么先人工复核”。
- 使用入口：`benchmark --markdown-output`、`show-review`、`show-workflow`、`/workflows`。
- 成功标准：能从 `ReviewOutput` 和 workflow artifacts 生成 gate checklist、阶段建议、必须修改项和展示卡片。

## 关键业务流程

### 投稿前自检

1. 作者运行 `new-manuscript --output draft.json`。
2. 作者按模板替换标题、摘要和正文。
3. 作者运行 `review --input draft.json --dry-run`。
4. 如果 dry-run 失败，先补结构和字数。

### 编辑初筛

1. 操作员运行 `doctor --require-provider`。
2. 对稿件运行 `review --input manuscript.json --output result.json`。
3. 根据 `final_recommendation` 决定下一步。
4. 用 `show-review` 或 `/review/{run_id}` 复查。

### 风险优先队列

1. 系统先运行 `risk-audit`。
2. `FLAG_FOR_HUMAN_REVIEW` 或 `BLOCK_BEFORE_REVIEW` 不进入 venue-fit 奖励。
3. 审核员通过 `list-workflow-sessions --workflow-id screening.risk_audit.v1` 拉取历史记录。

### 风险优先完整初筛

1. 完整 `review` 仍然先运行本地和 provider-backed precheck。
2. 如果有效 precheck 已经发现风险标记，系统直接走 `risk_gate`。
3. `risk_gate` 会跳过 evidence / value / meta 面板，避免高风险稿件继续获得 payload 或 venue-fit 奖励。
4. 输出仍是 `ReviewOutput`，但推荐标签会进入人工风险复核方向。

### Venue Fit 分诊

1. 对结构基本可评审的稿件运行 `venue-fit-audit`。
2. `STRONG_FIT` 需要 venue fit、meme-to-argument、zhenghuo execution 和 discussion value 同时过线。
3. `MISALIGNED` 不等于低质量，只说明不适合当前 S.H.I.T 初筛口径。

### S.H.I.T 三段流转

1. `Petri Dish / 培养皿`：作者或运营先用 `new-manuscript` 和 `review --dry-run` 做结构自检。
2. `Fermentation / 发酵区`：编辑运行 `review`，风险审核员必要时运行 `risk-audit`。
3. `Real S.H.*.T / 构石`：只有结构、payload、venue fit 和风险边界都讲得清楚的稿件，才进入更深人工评审或展示归档。

### Benchmark 采用评估

1. 新采用者先运行 `benchmark --mode dry-run`，确认本地 intake gate 和风险边界。
2. 有 provider 后再运行 `benchmark --mode review --limit 1`，确认真实模型能返回 schema-valid 的初筛输出。
3. 维护者比较完整 review 与 intake-only baseline，判断多面板工作流是否比简单 gate 更有价值。

### 开源采用评估

1. 先运行 `python -m pytest -q`，确认当前环境能通过完整回归。
2. 运行 `doctor` 和 `doctor --require-provider`，区分本地 dry-run readiness 与正式 provider-backed readiness。
3. 用 `new-manuscript` 生成输入样例，再用 `review --dry-run` 检查 schema、空白 ID、章节和字数边界。
4. 用 `list-workflow-sessions --limit 10` 和 API `limit=10` 验证 CLI/API 查询边界一致。
5. 用 `/workflows` 检查 `edges`、`parallel_groups` 和 `artifact_keys`，确认外部后台能理解工作流图结构。
6. 检查 SQLite 文件中的 `schema_metadata`，确认本地数据库处于当前 schema 版本。

## 非目标

- 不做最终录用决策。
- 不保证模型输出完全正确；输出应作为初筛证据链的一部分。
- 不替代法律、安全或伦理审核。
- 不保存云端状态；默认持久化在本地 SQLite。
- 不把 `mock` backend 当作正式 provider。

## 开源成功标准

一个强可用开源版本应持续满足：

- 新用户能在 5 分钟内完成 `doctor`、`new-manuscript`、`dry-run`。
- 工程用户能通过 FastAPI 和 SQLite 查询重建一条评审链路。
- Rubric 变化有测试保护，不靠口头约定。
- 安全边界写在 prompt、scoring、docs 和 tests 中。
- 贡献者知道如何提交 bug、feature、PR 和安全报告。
- 查询入口对 `manuscript_id`、`workflow_id`、`status` 和 `limit` 有稳定行为，适合接入外部后台。
- 默认 benchmark 能离线运行，真实模型 benchmark 可选且不会隐式消耗 API quota。
