# 配置说明

运行配置由 `glorious_mess_reviewer.config.settings.Settings` 管理。
默认环境变量前缀是 `GLORIOUS_MESS_`，OpenAI key 额外兼容 `OPENAI_API_KEY`。

## 加载优先级

以当前实现为准，配置优先级从高到低如下：

1. 显式传入 `Settings(...)`
2. 环境变量
3. `.env`
4. 代码默认值

## 主要配置项

### 应用与日志

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `GLORIOUS_MESS_APP_NAME` | `glorious_mess_reviewer` | 应用名 |
| `GLORIOUS_MESS_ENVIRONMENT` | `development` | 运行环境标签 |
| `GLORIOUS_MESS_HOST` | `127.0.0.1` | HTTP 服务监听地址 |
| `GLORIOUS_MESS_PORT` | `8000` | HTTP 服务端口 |
| `GLORIOUS_MESS_LOG_LEVEL` | `INFO` | 日志级别 |
| `GLORIOUS_MESS_DEBUG` | `false` | 调试模式 |
| `GLORIOUS_MESS_PROMPT_VERSION` | `v1` | Prompt 版本标识 |
| `GLORIOUS_MESS_LOG_PROMPT_TEXT` | `false` | 是否记录完整 Prompt 文本 |

### Provider 与模型

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `GLORIOUS_MESS_PROVIDER_BACKEND` | `openai` | 当前支持 `openai` / `mock` |
| `OPENAI_API_KEY` | 无 | OpenAI API key |
| `GLORIOUS_MESS_OPENAI_API_KEY` | 无 | namespaced 的 OpenAI API key |
| `GLORIOUS_MESS_OPENAI_BASE_URL` | 无 | 可选的 OpenAI-compatible base URL |
| `GLORIOUS_MESS_OPENAI_API_STYLE` | `responses` | `responses` 或 `chat_completions` |
| `GLORIOUS_MESS_DEFAULT_MODEL` | `gpt-4o-mini` | 默认模型名；生产环境建议显式设置 |
| `GLORIOUS_MESS_DEFAULT_TEMPERATURE` | `0.2` | 默认温度 |
| `GLORIOUS_MESS_REQUEST_TIMEOUT_SECONDS` | `60` | 单次请求超时 |
| `GLORIOUS_MESS_PROVIDER_MAX_RETRIES` | `1` | provider 级重试次数 |

### 存储与评审流

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `GLORIOUS_MESS_DATABASE_PATH` | `glorious_mess_reviews.db` | SQLite 文件路径 |
| `GLORIOUS_MESS_STORE_RAW_AGENT_OUTPUTS` | `true` | 是否持久化 `raw_agent_outputs` |
| `GLORIOUS_MESS_MINIMUM_REVIEWABLE_CHARACTERS` | `1200` | 默认最小可评审字数阈值 |

## 行为说明

- `provider_backend` 当前只支持 `openai` 和 `mock`。
- `GLORIOUS_MESS_PORT` 必须在 `1..65535` 范围内。
- `GLORIOUS_MESS_MINIMUM_REVIEWABLE_CHARACTERS` 必须大于 0，避免 preset 解析到运行时才失败。
- `mock` backend 主要用于测试，不是正式运行路径。
- `dry-run` 不要求 provider。
- `review`、`risk-audit`、`venue-fit-audit` 都要求 provider。
- 默认 `openai_api_style=responses` 使用 Responses API structured output。
- OpenAI-compatible `/chat/completions` endpoint 使用 `GLORIOUS_MESS_OPENAI_API_STYLE=chat_completions`。
- `doctor` 只检查本地 readiness，不会发起模型请求。
- `doctor --require-provider` 适合部署或 CI 环境，用于强制确认 provider-backed 工作流可用。
- 默认 preset `shit-screening-default` 的最小可评审字数会继承
  `GLORIOUS_MESS_MINIMUM_REVIEWABLE_CHARACTERS`。
- `shit-hardcore-screening` 与 `shit-abstract-screening` 会覆盖自己的 preset 阈值。

## 示例

```bash
set GLORIOUS_MESS_PROVIDER_BACKEND=openai
set OPENAI_API_KEY=your_key_here
set GLORIOUS_MESS_DEFAULT_MODEL=your_model_here
set GLORIOUS_MESS_REQUEST_TIMEOUT_SECONDS=60
set GLORIOUS_MESS_PROVIDER_MAX_RETRIES=1
set GLORIOUS_MESS_DATABASE_PATH=glorious_mess_reviews.db
set GLORIOUS_MESS_MINIMUM_REVIEWABLE_CHARACTERS=1200
```

### OpenAI-compatible Chat 示例

部分模型服务只提供 OpenAI-compatible Chat Completions API。此时需要切换 API style：

```bash
set GLORIOUS_MESS_PROVIDER_BACKEND=openai
set GLORIOUS_MESS_OPENAI_API_STYLE=chat_completions
set GLORIOUS_MESS_OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
set GLORIOUS_MESS_OPENAI_API_KEY=your_key_here
set GLORIOUS_MESS_DEFAULT_MODEL=qwen-plus
set GLORIOUS_MESS_REQUEST_TIMEOUT_SECONDS=120
```

[阿里云百炼 / DashScope 的 OpenAI 兼容 Chat 文档](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)列出的 base URL 是 `https://dashscope.aliyuncs.com/compatible-mode/v1`，HTTP endpoint 是 `/chat/completions`。在本项目里只需要配置 base URL。

## 本地诊断

```bash
glorious_mess_reviewer doctor
glorious_mess_reviewer doctor --require-provider
```

典型返回字段：

- `database_ok`：SQLite 文件是否可初始化和查询
- `provider_configured`：当前 provider 是否可构建
- `dry_run_ready`：是否可以运行 `review --dry-run`
- `full_review_ready`：是否可以运行完整 review / risk-audit / venue-fit-audit

## 数据保留相关配置

- `GLORIOUS_MESS_STORE_RAW_AGENT_OUTPUTS=true` 时，最终输出和持久化记录会保留 raw agent payload。
- `GLORIOUS_MESS_LOG_PROMPT_TEXT=false` 是默认值；只有显式开启时才把完整 prompt 文本写入事件日志。
- `GLORIOUS_MESS_DATABASE_PATH` 指向的 SQLite 文件包含请求 payload、评审输出、工作流产物和事件日志。
  如果稿件包含敏感内容，应把该文件放到受控目录并按本地政策处理保留周期。
- 面向匿名演示或公开分享时，建议设置 `GLORIOUS_MESS_STORE_RAW_AGENT_OUTPUTS=false`，并删除本地数据库、`.env` 和 provider benchmark 输出。

## 相关文件

- 配置实现：[../glorious_mess_reviewer/config/settings.py](../glorious_mess_reviewer/config/settings.py)
- 日志实现：[../glorious_mess_reviewer/config/logging.py](../glorious_mess_reviewer/config/logging.py)
- CLI 入口：[../glorious_mess_reviewer/cli/main.py](../glorious_mess_reviewer/cli/main.py)
