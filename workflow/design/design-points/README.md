# Design-Points(概念性设计 essays)

概念性设计 essays。迭代;用户多步骤逐步完成;实质性但**不是当前行为**。

## 权威边界(per Q2 §4.4)

> 一个 design-point 是**候选设计 / 非权威参考**。它仅当被以下任一引用时才成为约束:
>
> - 一个 `workflow/design/decisions/` 中 adopted 的 decision,或
> - 一个 `workflow/blueprints/archive/` 中 implemented 的 blueprint,或
> - 当前模块 docs(`src/factgraph/*/docs/`),或
> - `workflow/foundations/architecture_principles.md`
>
> design-point **不能直接覆盖 shipped 行为**。实现必须通过下游消费链(decision → blueprint → impl)到达代码。

每个 essay 的 header 包含此声明的逐字 copy。

## 生命周期

`active/` — 还在迭代,跨越数周到数月,仍可能产生新问题 / decisions / blueprints。

`archive/` — **同时满足以下三条**时归档(per Q2 §4.3):

1. 该 design-point 提出的所有 load-bearing 问题都在 `workflow/design/decisions/` 中闭合(任一 closed ADR 状态:`adopted` / `superseded` / `withdrawn`)
2. 所有实现-eligible 内容已 ship(被 `implemented` blueprint 引用),或已被显式 defer / superseded
3. 没有 `active` 状态的 blueprint 仍把该 design-point 当作 live 设计依据

也可通过**被新 essay supersede** 归档(后继在 `Inputs` 引用前者,前者归档,即便上述三条未全部满足)。

## 当前 active design-points

| Design-point | Status | Role |
|---|---|---|
| `explanation-completion-roadmap.zh.md` | active strategic synthesis (2026-05-28 draft) | User-facing explainability completion stack inheriting evidence-tree §14 deferred items (D1/D5/D6/D7/D11/D15/D18/D20). Also carries §10/§11/§12 legacy backlog from 6 superseded design-points (RuleExpr v1 / Database-View / Post-T5 roadmap residuals). |
| `identity-mechanism-redesign.zh.md` | active design exploration (2026-05-29 intake) | Identity 机制重设计:Form I schema(Identity/Field + `_DataMember`)+ 3-layer API(entities/fields/assertions)+ AssertionView 统一 + INV-7a/b/c(Identity-as-Claim mirrored anchor)+ Q1 idref_v1 typed content-derived hash locked. Stage 1 audit pending. |
| `ledger-schema-specification.zh.md` | active design exploration (2026-05-29 intake) | Claim-first 3-table ledger schema(claims / claim_meta / ledger_meta)+ INV-1..INV-15 + 7-条数据精简 migration + INV-7c strategy C 实施同步(Identity pred_id set,拒 claim_meta tag). |
| `append-only-ledger-evaluation.zh.md` | active design exploration (2026-05-29 intake) | Append-only 范式 10 维度评估 + future gap 识别(GDPR / bitemporal / compaction);G1 措辞需后续按 identity §14.2 更新。 |

## 2026-05-29 archive batch

6 design-points 通过 supersede 规则 (per §"生命周期") 一次性 archive 到 `workflow/design/design-points/archive/` (commits 2026-05-29 早晨; session 起始 2026-05-28):

| 文件 | 主要 supersede 路径 |
|---|---|
| `rule-expression-and-proof-attempt.zh.md` | inherited as `explanation-completion-roadmap.zh.md` §10 legacy + Inputs 引用 |
| `match-api-design.zh.md` | D20 witness 收编 + AND+OR runtime shipped via module docs |
| `evidence-tree-rainbird-style-v1.zh.md` | §14 deferred 8 项 inherited via §0 Inputs + §4 Inheritance Map + Tier S/A/B 三档; §1-§13 Phase B shipped via module docs |
| `database-view-fg-layered-architecture.zh.md` | inherited as `explanation-completion-roadmap.zh.md` §11 legacy + Inputs 引用; A1-A20 shipped via module docs |
| `rule-expression-and-proof-track-plan.zh.md` | 自标 superseded by `post-t5-completion-roadmap.zh.md` (后者亦在本批 archive) |
| `post-t5-completion-roadmap.zh.md` | inherited as `explanation-completion-roadmap.zh.md` §12 legacy + Inputs 引用 |

### 2026-05-29 evening intake batch

1 design-point 通过 supersede 规则归档,作为 `identity-as-claim` 3-doc set intake 的伴随归档:

| 文件 | 主要 supersede 路径 |
|---|---|
| `identity-and-data-model-redesign.zh.md` | 拆分为 3 份继承 doc:`identity-mechanism-redesign.zh.md`(Identity 半边)+ `ledger-schema-specification.zh.md`(ledger schema 半边)+ `append-only-ledger-evaluation.zh.md`(append-only 范式评估)。归档版顶部含取代关系映射表。 |

完整状态机 + 权威语义见 [`workflow/design/README.md`](../README.md)。模板:`workflow/templates/design/design-point.md`。
