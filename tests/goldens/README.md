# Golden 回归资产

这个目录保存高精度 golden artifact。
当前主要文件是 `review_output_snapshots.json`，覆盖以下三篇稿件：

- `absurd_but_rigorous.json`
- `funny_but_hollow.json`
- `serious_but_misfit.json`

## 当前规则

golden 对比前会先归一化这些字段：

- `created_at`
- `workflow_session_id`

这样做的目的是把时间戳和随机 session id 从快照里去掉，
保留真正需要回归的业务字段。

## 维护约定

- 改 recommendation、fallback payload 或 `ReviewOutput` 结构时，再考虑更新 golden。
- 更新 golden 后，同步检查 `docs/testing.md` 和根 README 里的测试说明。
