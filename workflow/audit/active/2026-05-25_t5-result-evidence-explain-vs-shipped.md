# Stage 1 Audit: T5 Result + Evidence + Explain vs Shipped Runtime

Status: draft
Date: 2026-05-25
Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
Base commit: `4eeb18b9` (`chore(memory): consolidate T4.3 archive and close T4 cycle`)
Class prediction: L cluster; requires Stage 2 decision docs, Stage 3 synthesis, and implementation slices.
Reviewer handoff: Codex drafts; Claude reviews.

## 1. Purpose

T4 is closed: Stage 1-3 plus T4.1, T4.2, and T4.3 are archived, memory-consolidated, and pushed through the T4 gate. The current memory state marks T4 complete and next-stage selection pending (`workflow/memory/current.md:3-9`, `workflow/memory/current.md:43-45`). Human selected the Hybrid path: push gate first, then T5.

This audit compares the T5 parent design commitments against shipped runtime and SDK surfaces before any T5 decision or implementation work. The audit focuses on `.eval` result shape, row-centric explanation, why-not disposition, legacy hard-cut blast radius, evidence publicization, semantics wrappers, and the T1.3 final `Rule` naming flip.

Given the initial 14-question surface after this audit, Stage 2 likely needs roughly 7-10 decision docs before Stage 3 synthesis chooses a final implementation ladder.

## 2. Audit Scope

In scope:

- Parent §5.8 `.eval` namespace, `EvaluateResult`, `EvaluateRow`, `Claim`, `EvidenceRef`, `Explanation`, `row.close()`, and pending `fg.eval.why_not(...)` (`workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md:924-1285`).
- Parent commitment rows C61-C78, including semantics wrapper commitments and temporal / uncertainty projection commitments (`workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md:1586-1603`).
- Track plan T5 sub-slices T5.1-T5.10 and affected shipped surfaces (`workflow/design/design-points/archive/rule-expression-and-proof-track-plan.zh.md:233-264`).
- Shipped SDK `eval`, `check`, `diagnose`, `why_not`, `run`, `accept`, and RuleExpr evaluate paths.
- Shipped application protocol DTOs for CandidateSet, Check, Diagnose, WhyNot, EvidenceGraph, SupportArtifact, and T4.3 closed-head inspect.
- T1.3 final SDK `Rule` flip blast radius: current public `Rule` and `LegacyRule` exports remain in SDK namespace.

Out of scope for this Stage 1 audit:

- No code implementation, API deletion, migration shim, or docs rewrite.
- No reopening T4.1/T4.2/T4.3 behavior.
- No adapter production edits.
- No push.
- No final decision on whether T5 includes all semantics commitments C73-C78 or splits part of them into a later cycle.
- No §6 task split (`match` / `evaluate` / `prove`) or §9 RuleExpr x evidence joins; both are explicitly outside the T5 track plan (`workflow/design/design-points/archive/rule-expression-and-proof-track-plan.zh.md:263-266`).
  Parent §6 proposes a future three-way decomposition of evaluation behavior; parent §9 proposes a join surface between RuleExpr and evidence. This audit treats both as deferred context, not T5 implementation scope.

## 3. Canonical Sources Read

| Source | Lines | Audit use |
|---|---:|---|
| Current memory | `workflow/memory/current.md:3-9`, `workflow/memory/current.md:43-45` | T4 closed state, sacred branch, dirty set, T4.3 final archive anchor. |
| Track plan T5 row | `workflow/design/design-points/archive/rule-expression-and-proof-track-plan.zh.md:233-264` | T5 scope, sub-slice ladder, affected shipped surfaces, explicit not-in-T5 items. |
| Parent §5.8 | `workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md:924-1285` | `.eval` namespace, result row DTOs, explain, why-not pending, row digests. |
| Parent commitments | `workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md:1586-1603` | C61-C78 commitment table. |
| Parent deferred table | `workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md:1605-1612` | Why-not pending, run deletion trigger, what-if refactor, projection rename deferral. |

## 4. Shipped Source Read

