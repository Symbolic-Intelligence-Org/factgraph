# Task Blueprint: Docs Memory And Blueprint Realignment

- Status: archived
- Created: 2026-03-22
- Last Updated: 2026-03-22
- Related Modules:
  - `docs`
  - `memory`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/README.md](../../README.md)
  - [docs/blueprints/README.md](../README.md)
  - [docs/blueprints/active/2026-03-15_overall-system-blueprint.md](./2026-03-15_overall-system-blueprint.md)
  - [docs/blueprints/active/2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
  - [docs/blueprints/active/2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
- Audit Log:
  - [2026-03-22_docs-memory-and-blueprint-realignment.audit.md](./2026-03-22_docs-memory-and-blueprint-realignment.audit.md)

## 1. Problem

当前仓库的文档落点已经出现两类混杂：

- `docs/` 根目录中同时存在稳定原则、references、session handoff 和一份不属于 blueprint 工作流的架构 design doc；
- `docs/blueprints/active/` 中还保留着三个已经不再代表当前推进方向的早期母蓝图。

这会造成两个现实问题：

1. 后续 agent 容易把根目录 design doc 当成当前实现约束，或把旧 active blueprint 当成仍在推进的任务。
2. session continuity 材料与“当前真相/任务约束”材料仍混在 `docs/` 中，职责边界不清晰。

本任务要把这几类材料重新落位：

- 将 root design doc 重生为新的 active 母蓝图；
- 将 handoff 迁移到独立的 `memory/` 机制；
- 将三个已被取代的 active blueprint 以 `superseded` 路径归档；
- 同步索引和工作流文档，使新的职责边界可持续维护。

## 2. Goals

- 建立新的 `memory/` 工作区，用于承载 session continuity 材料，并明确其 non-authoritative 边界。
- 新建一个 active 母蓝图，承接 2026-03-22 architectural pivot 的当前阶段任务约束。
- 将三个旧 active blueprint 标记为 `superseded` 并归档。
- 更新索引与工作流文档，使 `docs/`、`docs/blueprints/`、`memory/` 的职责分工清晰一致。

## 3. Non-goals

- 不实现 ECSS 编码或 Souffle provenance 功能本身。
- 不在本任务中打开新的子蓝图实现线。
- 不修改 `src/factpy_kernel/*/docs/` 的实现真相内容。
- 不重写 archive 中的历史 rationale 内容，只修正当前工作流入口。

## 4. Current Context

- 当前实现入口：
  - `docs/design-20260322-architectural-pivot.md` 承载了最新的战略判断，但不在 blueprint 工作流内。
  - `docs/session_handoff_2026-03-20.md`、`docs/session_handoff_2026-03-21.md`、`docs/session_handoff_2026-03-22.md` 仍位于 `docs/` 根目录。
  - `docs/blueprints/active/` 中仍保留三个早期 draft 母蓝图。
- 当前已知约束：
  - 非 trivial 文档工作流调整也必须先建 blueprint。
  - 新的 durable 文档入口需要更新 `docs/README.md`。
  - 被替代的 active blueprint 应记录 successor，并以 `superseded` 路径归档。
- 当前相关历史蓝图：
  - `docs/blueprints/archive/2026-03-18_session-handoff-refresh.md`
  - `docs/blueprints/archive/2026-03-19_evidence-tree-stage-handoff-refresh.md`
  - `docs/blueprints/archive/2026-03-19_blueprint-workflow-active-archive-cleanup.md`

## 5. Proposed Shape

### 5.1 文档职责重排

- `docs/architecture_principles.md`
  - 继续承载稳定原则与长期边界。
- `docs/blueprints/active/`
  - 继续承载当前任务约束。
  - 新增一份 2026-03-22 阶段母蓝图，作为当前唯一长期 active 母图。
- `docs/blueprints/archive/`
  - 接收三个被新母蓝图取代的旧 active blueprint。
- `memory/`
  - 新增为 repo-level operational memory 区。
  - 用于 session continuity，不承担当前真相，不替代 active blueprint。

### 5.2 设计文档迁移方式

- root design doc 不继续作为独立根目录设计文档保留。
- 其核心内容迁移并重组到新的 active 母蓝图：
  - 当前阶段问题定义
  - 关键架构判断
  - ECSS domain validation 与 Souffle provenance PoC 的下一步顺序
  - 子蓝图拆分建议

### 5.3 Memory 结构

- `memory/README.md`
  - 定义 memory 的职责与边界。
- `memory/current.md`
  - 当前 canonical operational memory 入口。
- `memory/session_handoffs/YYYY-MM-DD.md`
  - 归档具体会话 handoff 文档。

### 5.4 Superseded 归档策略

- `2026-03-15_overall-system-blueprint`
- `2026-03-16_temporal-hybrid-reasoning-blueprint`
- `2026-03-17_runtime-traceability-explainability-blueprint`

三者都补齐：

- `Status: superseded`
- `Outcome / Deviations`
- audit 中的 successor 记录

然后移动到 `docs/blueprints/archive/`。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 模块实现真相仍以 `src/factpy_kernel/*/docs/` 为准。
  - `memory/` 只承载操作记忆，不承载当前实现真相或任务约束。
  - 新母蓝图仍应遵守 blueprint 工作流，而不是退化回自由形态 design memo。
- 明确不做的内容：
  - 不把 `memory/` 写成第二套 docs index。
  - 不让 handoff/memory 材料重新回流为 architecture truth。
  - 不把旧 active blueprint 改写成“当前方向仍开放”的文档。
- 兼容性约束：
  - 旧设计与 handoff 的可读信息不能在迁移中丢失。
  - `docs/README.md`、`docs/blueprints/README.md`、`AGENTS.md`、`docs/architecture_principles.md` 的描述必须一致。

## 7. Acceptance

- [ ] 新的 `memory/` 结构已建立，并有明确入口文档
- [ ] `docs/design-20260322-architectural-pivot.md` 已重生为新的 active 母蓝图
- [ ] 三个旧 active blueprint 已按 `superseded` 路径归档
- [ ] `docs/README.md` 与相关工作流文档已同步

## 8. Implementation Plan

1. 创建本次迁移蓝图与 audit，并冻结范围。
2. 新建 `memory/` 目录结构，迁移现有 handoff 材料并建立 `current.md` 入口。
3. 新建 2026-03-22 阶段母蓝图与 audit，吸收 root design doc 的当前阶段约束。
4. 更新 `docs/README.md`、`docs/blueprints/README.md`、`docs/architecture_principles.md` 与 `AGENTS.md`，反映新的文档职责边界。
5. 将三个旧 active blueprint 标记为 `superseded` 并归档，更新 archive inventory。

## 9. Docs To Update

- `docs/README.md`
- `docs/blueprints/README.md`
- `docs/architecture_principles.md`
- `AGENTS.md`
- `memory/README.md`
- `memory/current.md`

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
  - 新建了 `memory/` 作为 operational memory 区，并建立 `memory/current.md` 与 `memory/session_handoffs/`。
  - `docs/design-20260322-architectural-pivot.md` 已退场，其当前阶段内容重生为 `2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md`。
  - 三个旧 active 母蓝图已标记为 `superseded` 并迁入 archive。
  - `docs/README.md`、`docs/blueprints/README.md`、`docs/architecture_principles.md` 与 `AGENTS.md` 已同步新的职责边界。
- 与 blueprint 不同的地方：
  - 额外顺手移除了 `docs/README.md` 中一个已失效的 `src/factpy_kernel/ecss/docs/README.md` 链接。
- 为什么会有这些调整：
  - 该链接在本次索引同步中被验证为不存在；继续保留只会增加索引噪音。
- 归档说明：
  - 本任务为 docs-workflow migration slice，已完成并归档；当前 active 目录应只保留新的阶段母蓝图。
