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
| `meander-factgraph-unified-design-review-candidate-v0-1-1.zh.md` | active narrow lineage revision (2026-08-10 working) | Option 1 text-convergence successor to the byte-frozen v0.1 candidate; preserves architecture `REVISE`, product authorization `STOP-except-discovery`, and all 16 `NEEDS_DECISION`; candidate/non-authoritative, with no formal supersession or product/experiment/implementation authorization. |
| `explanation-completion-roadmap.zh.md` | active strategic synthesis (2026-05-28 draft) | User-facing explainability completion stack inheriting evidence-tree §14 deferred items (D1/D5/D6/D7/D11/D15/D18/D20). Also carries §10/§11/§12 legacy backlog from 6 superseded design-points (RuleExpr v1 / Database-View / Post-T5 roadmap residuals). |
| `identity-mechanism-redesign.zh.md` | active design exploration (2026-05-29 intake) | Identity 机制重设计:Form I schema(Identity/Field + `_DataMember`)+ 3-layer API(entities/fields/assertions)+ AssertionView 统一 + INV-7a/b/c(Identity-as-Claim mirrored anchor)+ Q1 idref_v1 typed content-derived hash locked. Stage 1 audit pending. |
| `ledger-schema-specification.zh.md` | active design exploration (2026-05-29 intake) | Claim-first 3-table ledger schema(claims / claim_meta / ledger_meta)+ INV-1..INV-15 + 7-条数据精简 migration + INV-7c strategy C 实施同步(Identity pred_id set,拒 claim_meta tag). |
| `append-only-ledger-evaluation.zh.md` | active design exploration (2026-05-29 intake) | Append-only 范式 10 维度评估 + future gap 识别(GDPR / bitemporal / compaction);G1 措辞需后续按 identity §14.2 更新。 |
| `factgraph-storage-architecture-evolution.zh.md` | active strategic synthesis (2026-06-02 draft) | 存储架构演化路线:lifecycle 收敛(阶段 A,commit_assertions 统一)→ ledger 读路径迁 SQL(B)→ eval lazy materialize(C)→ eager mode 废弃(D)。挖出 5 个相互纠缠的事实(workspace 双格式 / 内存 cache / attach 半拒绝 / entities.create-delete 漏洞 / 命名错位),Q-SAE-1..6 待 decision。 |
| `schema-mutation-additive-only.zh.md` | active design-space record (2026-06-02 draft) | `fg.schema.*` 当前 additive-only 契约 + 7 类拒绝 + workspace digest / no-backfill / identity 锁定的根因;destructive surface(`delete` / `update` / `deprecate` / `migrate`)+ 4 路径选项(A-D)未来空间。 |
| `fields-iterable-value-batch.zh.md` | active design-space record (2026-06-02 draft) | `fg.fields.set / add / retract` 当前只接受单标量 value,iterable / list 在 SDK 边界 coerce 层被拒;workaround(多次调用 / `fg.batch` / `EntityEditor`);未来 surface 待定项(返回值、原子性、与 single-cardinality 的边界、与 `fg.batch` 的冗余)。 |
| `rule-namespace-rulespec-redesign.zh.md` | active design-space record (2026-06-02 draft, 2026-06-03 extended ×3) | application `Rule` 占用 user-facing "Rule" 命名导致 SDK 必须用 `build_application_rule(...)`;违反 codebase 已有 `SemanticsProfile` ↔ `ProbLogSemantics` 命名模式;提议路径 A — 重命名 application `Rule` → `RuleSpec`, SDK `Rule` 作为 user-facing shadow class with `.build()` / `.from_atoms()` / `__new__` dispatch;路径 B 候选 wrapper class;路径 C 仅重命名 factory。**2026-06-03 扩展 (1)**:加入 RuleExpr OR `branch_id` 匿名化 ergonomic gap(§3.4 / §4.5)—— 合成 `c{idx}` 而非派生 Rule.id / occurrence alias,导致 `case_probabilities` 顺序敏感的 silent fail。**2026-06-03 扩展 (2)**:加入 `Claim` cross-layer 同名占用 ergonomic gap(§3.5 / §4.6)—— ledger `Claim`(`asrt_id`/`pred_id`/`e_ref`/`rest_terms`)和 application protocol `Claim`(`kind`/`name`/`arguments`/`repr`/`digest`)同名不同字段,SDK `from factgraph.sdk import Claim` re-export 的是 protocol 那个;提议重命名 application protocol Claim 为 `ResultClaim`。**2026-06-03 扩展 (3)**:加入 `rule.id` 强制为 ledger predicate id ergonomic gap(§3.6 / §4.7)—— shipped 拒绝 `rule.id="find_us_users"` 这种 free-form rule 名字,只接受 `"user:region"` 形态,导致 user 无法语义化命名 rule;提议引入显式 `head_pred_id` 字段或等价机制让 `rule.id` 自由。**§3.6 / §4.7 superseded** by `evaluate-result-flatten-and-query-style.zh.md` §3.8 + Slice δ(2026-06-03):后者选 "head.id 自由 + arity check opt-in" 路径而非 `head_pred_id` 字段,作为 query-style 范式整体的一部分。 |
| `entity-exists-claim-emission-gap.zh.md` | active design-space record (2026-06-03 draft) | `fg.entities.create` 不 emit `<EntityType>:exists` claim,但 `build_application_rule(when=[Entity(var).field == v])` lowering 会 auto-prepend `PredAtom("Entity:exists", [v])`;canonical 用户面写法 evaluate 出 0 row 且无错误信息;`data_model.md §1.1` 描述与 shipped 不符;4 个候选方向(A. emit / B. 移除 auto-prepend / C. native implicit derive / D. 显式标注),倾向 A。 |
| `evaluate-result-flatten-and-query-style.zh.md` | active design-space record (2026-06-03 draft, **target form locked, ready for ADR**) | EvaluateResult / EvaluateRow / Claim / EvidenceRef 整体扁平化 + `rule.id ↔ ledger predicate id` 解耦(Datalog → query 范式)+ provenance digest 折叠为 `ResultFingerprint` sub-object + `row.repr` 走 desc 渲染。实证 audit:Claim 5 字段里 3 字段冗余(name/arguments/kind);EvidenceRef 5 字段里 4 字段是 D17 invariant 镜像;EvaluateResult 7 个 digest/id 字段无独立逻辑消费者,只用作 metadata bundle。目标:user-facing surface 从 25 字段减到 ~13。**supersede** `rule-namespace-rulespec-redesign §3.6 / §4.7`(rule.id ↔ pred_id 解耦那一支)。6 实施切片(α-ζ)按 risk 排序,可独立上线。 |

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
