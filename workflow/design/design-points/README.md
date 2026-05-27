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
| `rule-expression-and-proof-attempt.zh.md` | active parent essay | Rule / RuleExpr / evaluate / evidence / semantics parent design source. |
| `match-api-design.zh.md` | active implementation-backed design | `fg.read.match(...)` public API, connectivity, constraint, and witness-boundary design source; AND + OR runtime shipped, witness/cross-entity tuple output deferred. |
| `evidence-tree-rainbird-style-v1.zh.md` | active working skeleton | Evidence tree Phase B / rendering / deferred evidence registry source. |
| `database-view-fg-layered-architecture.zh.md` | active minimum implementable blueprint | Database / durable view / attach lifecycle design source. |
| `rule-expression-and-proof-track-plan.zh.md` | T1-T5 complete; retained as historical decomposition index | Superseded for future scheduling by `post-t5-completion-roadmap.zh.md`, but kept active to avoid broad historical-reference churn. |
| `post-t5-completion-roadmap.zh.md` | working planning artifact | Non-authoritative T6-T12 scheduling reference. |

完整状态机 + 权威语义见 [`workflow/design/README.md`](../README.md)。模板:`workflow/templates/design/design-point.md`。
