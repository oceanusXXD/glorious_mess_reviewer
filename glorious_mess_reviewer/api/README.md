# API 模块

这个目录保存 FastAPI 应用入口与 HTTP 层封装。

## 文件说明

- `app.py`：构建 FastAPI app，挂载路由和 app state
- `dependencies.py`：从 `app.state` 提取运行时评审服务与 store
- `errors.py`：统一错误 envelope 和异常处理

## 当前接口

- `GET /health`
- `POST /review`
- `POST /review/risk-audit`
- `POST /review/venue-fit-audit`
- `POST /review/dry-run`
- `GET /review/{run_id}`
- `GET /reviews`
- `GET /reviews/display`
- `GET /workflows`
- `GET /workflow-sessions`
- `GET /workflow/{session_id}`
- `GET /venue/default`
- `POST /venue/validate`

## 错误语义

- `404 review_not_found`
- `404 workflow_not_found`
- `422 invalid_request`
- `502 provider_failure`
- `500 internal_error`

## 维护约定

- 改 response model 时，先改 `schemas/`，再改这里和 `docs/api.md`。
- API 与 CLI 共用 runtime wiring，不要在这里单独复制 provider / store 逻辑。
- 正式评审、风险审计、venue 适配审计走运行时服务；
  `dry-run` 走 orchestrator 的确定性路径。
