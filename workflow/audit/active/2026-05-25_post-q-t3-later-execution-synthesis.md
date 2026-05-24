# Synthesis: T3 Later Execution Post-Q Bucketing

- Status: complete
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: working triage document; informs but does not lock implementation. Final scope decisions live in implementing blueprints per CADENCE Stage 3.
- Inputs:
  - `workflow/audit/active/2026-05-25_t3-later-execution-vs-shipped.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d6-public-entrypoint-head-dependency.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d7-lowering-plan-shape.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d8-join-lowering-semantics.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d9-adapter-matrix.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d10-evaluation-result-evidence-boundary.md`
- Outputs / Downstream:
  - T3L.1-T3L.3 implementation blueprint ladder.
  - Track-plan synchronization patch for T3 later rows.
  - Per-slice preservation invariants and negative-action gates.
- Related:
  - `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md`
  - `workflow/blueprints/archive/2026-05-24_t3-1-base-ruleexpr-bool-guards.md`
  - `workflow/blueprints/archive/2026-05-24_t3-2-expression-scope-validation.md`
  - `workflow/blueprints/archive/2026-05-24_t3-3-joins-and-reach-rule.md`
  - `workflow/blueprints/archive/2026-05-24_t3-4-join-by-ports.md`
  - `workflow/blueprints/archive/2026-05-24_t3-5-ruleexpr-inspect.md`
  - `workflow/blueprints/archive/2026-05-24_t3-6-docs-and-examples.md`
- Source audit: `workflow/audit/active/2026-05-25_t3-later-execution-vs-shipped.md`
- Closed Q decisions:
  - D6 Public Entrypoint And Head Dependency
  - D7 RuleExpr Lowering Plan Shape
  - D8 Join Lowering Semantics
  - D9 Adapter Matrix And Rejection Policy
  - D10 Evaluation Result / Evidence Boundary
- Branch: `v0.2.0-t3-later-execution-audit-2026-05-25`

> Synthesis is required because the T3 later audit closed five decisions spanning blueprint-eligible implementation, cross-adapter support boundaries, error hierarchy, evidence/result deferral, and Stage 3 slice-split Q10.

## 1. Scope Of Synthesis

This synthesis re-buckets T3 later Stage 1 audit rows after D6-D10 review.

It does not implement RuleExpr execution and does not replace per-slice blueprints. It produces the implementation ladder and synchronization obligations for the T3 later execution tranche.

## 2. 5-Bucket Classification

### 2.1 Blueprint-Eligible

| Item | Destination | Reason |
|---|---|---|
| Public `fg.eval.evaluate(application_rule_or_rule_expr, head=...)` entrypoint | T3L.3 | D6 locks the public target, but Stage 3 delays public exposure until the internal lowering and adapter matrix are ready. |
| C35 single application `Rule` coercion into one-rule RuleExpr | T3L.1 internally, T3L.3 publicly | D6 locks dispatch-entry coercion before lowering; D7/D10 need the same shape for internal tests. |
| Minimal head subset with application Rule `head=` | T3L.1/T3L.3 | D6 locks required `head=` and rejects full T4 Head / closed-head behavior. |
| Private `RuleExprLoweringPlan` categories | T3L.1 | D7 locks canonical private lowering target and minimum sub-DTO categories. |
| Alias-local variable namespacing | T3L.1 | D7 locks namespacing before AND concatenation; D8 relies on it for join endpoint resolution. |
| AND cartesian-product / OR branch alternatives | T3L.1 | D7 locks branch model; D9 materializes it as branch-list bodies. |
| Explicit join equality atom materialization | T3L.1 | D8 locks `RuleJoinConstraint(op="eq")` to equality atoms and rejects variable unification. |
| Join materialization metadata | T3L.1 | D8 locks `RuleExprJoinMaterialization`; D10 requires it in the private trace sidecar. |
| Native engine RuleExpr execution | T3L.1 | D9 native matrix cell supports branch-list / eq / aggregates within shipped grammar. |
| Souffle + ProbLog RuleExpr execution parity | T3L.2 | D9 supports both within shipped adapter grammar, including existing aggregate behavior. |
| PyReason pred-only subset and non-pred preflight rejection | T3L.2 classifier, T3L.3 public error | D9 locks PyReason support to pred-only branches and `SDKStoreError` preflight for eq/aggregate/non-pred atoms. |
| Aggregate-in-RuleExpr preservation | T3L.1 native, T3L.2 adapter parity | D9 Q7a locks aggregate-local scope and empty-set guards. |
| Public adapter rejection diagnostics | T3L.3 | D9 locks `SDKStoreError` and four required message fields. |
| Public success result stays `list[CandidateSet]` | T3L.3 | D10 rejects new result wrappers and CandidateSet extension. |
| Private RuleExpr evaluation trace sidecar | T3L.1 design, T3L.3 candidate/support correlation | D10 locks minimum categories and lifetime/correlation invariants. |
| User-facing execution docs and examples | T3L.3 | Public behavior should be documented only after public dispatch + adapter matrix behavior are stable. |

