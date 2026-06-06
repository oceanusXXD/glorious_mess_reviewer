# 测试样本

这个目录保存测试输入样本，所有文件都符合 `ManuscriptInput` 结构。

## 当前样本

- `absurd_but_rigorous.json`
  - 高质量、venue-aware、应该得到较高 recommendation 的样本
- `funny_but_hollow.json`
  - gimmick 明显但 payload 薄弱，适合覆盖 `dry-run` 和 gimmick 分支
- `partial_failure.json`
  - 用于覆盖 partial agent failure / fallback 路径
- `serious_but_misfit.json`
  - 结构较认真，但 venue 适配度不高

## 维护约定

- 新增 fixture 时，说明它覆盖的 recommendation 或 fallback 分支。
- 如果 fixture 进入 golden 回归，记得同步更新
  `tests/goldens/README.md` 和 `docs/testing.md`。
