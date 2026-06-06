# 配置模块

这个目录提供运行时配置和日志初始化。

## 文件说明

- `settings.py`：`Settings`、环境变量映射、provider backend 选择
- `logging.py`：JSON logger formatter 与 root logger 初始化

## 当前约束

- 环境变量前缀是 `GLORIOUS_MESS_`
- OpenAI key 同时兼容 `OPENAI_API_KEY` 和 `GLORIOUS_MESS_OPENAI_API_KEY`
- `provider_backend` 当前只支持 `openai` 与 `mock`
- 默认最小可评审字数阈值是 `1200`

## 维护约定

- 改配置字段时，同步更新 `docs/configuration.md` 和测试。
- 改日志字段时，确认 API / CLI 错误输出和 event log 仍然稳定。