### 2.2 Cross-Doc Blocked

| Item | Required synchronization | Timing |
|---|---|---|
| Track plan T3 later row | Replace "L or M TBD" placeholder with T3L.1-T3L.3 ladder and Stage 1-3 anchor | This synthesis commit. |
| D6-D10 reviewed status | Add §9 reviewed rows to each D-doc so Stage 3 cites reviewed decisions, not proposed-only records | This synthesis commit. |
| T5 EvaluateResult / WhyNot boundary | Remains T5-owned; no T3 later blueprint may create public result wrappers without a scope/class amendment | Per-slice blueprint non-goals and negative-action gates. |
| Full T4 Head / closed-head behavior | Remains T4-owned; T3 later only supports D6 minimal head subset | Per-slice blueprint non-goals and D6 preservation gates. |

### 2.3 No Independent Action

| Item | Reason |
|---|---|
| Final SDK top-level `Rule` flip | T5 hard-cut owns final staged naming change; T3 later continues D1/T1.3 staged names. |
| Public `RuleExprLoweringPlan` export | D7 rejects public export; implementation uses private helpers only. |
| Public `RuleExprEvaluateResult` / `EvaluateResult` | D10 rejects in T3 later; T5 owns durable public result shape. |
| RuleExprInspect execution reuse | D7 rejects RuleExprInspect as execution IR; no separate action beyond per-slice preservation tests. |
| Same-name port auto-join | D8/D9 preserve T3.3/T3.4 no-auto-join behavior; no independent syntax change. |

### 2.4 Already Aligned

| Item | Evidence |
|---|---|
| T3 authoring substrate | T3.1-T3.6 archived; RuleExpr, joins, join_by_ports, inspect, docs stable. |
| Native WhereIR branch-list support | Shipped native evaluator normalizes one-level AND and two-level OR-of-AND bodies. |
| Souffle / ProbLog branch-list support | Shipped adapters already normalize branch-list WhereIR shape. |
| PyReason pred-only branch-list subset | Shipped PyReason compiler extracts branches but validates each atom as pred-only. |
| Support branch/atom keys | Shipped support artifact keys already use `b{branch_index}.a{atom_index}:...` form. |
| Existing `CandidateSet` public success row | Shipped SDK evaluate and application derivation runtime already return `list[CandidateSet]`. |

### 2.5 Deferred / Later Tranche

| Item | Deferral |
|---|---|
| Full T4 Head / closed-head / projection API | T4. |
| T5 `EvaluateResult` DTOs and public explanation surface | T5. |
| T5 `fg.eval.why_not(...)` redesign | T5. |
| Public structured SDKStoreError payloads | T5 or a later diagnostics decision; D9 only locks message contract. |
| PyReason Form 2 aggregate / non-pred support | Later PyReason-specific design, unless a future Form 2 decision supersedes D9. |
| Stable cross-process RuleExpr execution digest | Not in T3 later; D7 `canonical_key` is private plan identity. |

## 3. Recommended Blueprint Phase Order

### T3L.1: Internal Lowering Core + Native Execution

Predicted class: M.

Purpose:

- Build private RuleExpr execution-lowering core without public SDK dispatch.
- Prove D6-D8 semantics and D10 trace sidecar against native engine first.

Must include:

