# CLI 模块

这个目录保存命令行入口 `glorious_mess_reviewer`。
CLI 面向本地操作员、编辑和调试者，所有输出默认都是 JSON，
便于保存、管道处理和自动化。

## 当前命令

| 命令 | 作用 | 是否需要 provider |
| --- | --- | --- |
| `doctor` | 检查数据库、provider、dry-run/full-review readiness | 否 |
| `new-manuscript` | 生成一份可评审 starter `ManuscriptInput` | 否 |
| `review` | 执行完整初筛工作流 | 是 |
| `review --dry-run` | 只做确定性预检查 | 否 |
| `risk-audit` | 执行 `screening.risk_audit.v1` | 是 |
| `venue-fit-audit` | 执行 `screening.venue_fit_audit.v1` | 是 |
| `benchmark` | 运行固定样本 benchmark，可输出 JSON / Markdown 报告 | dry-run 否，review 是 |
| `show-default-venue` | 打印内置 `VenueProfile` | 否 |
| `show-review` | 读取一条持久化 review 记录 | 否 |
| `show-review-display` | 读取一条适合后台展示的轻量 review 投影 | 否 |
| `show-workflow` | 读取一条完整 workflow session | 否 |
| `list-reviews` | 列出完整 review 摘要 | 否 |
| `list-review-displays` | 列出适合后台队列页的 review 展示摘要 | 否 |
| `review-display-overview` | 汇总后台队列的 lane counts、gate pressure 和 repair hotspots | 否 |
| `list-workflows` | 列出已注册 workflow metadata | 否 |
| `list-workflow-sessions` | 列出已持久化 workflow session 摘要 | 否 |
| `serve` | 启动 FastAPI HTTP 服务 | 否 |

## 推荐本地流程

```bash
glorious_mess_reviewer doctor
glorious_mess_reviewer new-manuscript --output sample-manuscript.json
glorious_mess_reviewer review --input sample-manuscript.json --dry-run
glorious_mess_reviewer review --input sample-manuscript.json --output review-output.json --report-output intake-report.md
glorious_mess_reviewer list-workflow-sessions
```

`review --report-output` 只适用于 provider-backed 完整初筛。它会把 `ReviewOutput` 和原始 `ManuscriptInput` 渲染成 Markdown intake report，包含 queue triage、readiness gates、score groups 和 repair targets，适合交给编辑、作者或后台展示层阅读。

## Benchmark

离线 benchmark 不需要 provider，适合 CI 和开源采用前检查：

```bash
glorious_mess_reviewer benchmark \
  --mode dry-run \
  --output benchmark-report.json \
  --markdown-output benchmark-report.md
```

真实模型 benchmark 需要先配置 provider：

```bash
glorious_mess_reviewer benchmark --mode review --limit 1
```

`benchmark` 会把完整 JSON report 打印到 stdout。`--markdown-output` 生成给人读的摘要表，`--output` 保留给自动化处理。

## 查询命令

```bash
glorious_mess_reviewer list-reviews --limit 20
glorious_mess_reviewer list-review-displays --limit 20
glorious_mess_reviewer list-review-displays --sort queue_priority --lane human_risk_review
glorious_mess_reviewer list-review-displays --sort repair_priority --lane author_revision
glorious_mess_reviewer review-display-overview --limit 100
glorious_mess_reviewer list-reviews --manuscript-id absurd-rigorous-001

glorious_mess_reviewer list-workflow-sessions --limit 20
glorious_mess_reviewer list-workflow-sessions --workflow-id screening.risk_audit.v1
glorious_mess_reviewer list-workflow-sessions --status failed

glorious_mess_reviewer show-review --run-id <run_id>
glorious_mess_reviewer show-review-display --run-id <run_id>
glorious_mess_reviewer show-workflow --session-id <session_id>
```

## 错误语义

普通用户错误会返回 JSON 到 stderr，而不是 Python traceback：

- `input_not_found`
- `input_read_failed`
- `invalid_input`
- `invalid_benchmark_suite`
- `output_write_failed`
- `provider_failure`
- `review_not_found`
- `workflow_not_found`

退出码约定：

- `0`：成功
- `1`：输入、输出、查询或 readiness 检查失败
- `2`：provider 缺失或 provider 调用失败

## 维护约定

- 不要在 CLI 内重复实现 provider / store wiring。
- 改命令参数时，同步更新根 README、`docs/api.md`、`docs/configuration.md`
  和 `tests/test_logging_and_cli.py`。
