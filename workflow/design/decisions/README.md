# Decisions(ADR 决策)

ADR 风格的离散决策记录。每个 decision 锁定一个 load-bearing 设计问题,在下游 blueprint / 实现工作开始之前。

## ADR 4-state 生命周期(per Q2 §4.5)

| Status | 含义 | 目录 |
|---|---|---|
| `proposed` | 审议中,尚非约束 | `active/` |
| `adopted` | **当前约束**;下游必须遵守 | `active/` |
| `superseded` | 被新 decision 替代 | `archive/` |
| `withdrawn` | 撤回;需写明理由 | `archive/` |

**`adopted` decisions 留在 `active/`**,因为它们仍是**当前约束**。只有 `superseded` / `withdrawn` 进 `archive/`。这与 `workflow/blueprints/` 不同 — blueprint `implemented` 后立即归档(blueprint 是历史 rationale;adopted decision 是当前规则)。

## 当前 adopted decisions 索引

| Date | Decision | Summary |
|---|---|---|
| 2026-05-25 | D16 T5 Tranche Boundary | T5 Core / Semantics boundary and D17-D26 ladder. |
| 2026-05-25 | D17 Result / Row DTO Foundation | `EvaluateResult` / `EvaluateRow` / `Claim` / `EvidenceRef` ownership and CandidateSet mapping. |
| 2026-05-25 | D18 Return-Shape Transition | Public `evaluate(...) -> EvaluateResult` hard-cut strategy. |
| 2026-05-25 | D19 Digest Source-of-Truth | Result, row, claim, evidence, and audit digest sources. |
| 2026-05-25 | D20 Explanation Envelope | `Explanation`, `row.explain()`, manual explain, and EvidenceGraph integration boundary. |
| 2026-05-25 | D21 Row Close / Closed-Head Gate | `EvaluateRow.close()` and closed-head validation for manual explain. |
| 2026-05-25 | D22 Why-Not Disposition | Failed `Explanation` as v1 why-not envelope and legacy why-not quarantine. |
| 2026-05-25 | D23 Legacy SDK Hard-Cut Plan | Legacy public shell removal, service/OpenAPI migration, and docs hard-cut ordering. |
| 2026-05-25 | D24 Final SDK Rule Flip | `factgraph.sdk.Rule` final naming and legacy DSL displacement. |
| 2026-05-25 | D25 Evaluate / Explain Semantics Consistency | Semantics digest consistency across evaluate, row explain, and manual explain. |
| 2026-05-25 | D26 Semantics Commitments Scope | Semantics-lite boundary and adapter-touching C74/C76/C77/C78 deferral. |

## 相关

- [`workflow/design/README.md`](../README.md) — 完整状态机、允许转换、跨边界 mv 约定
- `workflow/templates/design/decision.md` — 新 decision 的权威起点
- [`workflow/CADENCE.md`](../../CADENCE.md) Stage 2 — audit → Q → synthesis → blueprint 流程中的 Q-resolution 阶段
