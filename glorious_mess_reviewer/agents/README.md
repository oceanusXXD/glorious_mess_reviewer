# Agent 系统

这个目录保存四个内置评审 Agent 的 Python 封装，
以及 registry-style 的 `ScreeningAgentCatalog`。

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `base.py` | 统一的 provider 调用、Prompt 渲染、异常封装 |
| `han_ce_gate.py` | `HanCeGateAgent`，负责预检查 / intake / 风险初判 |
| `evidence_sludge_engine.py` | `EvidenceSludgeEngineAgent`，负责 claim / reasoning / evidence / payload |
| `absurdity_but_make_it_rigorous.py` | `AbsurdityButMakeItRigorousAgent`，负责 venue 适配度 / 整活质量 / 原创性 |
| `final_sediment_council.py` | `FinalSedimentCouncilAgent`，负责聚合上游结果 |
| `catalog.py` | 注册 node id、artifact key、phase 和 agent class |

## 职责边界

- Agent 负责产出结构化 panel 判断，不直接给最终 recommendation。
- recommendation 逻辑放在 `scoring/`。
- 工作流顺序放在 `workflows/`。
- 失败或 provider 问题会在 `base.py` 中封装成 `AgentCallError`，
  交由 orchestrator / workflow 处理。

## 维护约定

- 改 Agent 输出字段时，先同步数据契约，再同步模板和测试。
- 改 node id 或 artifact key 时，先同步 `catalog.py`、`workflows/`
  和 runtime 相关测试。