| Source | Lines | Shipped state |
|---|---:|---|
| SDK exports | `src/factgraph/sdk/__init__.py:28-56`, `src/factgraph/sdk/__init__.py:88-108` | SDK exports `Rule`, `LegacyRule`, `Inference`, `ApplicationRule`, `RuleExprInspect`; no `EvaluateResult`, `EvaluateRow`, `Claim`, `EvidenceRef`, `Explanation`, or `DetachedRowError`. |
| SDK eval namespace | `src/factgraph/sdk/store.py:420-475` | `fg.eval` currently exposes `run`, `evaluate`, `inspect_semantics`, `accept`, and `accept_many`. |
| SDK check / diagnose / why_not | `src/factgraph/sdk/store.py:1178-1278` | `check`, `diagnose`, and `why_not` remain direct SDK methods returning application DTOs. They still take `engine` and `registry`. |
| SDK evaluate dispatch | `src/factgraph/sdk/store.py:2211-2384` | `evaluate(...) -> list[CandidateSet]`, still accepts `registry` and `engine_options`, and RuleExpr evaluate returns `list[CandidateSet]`. |
| CandidateSet | `src/factgraph/core/derivation/candidates.py:13-70` | Shipped candidate DTO is accept-oriented and row-like only by convention; no row resolver, claim, evidence ref, or result envelope. |
| Check DTOs | `src/factgraph/application/protocol/derivation_check.py:62-160` | `CheckResult` has four-state status and optional `EvidenceEnvelope`; this is not the proposed `Explanation` envelope. |
| Diagnose DTOs | `src/factgraph/application/protocol/derivation_diagnose.py:1-21`, `src/factgraph/application/protocol/derivation_diagnose.py:136-165` | Diagnose is a sibling capability, does not carry `EvidenceEnvelope`, and exposes `DiagnoseResult`. |
| WhyNot DTOs | `src/factgraph/application/protocol/derivation_why_not.py:1-6`, `src/factgraph/application/protocol/derivation_why_not.py:24-34`, `src/factgraph/application/protocol/derivation_why_not.py:163-332` | Why-not owns independent request/result row DTOs and is not yet integrated into `.eval.explain`. |
| Support carriers | `src/factgraph/core/store/_support.py:9-20`, `src/factgraph/core/store/_support.py:96-162` | SupportArtifact / ProvenanceEnvelope exist as engine support carriers; they are not public `EvidenceRef` / `Explanation`. |
| Evidence graph | `src/factgraph/audit/evidence_graph.py:24-77` | `EvidenceGraph` exists in audit layer with nodes, edges, support_kind, and metadata. Parent wants this as `Explanation.evidence`. |
| Closed-head inspect | `src/factgraph/application/protocol/rule_expr_inspect.py:89-199` | T4.3 added append-only `RuleExprInspect.is_closed` and `unbound_ports`, plus private closed-head helper. |
| Legacy SDK Rule / Inference | `src/factgraph/sdk/dsl/rule.py:53-118`, `src/factgraph/sdk/dsl/rule.py:119-170` | SDK `Rule` is still the legacy query object; SDK `Inference` remains the derivation authoring object. |

## 5. Findings

### F1 — `fg.eval.evaluate` success shape still returns `list[CandidateSet]`

Parent C62 requires `fg.eval.evaluate(expr, head=Rule, engine=..., semantics=...)` to return `EvaluateResult` (`workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md:1587`). Shipped `SDKStore.evaluate` returns `list[CandidateSet]` (`src/factgraph/sdk/store.py:2211-2211`) and the RuleExpr path preserves that shape through `evaluate_derivation_plans(...)` (`src/factgraph/sdk/store.py:2324-2384`).

This is the central T5 gap: T4 intentionally preserved `list[CandidateSet]` to avoid public result-shape churn; T5 owns the breaking result surface.

### F2 — `CandidateSet` is not an `EvaluateRow`

`CandidateSet` carries derivation, target, payload, support digest/kind, candidate id/key, state, and confidence (`src/factgraph/core/derivation/candidates.py:13-30`). It does not carry `claim`, `evidence_ref`, `_result_resolver`, live/detached behavior, row-level `explain()`, row-level `close()`, or parent row digests (`workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md:1020-1081`).

T5 must decide whether `CandidateSet` remains an internal adapter/runtime artifact, a compatibility view, or a deleted public surface.

The full proposed `EvaluateRow` field set is `row_id`, `bindings`, `claim`, `raw_kind`, `bound`, `evidence_ref`, and non-data `_result_resolver`; `CandidateSet` has no exact counterpart for several of those fields.

### F3 — `.eval` namespace is partly present but conflicts with parent delete/deprecate plan

Shipped `_SDKEvalManager` still exposes `run`, `evaluate`, `inspect_semantics`, `accept`, and `accept_many` (`src/factgraph/sdk/store.py:420-475`). Parent §5.8 deletes `fg.eval.accept` / `accept_many`, deletes `engine_options=` and `registry=` from public evaluate, and freezes `fg.eval.run` for later deletion (`workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md:940-957`).

