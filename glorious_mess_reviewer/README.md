# 包总览

`glorious_mess_reviewer` 是仓库的 Python 主包。
它提供 FastAPI 服务、CLI 入口、provider 封装、
工作流运行时、评分逻辑和 SQLite 持久化。

## 子目录说明

| 目录 | 作用 |
| --- | --- |
| `agents/` | 四个内置评审 Agent 与 agent catalog |
| `api/` | FastAPI 应用入口、依赖注入和错误封装 |
| `benchmark.py` | benchmark suite 加载、执行、汇总和 Markdown report |
| `cli/` | 命令行入口 |
| `config/` | `Settings` 与日志初始化 |
| `display.py` | 从持久化 review 派生后台展示 payload |
| `orchestrator/` | 预检查、Agent 调用、fallback、输出投影 |
| `prompts/` | prompt loader、few-shot、venue guidance、模板 |
| `providers/` | OpenAI provider 与 mock provider |
| `runtime/` | 工作流注册、执行与评审服务 wiring |
| `schemas/` | Pydantic 数据契约与枚举 |
| `scoring/` | rule caps、加权评分、recommendation 逻辑 |
| `storage/` | SQLite 表结构与查询接口 |
| `workflows/` | 三个内置工作流定义 |

## 先读哪些文件

1. `schemas/contracts.py`
2. `runtime/README.md`
3. `workflows/README.md`
4. `orchestrator/review_pipeline.py`
5. `scoring/payload_vs_vibes.py`
6. `api/app.py`
7. `cli/main.py`

## 维护建议

- 改对外数据契约：先看 `schemas/`，
  再同步 API / CLI / docs / tests。
- 改正式评审主链路：先看 `workflows/` 和 `orchestrator/`。
- 改 recommendation：先看 `scoring/` 与 `tests/test_scoring.py`。
- 改 provider：先看 `providers/`、`runtime/`
  和 `tests/test_openai_provider.py`。
- 改 benchmark：同步 `benchmark.py`、`docs/benchmark.md`、
  `docs/examples/benchmark-suite.json` 和 `tests/test_benchmark.py`。
- 改 preset：同步 `schemas/`、`docs/venue-profile.md`、
  API/CLI 查询入口和测试。
