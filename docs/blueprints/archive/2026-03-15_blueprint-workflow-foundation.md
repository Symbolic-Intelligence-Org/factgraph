# Task Blueprint: Blueprint Workflow Foundation

- Status: archived
- Created: 2026-03-15
- Last Updated: 2026-03-15
- Related Modules:
  - `docs/`
  - `src/factpy_kernel/application/docs`
  - `src/factpy_kernel/`
- Related Docs:
  - [docs/architecture_principles.md](/Users/zhenzhili/hnsm-backend/docs/architecture_principles.md)
  - [docs/blueprints/README.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/README.md)
  - [docs/README.md](/Users/zhenzhili/hnsm-backend/docs/README.md)
- Audit Log:
  - [2026-03-15_blueprint-workflow-foundation.audit.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/2026-03-15_blueprint-workflow-foundation.audit.md)

## 1. Problem

项目缺少一套明确、可持续、可审计的蓝图工作流。  
历史蓝图、当前实现文档和任务级设计约束混在一起，导致：

- 新任务没有统一入口
- 多轮实现容易发生 scope drift
- 模块 docs 与蓝图之间职责不清
- 历史蓝图缺少明确的归档边界

## 2. Goals

- 建立仓库级蓝图工作流规则
- 明确蓝图、模块 docs、历史蓝图、稳定原则文档的职责分工
- 提供 active/archive/templates 目录结构
- 给 Codex 增加可读取的 `AGENTS.md` 约束
- 修正当前 `application` 文档里的失效蓝图引用

## 3. Non-goals

- 不重写全部历史蓝图正文
- 不把历史蓝图改造成当前实现说明
- 不一次性整理所有模块文档
- 不引入仓库外部依赖的自动化脚本

## 4. Current Context

- 当前实现真相已经主要落在 `src/factpy_kernel/*/docs/`
- `docs/blueprint_history/` 中保留了大量历史蓝图
- 仓库此前没有实际落盘的 `AGENTS.md`
- `application` 相关文档存在指向旧路径的蓝图引用

## 5. Proposed Shape

- 在仓库根引入 `AGENTS.md`，定义 blueprint-first workflow
- 在 `src/factpy_kernel/AGENTS.md` 中声明模块 docs 的“当前真相”职责
- 新建 `docs/blueprints/{active,archive,templates}/`
- 新建 `docs/README.md` 与 `docs/architecture_principles.md`
- 为 `docs/blueprint_history/` 增加边界说明
- 更新 `application` 文档，使其链接到现存历史蓝图与新工作流入口

## 6. Boundaries And Invariants

- 模块 docs 仍然是当前实现真相
- 蓝图只负责任务约束、决策和归档 rationale
- 历史蓝图继续保留历史语境，不追代码
- 新工作流要能在后续 Codex 任务中直接复用

## 7. Acceptance

- [x] 仓库存在可读取的 `AGENTS.md` workflow 规则
- [x] `docs/blueprints/` 目录结构与模板已建立
- [x] `docs/README.md` 已作为文档入口落地
- [x] 历史蓝图区边界说明已补齐
- [x] `application` 侧失效链接已修正

## 8. Implementation Plan

1. 新增仓库级 workflow 文档与 `AGENTS.md`
2. 新增蓝图目录、模板与 legacy 说明
3. 更新现有模块文档的蓝图引用
4. 归档本次工作作为首个样例

## 9. Docs To Update

- `README.md`
- `docs/README.md`
- `docs/architecture_principles.md`
- `docs/blueprints/README.md`
- `docs/blueprint_history/README.md`
- `src/factpy_kernel/application/docs/README.md`
- `src/factpy_kernel/application/docs/01_overview.md`
- `src/factpy_kernel/application/docs/01_overview_en.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 已建立仓库级蓝图 workflow、模板、索引与 `AGENTS.md` 层级规则。
  - 已补一个归档样例，作为后续任务参考。
- 与 blueprint 不同的地方：
  - 未创建仓库外部 skill 或自动化脚本。
- 为什么会有这些调整：
  - 当前目标是先把 repo-native 的规则和目录骨架建立起来，让未来 Codex 能直接遵守。
- 归档说明：
  - 本文档作为 bootstrap 样例直接归档，标记新工作流已经开始生效。
