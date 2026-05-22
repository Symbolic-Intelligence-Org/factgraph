# Task Blueprint: Ontology Feasibility Analysis

- Status: draft
- Created: 2026-03-31
- Last Updated: 2026-03-31
- Related Modules:
  - `src/factpy_kernel/core`
  - `src/factpy_kernel/authoring`
  - `src/factpy_kernel/adapters`
  - `src/factpy_kernel/sdk`
  - `src/factpy_kernel/service`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-22_architectural-decisions-v2.md](./2026-03-22_architectural-decisions-v2.md)
- Audit Log:
  - [2026-03-31_ontology-feasibility-analysis.audit.md](./2026-03-31_ontology-feasibility-analysis.audit.md)

## 1. Problem

团队计划引入本体论作为业务逻辑表达与执行的重要载体，但当前项目已经有 schema、rule、derivation、多引擎 evaluate 与 audit pipeline。需要先判断现有代码是否具备承接本体建模、规则编译、推理执行与审计交付的基础能力，以及缺口主要位于哪里。

## 2. Goals

- 梳理当前代码中与本体建模、语义约束、规则推理、解释链路有关的关键模块与边界。
- 评估“用本体承载业务逻辑”在现有架构上的可行性、适配方式与主要风险。
- 给出分阶段落地建议，并明确哪些点可以复用现有能力，哪些点需要新增适配层或协议。

## 3. Non-goals

- 不在本轮实现 ontology runtime、OWL/RDF importer 或新的核心推理后端。
- 不修改 core 语义、authoring 协议或 service API。
- 不把外部 ontology 标准直接固化为当前实现真相。

## 4. Current Context

- 当前实现入口：`core` 提供 schema / store / rule / derivation / evaluate 语义内核，`authoring` 负责 DSL 与编译，`adapters` 负责 ProbLog/PyReason 等后端接入。
- 当前已知约束：项目是 auditable reasoning framework，不是单一 reasoning engine；新增引擎应尽量复用统一 schema、annotation 与 audit 出口。
- 当前相关历史蓝图：
  - `docs/blueprints/active/2026-03-22_architectural-decisions-v2.md`
  - `docs/blueprints/archive/2026-03-27_multi-engine-semantic-delivery.md`
  - `docs/blueprints/archive/2026-03-16_temporal-hybrid-reasoning-blueprint.md`

## 5. Proposed Shape

本轮只做调研与可行性分析，不改核心实现。输出应围绕：

- ontology 与现有 `schema_ir` / predicate / annotation / rule DSL 的映射关系；
- ontology 作为“建模层”“编译源”“运行时真相”三种接入方式的优缺点；
- 当前多引擎架构是否适合承接 description-logic / graph-rule / rule-based hybrid 的后续扩展；
- 哪些结论属于短期可落地方案，哪些需要新蓝图后再推进。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 不改核心代码行为。
  - 结论必须基于当前代码与模块文档，不以历史设想替代现状。
  - 若引用历史蓝图，只作为 rationale，不把历史设计误写为已落地能力。
- 明确不做的内容：
  - 不实现本体引擎。
  - 不引入新的 shared runtime semantics。
- 兼容性约束：
  - 分析建议应尽量遵守既有 multi-engine、annotation store、audit pipeline 的架构方向。

## 7. Acceptance

- [ ] 已完成与 ontology 可行性直接相关的代码/文档调研
- [ ] 已明确当前可复用能力、关键缺口与主要风险
- [ ] 已给出建议接入形态与阶段化路径
- [ ] 没有越过 blueprint 明示的边界

## 8. Implementation Plan

1. 阅读核心架构文档与实现入口，确认 schema、rule、annotation、engine adapter 的当前真相。
2. 并行调查 authoring、runtime、adapter、service/audit 对“语义层扩展”的可承接能力。
3. 跑针对性的测试或静态检查，验证关键假设。
4. 汇总为可行性结论、风险矩阵与推荐落地路径。

## 9. Docs To Update

- 无。本轮仅新增调研蓝图与 audit。

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
