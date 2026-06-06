# Provider 模块

这个目录保存 LLM provider 抽象与具体实现。

## 文件说明

- `base.py`：provider 接口、JSON 解析和 schema 校验辅助
- `openai_provider.py`：OpenAI Responses API 与 OpenAI-compatible Chat Completions 实现
- `mock_provider.py`：测试用 mock provider

## 当前约束

- 正式运行路径使用 `openai` backend。
- `openai_api_style=responses` 使用 Responses API structured output。
- `openai_api_style=chat_completions` 使用 `/chat/completions` 和 JSON object response format，适合 OpenAI-compatible endpoint。
- `mock` backend 主要用于测试和受控 fixture。
- provider 选择和注入在 `runtime/wiring.py` 中完成。
- 仓库自己管理重试策略，测试会验证 SDK 内部重试关闭后的行为。

## 维护约定

- 改 OpenAI 调用行为时，优先看 `tests/test_openai_provider.py`。
- 改 provider 错误语义时，同步确认 API 和 CLI 的
  `provider_failure` 输出。