- private lowering module placement decision; likely sibling module under `src/factgraph/application/protocol/` or `src/factgraph/application/` rather than extending `rule_expr.py` heavily;
- D6 C35 coercion for application Rule to one-rule RuleExpr inside private lowering entry;
- D7 `RuleExprLoweringPlan` categories: branch set, occurrence bindings, port bindings, head binding, canonical key;
- D7 alias-local variable namespacing before AND concatenation;
- D7 AND cartesian product and OR deterministic branch alternatives;
- D8 equality atom materialization for explicit joins;
- D8 `RuleExprJoinMaterialization` metadata;
- D9 branch-list `CompiledDerivationPlan` materialization for native;
- D9 aggregate preservation for native;
- D10 private trace sidecar minimum categories and lifetime/correlation invariants;
- private/focused tests proving native execution returns existing `CandidateSet` rows through internal helpers.

Must not include:

- public `fg.eval.evaluate(rule_expr, ...)` dispatch;
- Souffle / ProbLog parity;
- public result wrappers;
- SDK exports;
- docs beyond test fixtures or internal comments.

Acceptance anchors:

- D6 §4.1/§4.4; D7 §4.2-§4.12; D8 §4.1-§4.11; D9 native row; D10 §4.5.

### T3L.2: Adapter Matrix Parity + Aggregate Preservation

Predicted class: M.

Purpose:

- Extend the private lowering/materialization path to D9-supported non-native adapter behavior.
- Keep public dispatch closed until adapter behavior and preflight classifier are deterministic.

Must include:

- Souffle branch-list/equality materialization through shipped grammar floor;
- ProbLog branch-list/equality materialization through shipped grammar floor;
- aggregate-in-RuleExpr preservation for Souffle and ProbLog, including T2.3 empty-set guard behavior;
- internal PyReason support classifier: pred-only branches pass; D8 eq / non-pred / aggregate-containing branches classify as public preflight rejection candidates;
- no adapter grammar upgrade beyond shipped behavior;
- no silent downgrade of joins, OR branches, aggregates, or provenance;
- tests for native/Souffle/ProbLog matrix rows and PyReason rejection classification.

Must not include:

- public SDK dispatch if T3L.1 kept it private;
- public result DTOs;
- PyReason Form 2 grammar expansion;
- public docs except optional internal developer notes.

Acceptance anchors:

- D9 §4.1-§4.11; D10 §4.10; D8 §4.8; T2.3 aggregate invariants.

### T3L.3: Public SDK Dispatch + Diagnostics + Docs

Predicted class: M.

Purpose:

- Expose the completed T3 later execution path to users.
- Lock public error/result behavior and user-facing docs.

Must include:

- `_SDKEvalManager.evaluate(...)` dispatch branch for application Rule / RuleExpr inputs;
- required `head=` for application Rule / RuleExpr inputs;
- reject legacy SDK `Rule` / `Inference` as `head=`;
- keep legacy SDK `Inference` / derivation dict evaluation behavior unchanged;
- public success result remains `list[CandidateSet]`;
- D9 `SDKStoreError` preflight message contract for unsupported engine/grammar cells;
- PyReason public pred-only subset + non-pred rejection;
- trace sidecar correlation with selected `CandidateSet` / invocation / runtime branch index;
- user-facing docs for RuleExpr execution, supported engines, required `head=`, result shape, and adapter preflight rejections.

Must not include:

- public `RuleExprEvaluateResult` / T5 `EvaluateResult`;
- public trace/evidence DTO export;
- `CandidateSet` shape change or provenance in `payload`;
- full T4 Head / closed-head behavior.

Acceptance anchors:

- D6 public entrypoint; D9 error message contract; D10 public result boundary; T3.6 docs style and no-Python docs discipline where applicable.

## 4. Cadence Reminders For Implementing Blueprints

- Apply T3 cycle cadence patterns: preemptive scope locking, executable-quality §5/§6 specs, Step 4.6 grep, and pre-feat A-fallback when scope/risk is found.
- Each T3L.x blueprint must cite Stage 1 audit + D6-D10 by section.
- Each T3L.x blueprint must include negative-action gates for:
  - no legacy `Inference` evaluation behavior change;
  - no legacy SDK `Rule` truthiness/naming changes;
  - no `CandidateSet` or `EvidenceEnvelope` public shape change;
  - no public `RuleExprLoweringPlan` / trace DTO export;
  - no full T4 Head / closed-head behavior;
  - no T5 EvaluateResult / WhyNot public surface;
  - no PyReason grammar upgrade beyond D9 matrix.