This is a subtractive API zone and should not be bundled into DTO foundation without an explicit hard-cut decision.

### F4 — `check` / `diagnose` are shipped as sibling SDK shells, not `fg.eval.explain`

Parent C61 folds `fg.check` and `fg.diagnose` into `fg.eval.explain` (`workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md:1586`). Shipped SDK methods `check(...)` and `diagnose(...)` remain direct shell entry points returning `CheckResult` and `DiagnoseResult` respectively (`src/factgraph/sdk/store.py:1178-1241`). Application protocol also deliberately keeps Diagnose decoupled from Check (`src/factgraph/application/protocol/derivation_diagnose.py:1-21`).

T5 must map those existing shells into `Explanation` or explicitly retire them.

### F5 — Why-not is already shipped, while parent marks `fg.eval.why_not` pending

Parent §5.8.4 says `fg.eval.why_not(...)` is pending and may be unnecessary after `Explanation.status="failed"` covers why-not needs (`workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md:1265-1278`). Shipped SDK has `why_not(...)` returning `WhyNotUniverseResult` directly (`src/factgraph/sdk/store.py:1243-1278`), and the application protocol owns independent WhyNot row DTOs (`src/factgraph/application/protocol/derivation_why_not.py:1-6`, `src/factgraph/application/protocol/derivation_why_not.py:294-332`).

T5 cannot treat why-not as greenfield. It must decide migrate, wrap, keep, or delete.

### F6 — Evidence substrates exist but are not a public `Explanation`

`CheckResult` has `EvidenceEnvelope` wrapping `SupportArtifact | ProvenanceEnvelope` (`src/factgraph/application/protocol/derivation_check.py:62-81`). Audit `EvidenceGraph` exists and includes nodes, edges, support kind, and metadata (`src/factgraph/audit/evidence_graph.py:24-77`). Parent C67 wants `Explanation.evidence: EvidenceGraph | None` and unified 4-state status (`workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md:1176-1220`, `workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md:1592`).

The substrate is promising, but there is no shipped public envelope that carries claim, result lineage, row id, evidence ref id, failure_class, checked_scope, and suggested_next_steps.

### F7 — T4.3 closed-head inspect is shipped, but no must-be-closed caller exists

T4.3 delivered `RuleExprInspect.is_closed` and `unbound_ports` append-only fields (`src/factgraph/application/protocol/rule_expr_inspect.py:89-125`) plus private closed-head helper (`src/factgraph/application/protocol/rule_expr_inspect.py:163-199`). Parent row explain / manual replay requires closed-head behavior through `row.close()` and `fg.eval.explain(expr, head=closed_head)` (`workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md:1119-1147`).

T5 can reuse the closed-head helper, but T4.3 intentionally did not add `row.close()`, must-be-closed validation gates, or explain entry points.

### F8 — T1.3 final `Rule` flip remains unresolved and is coupled to T5 hard-cut

SDK exports both legacy `Rule` and `LegacyRule`, while application `Rule` is exported as `ApplicationRule` (`src/factgraph/sdk/__init__.py:38-56`, `src/factgraph/sdk/__init__.py:88-92`). Legacy SDK `Rule` remains a query object with `fg.eval.run(rule)` docs in its docstring (`src/factgraph/sdk/dsl/rule.py:53-118`). SDK `Inference` remains the derivation authoring object (`src/factgraph/sdk/dsl/rule.py:119-170`).

T5's new evaluate surface uses application `Rule` as the head. The final SDK naming flip should be audited and decided inside the T5 hard-cut plan, not as an unrelated cleanup.

Current namespace shape is four-way: `Rule` is the legacy SDK query class, `LegacyRule` is an alias to that same DSL class, `ApplicationRule` points at `factgraph.application.protocol.Rule`, and `Inference` remains a separate derivation authoring class. T1.3 final flip must decide which names survive and which names become transition aliases.

### F9 — Semantics wrappers are partially shipped; C73-C78 are larger than result DTOs

SDK exports `ProbLogSemantics` and `PyReasonSemantics` (`src/factgraph/sdk/__init__.py:25-27`, `src/factgraph/sdk/__init__.py:80-82`). Parent C73-C78 require per-rule params, atom-bound keys, uncertainty projection, temporal projection, iteration count, and ProbLog raw_kind/bound adapter consumption (`workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md:1598-1603`). Track plan T5.6-T5.8 treats these as substantial sub-slices, including an adapter-touching ProbLog slice (`workflow/design/design-points/archive/rule-expression-and-proof-track-plan.zh.md:248-250`).

