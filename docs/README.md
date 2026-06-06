# 文档索引

`docs/` 目录保存这个仓库的对外说明、运行约定和设计补充材料。
这些文档以当前代码实现为准，重点覆盖业务场景、API、配置、测试、
preset、Prompt 设计、CLI 使用和架构分层。

## 建议阅读顺序

1. [../README.md](../README.md)：项目总览与快速开始
2. [user-personas.md](user-personas.md)：用户画像、业务流程和开源成功标准
3. [../glorious_mess_reviewer/cli/README.md](../glorious_mess_reviewer/cli/README.md)：CLI 命令与本地操作流
4. [api.md](api.md)：HTTP 接口与返回数据契约
5. [configuration.md](configuration.md)：运行配置、provider 与数据保留
6. [venue-profile.md](venue-profile.md)：内置 venue profile、preset、推荐标签和自定义 profile
7. [shit-review-playbook.md](shit-review-playbook.md)：S.H.I.T 风格审稿口径
8. [prompt-design.md](prompt-design.md)：Prompt 组织方式与 guardrail
9. [benchmark.md](benchmark.md)：离线和真实模型 benchmark
10. [testing.md](testing.md)：测试范围与回归约定
11. [shit-site-alignment.md](shit-site-alignment.md)：S.H.*.T 站点对齐分析
12. [agent-framework-optimization.md](agent-framework-optimization.md)：当前架构分层说明

## 文档索引

| 文件 | 作用 |
| --- | --- |
| `user-personas.md` | 用户画像、核心业务流程、非目标和开源成功标准 |
| `api.md` | FastAPI 路由、请求/响应模型、错误语义 |
| `configuration.md` | `Settings` 字段、环境变量、provider 约束 |
| `venue-profile.md` | 默认 venue、三个 preset、推荐阈值、运营标签、自定义 profile |
| `benchmark.md` | benchmark suite、指标、离线/真实模型运行方式 |
| `testing.md` | pytest 运行方式、测试分类、golden 回归说明 |
| `prompt-design.md` | Prompt 模板、few-shot、venue guidance 组织方式 |
| `shit-review-playbook.md` | S.H.I.T 风格的评审口径与常见判断模式 |
| `shit-site-alignment.md` | 公开 S.H.*.T 站点产品形态、展示页和不应模仿边界 |
| `agent-framework-optimization.md` | runtime / workflow / orchestrator / scoring 分层解释 |

## 示例资产

| 文件 | 作用 |
| --- | --- |
| `examples/custom-venue-profile.json` | 可直接提交给 `POST /venue/validate` 的自定义 `VenueProfile` 示例 |
| `examples/benchmark-suite.json` | CLI benchmark 默认 suite |
| `assets/display-queue-overview.svg` | README dashboard preview for queue pressure and repair hotspots |
| `assets/screening-flow.svg` | README workflow preview for risk-first routing and audit outputs |

## 维护约定

- 改 API、CLI、数据契约或工作流时，同步更新对应文档。
- 改 preset、阈值或 recommendation policy 时，同步更新 `venue-profile.md`。
- 改 Prompt 模板、provider 或 fallback 逻辑时，同步更新 `prompt-design.md` 与 `testing.md`。
- 根 README 保留总览；细节文档尽量放到这里维护。