- T3L.1 should use sibling-module isolation if lowering code would otherwise bloat `rule_expr.py`.
- T3L.2 must include adapter-specific preflight grep of native/Souffle/ProbLog/PyReason grammar handlers.
- T3L.3 must include docs grep gates and preservation tests for T3.6 docs obligations.
- G7 baselines should include T3.1-T3.6 RuleExpr tests plus relevant adapter/aggregate tests; per-slice blueprints must compute exact expected pass counts.
- Do not archive this synthesis until the final consuming T3 later blueprint archives.

## 5. Audit Trail Of Stage 2 Closure

| Commit | Artifact | Event |
|---|---|---|
| `4ac498f0` | Stage 1 audit | Draft T3 later execution shipped-state audit |
| `99e7fda0` | Stage 1 audit | Clarify Stage 2 decision map |
| `0fad6cc6` | D6 | Draft public entrypoint and head boundary |
| `728ae097` | D6 | Clarify head boundary terms; reviewed clean |
| `729e0e7d` | D7 | Draft lowering plan shape |
| `9914790f` | D7 | Clarify lowering plan invariants; reviewed clean |
| `874afaac` | D8 | Draft join lowering semantics |
| `fcbaa8ee` | D8 | Clarify join lowering invariants; reviewed clean |
| `e44a277d` | D9 | Draft adapter matrix |
| `9c7f5336` | D9 | Clarify adapter rejection boundaries; reviewed clean |
| `a7122f18` | D10 | Draft result/evidence boundary |
| `7516c973` | D10 | Clarify trace boundary; reviewed clean |

## 6. Stage 2 Decision Coverage

| Audit question | Decision owner | Outcome |
|---|---|---|
| Q1 public/internal entrypoint | D6 | Public target is `fg.eval.evaluate(rule_expr, head=...)`, but implementation may stage internals first. |
| Q2 head dependency | D6 | Minimal application Rule `head=` subset; full T4 Head / closed-head deferred. |
| Q3 lowering IR | D7 | Private `RuleExprLoweringPlan`; `CompiledDerivationPlan` downstream only. |
| Q4 AND/OR lowering | D7 | AND cartesian product, OR deterministic branch alternatives. |
| Q5 join lowering | D8 | Explicit equality atoms, no variable unification. |
| Q6 engine matrix | D9 | Native/Souffle/ProbLog supported within shipped grammar; PyReason pred-only subset. |
| Q7 grammar floor | D9 | Engine-specific existing grammar floor; no portable LCD and no adapter grammar upgrade. |
| Q7a aggregate preservation | D9 | Native/Souffle/ProbLog preserve aggregate semantics; PyReason aggregate rejected. |
| Q8 result/evidence boundary | D10 | Public `list[CandidateSet]`; private trace sidecar; T5 public evidence deferred. |
| Q9 error hierarchy | D6-D9 | `RuleExprError` for semantic/lowering, `SDKStoreError` for public call shape and adapter preflight, no new subclass. |
| Q10 slice split | This synthesis | T3L.1 internal/native, T3L.2 adapter parity, T3L.3 public dispatch/docs. |

## 7. Acceptance For This Synthesis

- [x] Stage 1 audit Q1-Q10 + Q7a mapped to D6-D10 or Stage 3.
- [x] D6-D10 reviewed rows recorded.
- [x] All audit drift rows and cross-doc seams classified into exactly one bucket.
- [x] Recommended phase order is consistent with D6-D10 dependencies.
- [x] Track plan sync rows defined for T3L.1-T3L.3.
- [x] Cadence reminders carry forward T3 cycle discipline patterns.
- [x] Audit trail current as of `7516c973`.

Lifecycle: this synthesis stays in `workflow/audit/active/` until the final consuming T3 later blueprint archives, or until a later synthesis supersedes it.
