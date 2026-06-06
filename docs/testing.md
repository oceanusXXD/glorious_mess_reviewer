# 测试说明

这个仓库用 pytest 保护 API、CLI、schema、provider、
工作流运行时和 golden 回归。
文档中的测试描述以当前测试集为准。

## 运行方式

```bash
py -3.11 -m pytest
```

最近一次本地验证结果：

- 当前分支交付前运行 `python -m pytest -q`
- 具体通过数量以本地命令输出为准，避免文档和测试集变更脱节

## 测试分层

### 1. Schema 与 Settings

对应文件：

- `tests/test_schemas.py`
- `tests/test_settings.py`
- `tests/test_venue_profile_behavior.py`

关注点：

- `ManuscriptInput` 和类型化数据契约校验
- `RecommendationPolicy` 阈值关系
- `VenueProfile` preset 行为
- `raw_agent_outputs` 与工作流产物 envelope 的结构稳定性
- settings alias 与 provider backend 约束

### 2. Prompt 与 Provider

对应文件：

- `tests/test_prompts.py`
- `tests/test_prompt_assets.py`
- `tests/test_openai_provider.py`
- `tests/test_mock_provider_failures.py`
- `tests/test_json_parsing.py`

关注点：

- 四个 prompt 模板的渲染结果
- venue guidance 与 few-shot 是否按 preset 变化
- OpenAI provider 的 timeout / retry / 解析失败行为
- mock provider 的异常路径
- JSON parsing helper 的稳定性

### 3. API / CLI / Storage

对应文件：

- `tests/test_api.py`
- `tests/test_logging_and_cli.py`
- `tests/test_storage.py`

关注点：

- `/health`、`/review`、`/review/dry-run`
- `/review/risk-audit`、`/review/venue-fit-audit`
- `/review/{run_id}`、`/reviews`、`/workflows`
- `/workflow-sessions` 的会话摘要查询与过滤
- `/workflow/{session_id}`、`/venue/default`、`/venue/validate`
- CLI 的 `review`、`risk-audit`、`venue-fit-audit`
- CLI 的 `doctor`、`new-manuscript`、`show-*`、`list-*`、`serve`
- CLI 对普通输入错误的 JSON 错误输出
- SQLite 表写入、读回和工作流会话持久化
- provider 缺失、partial failure、fallback 等边界路径

### 4. 运行时 / 工作流 / Pipeline

对应文件：

- `tests/test_runtime.py`
- `tests/test_workflow_runtime.py`
- `tests/test_agent_catalog.py`
- `tests/test_review_pipeline.py`

关注点：

- 工作流注册表与运行时 wiring
- 工作流步骤与工作流产物持久化
- 失败 workflow session 与 `workflow_failed` 事件持久化
- agent catalog 元数据
- precheck merge 与 pipeline 决策分支

### 5. Scoring 与 Golden 回归

对应文件：

- `tests/test_scoring.py`
- `tests/test_golden_samples.py`

关注点：

- weighted score
- rule caps
- screening recommendation 分支
- 三个关键 fixture 的完整 `ReviewOutput` 快照回归

### 6. Benchmark 回归

对应文件：

- `tests/test_benchmark.py`

关注点：

- `docs/examples/benchmark-suite.json` 能被加载和校验
- `benchmark --mode dry-run` 不依赖 provider
- 7 个固定样本的 intake 接受状态和风险标记精确匹配
- Markdown benchmark report 能作为展示和人工复查产物

## 测试资产

- `tests/fixtures/`：输入稿件样本
- `tests/goldens/review_output_snapshots.json`：完整输出 golden
- `docs/examples/benchmark-suite.json`：benchmark suite 描述，引用测试 fixture 并设置期望结果

golden 回归会把 `created_at` 和 `workflow_session_id`
归一化后再比较，避免时间戳与 session id 引入噪声。

## Benchmark 命令

```bash
glorious_mess_reviewer benchmark --mode dry-run --markdown-output benchmark-report.md
```

真实 provider 验证需要显式配置 key，并建议先限制 case 数：

```bash
glorious_mess_reviewer benchmark --mode review --limit 1
```

## 维护约定

- 改数据契约、recommendation、fallback payload
  或工作流产物时，优先补测试再改代码。
- 改 fixture 或 golden 时，同步更新
  `tests/fixtures/README.md` 与 `tests/goldens/README.md`。
- 改外部接口或 CLI 行为时，同步更新根 README 与 `docs/api.md`。
- 改 benchmark case 或指标时，同步更新 `docs/benchmark.md` 和 `docs/examples/benchmark-suite.json`。
