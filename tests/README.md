# 测试总览

这个目录保存自动化测试、fixture 资产和 golden 回归文件。

## 当前覆盖范围

- API 集成测试
- CLI 行为测试
- 数据契约与 settings
- prompt 渲染与 prompt 资产
- provider retry / 解析失败路径
- 运行时 / 工作流 / pipeline 行为
- workflow session 摘要查询与失败事件持久化
- scoring / recommendation / golden 回归
- SQLite 持久化与查询

## 运行方式

```bash
py -3.11 -m pytest
```

## 验证约定

测试数量会随功能变更而变化。交付前以本地运行
`python -m pytest -q` 的输出为准，不在这里维护固定 passed 数。

## 测试资产地图

| 资产 | 位置 | 作用 |
| --- | --- | --- |
| fixture 输入 | `tests/fixtures/` | 提供不同稿件输入，覆盖 API、CLI、golden 和 recommendation 分支 |
| golden 快照 | `tests/goldens/review_output_snapshots.json` | 保存三篇关键稿件的完整 `ReviewOutput` 快照 |
| prompt 测试 | `tests/test_prompts.py` | 校验四个模板的渲染内容与 guardrail |
| prompt 资产测试 | `tests/test_prompt_assets.py` | 校验 venue guidance 与 few-shot 的 preset 变化 |
| scoring 测试 | `tests/test_scoring.py` | 校验 rule cap 与 recommendation 分支 |
| API 测试 | `tests/test_api.py` | 校验 HTTP 主路径、fallback、provider 异常、工作流会话查询和查询接口 |
| CLI / logging 测试 | `tests/test_logging_and_cli.py` | 校验 CLI 命令、JSON 输出、结构化错误、工作流持久化和 event log |
| storage 测试 | `tests/test_storage.py` | 校验 SQLite 写入、事务、读回与工作流会话持久化 |

## 维护约定

- 改 fixture 时，同步更新 `tests/fixtures/README.md`。
- 改 golden 时，同步更新 `tests/goldens/README.md`
  和 `docs/testing.md`。
- 改 `ReviewOutput`、recommendation 或 fallback payload 时，
  同步更新 golden 测试与文档。
