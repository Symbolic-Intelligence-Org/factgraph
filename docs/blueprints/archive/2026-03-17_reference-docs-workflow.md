# Task Blueprint: Reference Docs Workflow

- Status: archived
- Created: 2026-03-17
- Last Updated: 2026-03-17
- Related Modules:
  - `docs/`
  - `docs/blueprints/`
- Related Docs:
  - [docs/README.md](/Users/zhenzhili/hnsm-backend/docs/README.md)
  - [docs/blueprints/README.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/README.md)
  - [docs/architecture_principles.md](/Users/zhenzhili/hnsm-backend/docs/architecture_principles.md)
- Audit Log:
  - [2026-03-17_reference-docs-workflow.audit.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/2026-03-17_reference-docs-workflow.audit.md)

## 1. Problem

仓库已经形成了稳定原则、活动蓝图、模块真相和历史蓝图这几类文档，但仍有一类实际存在且被使用的材料没有正式角色：

- 外部标准或竞品比较
- 历史材料到当前实现的提炼/桥接
- 仅供当前讨论使用的内部工作笔记

这些文件目前散落在仓库根目录，例如 `temp.md`、`rainbird_compare.md`、`symir_blueprint_extraction.md`。  
它们已有现实价值，也已被 active blueprint 引用，但因为没有明确目录、角色和使用边界，容易造成入口混乱、路径漂移和职责混淆。

## 2. Goals

- 为“参考/提炼材料”建立正式文档角色与目录落点
- 把现有散落文件迁入新结构并修正引用
- 明确这类文档与 blueprint、module docs、history docs 的边界
- 给后续新增 reference 文档提供最小模板与索引入口

## 3. Non-goals

- 不把 reference 文档升级成当前实现真相
- 不把 reference 文档纳入 active/archive blueprint 状态机
- 不重写 reference 文档的主体内容
- 不整理所有历史材料，只处理当前已有且正在使用的代表性文件

## 4. Current Context

- [docs/README.md](/Users/zhenzhili/hnsm-backend/docs/README.md) 当前只收口原则、蓝图、模块 docs、legacy history 和 session handoff。
- [docs/blueprints/README.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/README.md) 当前没有给 reference 文档单独留位。
- `temp.md`、`rainbird_compare.md`、`symir_blueprint_extraction.md` 目前位于仓库根目录。
- [2026-03-15_overall-system-blueprint.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-03-15_overall-system-blueprint.md) 已引用 `symir_blueprint_extraction.md`。
- [2026-03-17_runtime-traceability-explainability-blueprint.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-03-17_runtime-traceability-explainability-blueprint.md) 和其 audit 已引用 `temp.md`。

## 5. Proposed Shape

- 新增 `docs/references/` 作为正式文档角色：
  - `external/`: 外部标准、竞品、产品或论文比较
  - `bridges/`: 历史内部材料到当前系统的提炼/桥接
  - `working/`: 仅供当前讨论使用的工作笔记或未定稿参考材料
  - `templates/`: 这类文档的最小模板
- reference 文档允许被 blueprint 在 `Related Docs`、`Current Context` 或正文中引用。
- reference 文档不承担当前实现真相；实现语义最终仍要回写到 module docs 或稳定原则文档。
- stable reference 入口进入 `docs/README.md`；`working/` 只由 `docs/references/README.md` 约束，不进入主索引逐项列出。
- 现有三份文件迁移到新目录，并在必要处补充角色说明与元信息头。

## 6. Boundaries And Invariants

- `src/factpy_kernel/*/docs/` 仍是实现真相。
- `docs/blueprints/{active,archive}/` 仍只放 blueprint 与 audit。
- `docs/blueprint_history/` 仍只放历史蓝图和遗留历史材料。
- reference 文档可作为输入材料或 rationale，但不能单独替代 blueprint 决策、验收标准或模块文档。
- `working/` 下的材料必须显式标明其非权威性质。

## 7. Acceptance

- [x] `docs/references/README.md` 已定义 reference 文档角色、边界和目录结构
- [x] 仓库级 workflow 规则已提到 `docs/references/`
- [x] 三份根目录文档已迁移到新结构
- [x] 现有 blueprint 链接已修正到新路径
- [x] `docs/README.md` 已新增 durable docs 入口

## 8. Implementation Plan

1. 新建本任务 blueprint 与 audit，冻结 reference 文档的角色、目录和迁移范围。
2. 新增 `docs/references/README.md` 与最小模板，形成后续可复用入口。
3. 迁移现有三份文档到 `docs/references/` 下的合适子目录，并补充最小元信息头。
4. 更新 `AGENTS.md`、`docs/README.md`、`docs/blueprints/README.md` 和现有 blueprint 引用。
5. 完成结果记录后归档本任务 blueprint。

## 9. Docs To Update

- `AGENTS.md`
- `docs/README.md`
- `docs/blueprints/README.md`
- `docs/references/README.md`
- `docs/references/templates/reference_note.md`
- `docs/blueprints/active/2026-03-15_overall-system-blueprint.md`
- `docs/blueprints/active/2026-03-17_runtime-traceability-explainability-blueprint.md`
- `docs/blueprints/active/2026-03-17_runtime-traceability-explainability-blueprint.audit.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 已新增 `docs/references/` 目录与 `external/`、`bridges/`、`working/`、`templates/` 子目录。
  - 已新增 `docs/references/README.md` 和最小模板，并把 reference 文档的边界写入 `AGENTS.md`、`docs/README.md`、`docs/blueprints/README.md`。
  - 已将三份根目录文档迁移为：
    - `docs/references/working/cross-domain-compliance-framing.md`
    - `docs/references/external/rainbird-evidence-chain-compare.md`
    - `docs/references/bridges/symir-blueprint-extraction.md`
  - 已修正 active blueprint 中对旧路径的引用。
- 与 blueprint 不同的地方：
  - 保留了 `working/` 条目在 `docs/references/README.md` 中的显式入口，便于当前讨论继续引用。
- 为什么会有这些调整：
  - `cross-domain-compliance-framing.md` 仍被 active blueprint 使用；虽然它不是 durable truth，但当前仍有现实使用价值，因此保留一个受控入口比彻底隐藏更稳妥。
- 归档说明：
  - 本任务已完成 reference 文档角色建模、迁移和索引收口，作为 workflow 扩展样例直接归档。