Stage 2 should decide whether all semantics work remains in T5 or whether T5 splits result/evidence from semantics/adapter commitments.

### F10 — Public docs still describe the pre-T5 surface

The shipped docs still describe public evaluation as `list[CandidateSet]`, `fg.eval.accept`, and `fg.what_if.*` shells. This is expected because T4 preserved the public result shape and did not start T5. T5 must include a docs migration slice, but docs should follow decisions rather than lead them.

### F11 — Result / row digest metadata sources are not all present in one place

Parent `EvaluateResult` requires `result_id`, `run_id`, `expr_digest`, `rule_set_digest`, `view_snapshot_digest`, `semantics_digest`, `result_digest`, engine version, adapter version, and evaluated timestamp (`workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md:1083-1117`). Shipped `CandidateSet` has candidate and tuple digests (`src/factgraph/core/derivation/candidates.py:13-30`) but not the full result-session envelope.

T5 must identify authoritative sources for view snapshot digest, rule-set digest, engine/adapter version, semantics digest, and result digest before DTO implementation.

### F12 — T5 is an L-class cluster, not a single implementation slice

Track plan already predicts roughly ten T5 sub-slices (`workflow/design/design-points/archive/rule-expression-and-proof-track-plan.zh.md:239-252`). The shipped code confirms broad blast radius: SDK store, SDK shells, application protocol, application runtimes, service routes, docs, and tests (`workflow/design/design-points/archive/rule-expression-and-proof-track-plan.zh.md:256-261`).

The Stage 2 decision layer should be at least as explicit as T4 D11-D15 before implementation begins.

## 6. Commitment Triage

| Commitment | Parent intent | Shipped state | Triage |
|---|---|---|---|
| C61 | `.eval` absorbs explain; `fg.check` / `fg.diagnose` delete or merge; why_not pending. | `check`, `diagnose`, and `why_not` remain shipped direct SDK methods. | Decision required. |
| C62 | `fg.eval.evaluate(...)->EvaluateResult`; delete `engine_options=`, `registry=`, `accept`, `accept_many`. | `evaluate(...)->list[CandidateSet]`; accepts `registry` / `engine_options`; `accept*` shipped. | Core conflict. |
| C63 | `fg.eval.run` frozen, later deletion after read.match. | `run` shipped in eval namespace and legacy `Rule` docstring. | Hard-cut timing decision. |
| C64 | `EvaluateRow` with claim/evidence_ref/live resolver. | No shipped `EvaluateRow`; `CandidateSet` is different. | New DTO decision. |
| C65 | `EvaluateResult` session envelope. | No shipped envelope; only lists of `CandidateSet`. | New DTO decision. |
| C66 | `row.explain()`, manual `fg.eval.explain`, `row.close()`. | No explain row API; T4.3 closed-head inspect only. | New behavior decision. |
| C67 | `Explanation` envelope with `EvidenceGraph`. | Check/Diagnose/WhyNot DTOs exist separately; EvidenceGraph exists in audit layer. | Merge / wrapper decision. |
| C68 | Row/result digest rules are audit metadata. | Candidate digests exist, but result/session digests do not. | Source-of-truth decision. |
| C69 | Evaluate/explain semantics consistency; different semantics explicit, no warn. | Semantics wrapper dispatch exists for evaluate; no explain API. | Decision required. |
| C70 | `fg.eval.why_not` pending. | Raw SDK `why_not` shipped. | User-scenario decision. |
| C71 | `fg.what_if.*` shells deferred after explain. | Docs and shells still exist. | Later hard-cut decision. |
| C72 | Closed-head inspect utility. | Shipped in T4.3. | Already aligned; T5 may reuse. |
| C73 | Per-rule semantics params map. | Partial semantics wrappers exist; final shape not audited here. | Stage 2 decision. |
| C74 | PyReason rule params + atom bounds. | Partial PyReason semantics shipped; exact commitment pending. | Stage 2 decision. |
| C75 | ProbLog/PyReason wrapper symmetry and raw_kind/bound model. | Partial wrappers shipped. | Stage 2 decision. |
| C76 | ProbLog uncertainty projection and adapter raw_kind/bound consumption. | Adapter consumption not part of T4; track plan calls out adapter slice. | Likely separate slice. |
| C77 | Temporal projection modes. | Not part of T4. | Stage 2 decision. |
| C78 | PyReason `iteration_count`; no ProbLog analog. | Needs audit against shipped semantics implementation. | Stage 2 decision. |

