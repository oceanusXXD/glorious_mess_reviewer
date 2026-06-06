# Prompt 系统

这个目录管理 Prompt 模板加载、few-shot 组装和 venue guidance 注入。

## 文件说明

- `loader.py`：Jinja2 渲染、`PromptTemplate`、Prompt hash / version
- `few_shots.py`：按 preset 生成 few-shot 校准示例
- `venue_guidance.py`：生成 venue guidance 与法律边界说明
- `templates/`：四个 Agent 模板

## 当前约束

- 所有模板都要求 JSON-only 输出
- 缺失信息必须显式标注
- 模板会注入 SHIT venue guidance 与 calibration examples
- recommendation 逻辑不放在模板里，模板只负责结构化评审判断

## 维护约定

- 改模板、few-shot 或 venue guidance 时，同步跑
  `tests/test_prompts.py` 和 `tests/test_prompt_assets.py`。
- 改模板字段时，同步更新 `schemas/` 与 Agent 文档。