## 7. Stage 2 Questions

| Q | Question | Driver |
|---|---|---|
| Q1 | What is the exact T5 tranche boundary: result/explain only, or result/explain plus semantics C73-C78? | F9, F12, track plan T5.1-T5.10. |
| Q2 | Where do `EvaluateResult`, `EvaluateRow`, `Claim`, `EvidenceRef`, `Explanation`, and `DetachedRowError` live and export from? | F1, F2, SDK export gap. |
| Q3 | Is `fg.eval.evaluate` a hard-cut return-shape replacement or an additive parallel surface during T5 implementation? | C62, F1, docs/test blast radius. |
| Q4 | What is the mapping from `CandidateSet` / adapter outputs to `EvaluateRow.claim`, `raw_kind`, `bound`, and `EvidenceRef`? | F2, F6, C64-C65. |
| Q5 | What are authoritative sources for `result_id`, `row_id`, `expr_digest`, `rule_set_digest`, `view_snapshot_digest`, `semantics_digest`, `engine_version`, and `adapter_version`? | F11, C68. |
| Q6 | How does `row.explain()` resolve evidence, and what data is copied into `EvidenceGraph.metadata` for durable replay? | F6, C66-C67. |
| Q7 | How should `row.close()` reuse T4.3 closed-head helpers without reopening T4.3 inspect semantics? | F7, C66, C72. |
| Q8 | How should `fg.eval.explain(expr, head=closed_head)` combine Check, Diagnose, EvidenceGraph, and failure_class semantics? | F4, F6, C67. |
| Q9 | Does shipped `why_not` migrate to `.eval.why_not`, fold into `Explanation.status="failed"`, remain temporarily, or get deleted? | F5, C70, parent pending. |
| Q10 | What is the hard-cut plan for `accept`, `accept_many`, `run`, `check`, `diagnose`, `what_if.*`, `engine_options=`, and `registry=`? | F3, F4, C61-C63, C71. |
| Q11 | How does the T1.3 final SDK `Rule` flip happen without confusing legacy `Rule`, `LegacyRule`, `Inference`, and application `Rule` imports? | F8. |
| Q12 | Which semantics wrapper commitments belong in T5 Stage 2, and which become a later track? | F9, C73-C78. |
| Q13 | Which application / service routes depend on old Check/Diagnose/WhyNot shapes and must be included in blast-radius tests? | Track plan affected surface, F12. |
| Q14 | How do `.eval.evaluate(..., semantics=...)` and `.eval.explain(..., semantics=...)` enforce semantics consistency between row-time evaluate and replay-time explain? If callers use different `semantics=` for the same row or manual replay, should the system warn, raise, or remain silent? | C69, F9. |

## 8. Reviewer Focus

1. Verify there is no hidden shipped `EvaluateResult` / `EvaluateRow` / `Explanation` production implementation.
2. Spot-check whether `CandidateSet` can realistically be mapped to Wave 1 `EvaluateRow` without losing support / candidate semantics.
3. Check whether `why_not` is accurately characterized as shipped raw SDK surface plus parent-pending future surface.
4. Verify T4.3 closed-head inspect is treated as reusable substrate, not as already implementing `row.close()` or explain gates.
5. Confirm T1.3 final SDK `Rule` flip is correctly pulled into T5 planning rather than forgotten.
6. Challenge whether C73-C78 should be in the same T5 decision cluster or split after result/explain.
7. Check if service-route blast radius needs stronger Stage 1 source reading before D-docs.

## 9. Acceptance Criteria

- [x] T4 complete / next-stage memory state read.
- [x] Parent §5.8 and C61-C78 read.
- [x] Track plan T5 row read.
- [x] SDK evaluate / eval namespace / check / diagnose / why_not source read.
- [x] CandidateSet, Check, Diagnose, WhyNot, SupportArtifact, EvidenceGraph, and T4.3 closed-head inspect source read.
- [x] Findings identify result-shape, explain, why-not, hard-cut, evidence, semantics, and Rule flip gaps.
- [x] Stage 2 questions prepared for decision-doc drafting.
- [x] No code implementation, no public API mutation, no push, no sacred branch movement.
