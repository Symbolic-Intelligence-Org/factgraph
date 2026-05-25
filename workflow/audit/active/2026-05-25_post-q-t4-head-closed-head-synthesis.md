# Synthesis: T4 Head + Closed-Head Post-Q Bucketing

- Status: complete
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: working triage document; informs but does not lock implementation. Final scope decisions live in implementing blueprints per CADENCE Stage 3.
- Inputs:
  - `workflow/audit/active/2026-05-25_t4-head-closed-head-vs-shipped.md`
  - `workflow/design/decisions/active/2026-05-25_t4-d11-scope-head-identity-boundary.md`
  - `workflow/design/decisions/active/2026-05-25_t4-d12-declared-port-namespace.md`
  - `workflow/design/decisions/active/2026-05-25_t4-d13-external-head-body-semantics.md`
  - `workflow/design/decisions/active/2026-05-25_t4-d14-rule-projection-sugar.md`
  - `workflow/design/decisions/active/2026-05-25_t4-d15-closed-head-inspect.md`
- Outputs / Downstream:
  - T4.1-T4.3 implementation blueprint ladder.
  - Track-plan synchronization patch for T4 rows.
  - Per-slice preservation invariants and negative-action gates.
- Related:
  - `workflow/audit/active/2026-05-25_post-q-t3-later-execution-synthesis.md`
  - `workflow/blueprints/archive/2026-05-25_t3l-1-internal-lowering-native.md`
  - `workflow/blueprints/archive/2026-05-25_t3l-2-adapter-matrix-parity.md`
  - `workflow/blueprints/archive/2026-05-25_t3l-3-public-dispatch-diagnostics-docs.md`
- Source audit: `workflow/audit/active/2026-05-25_t4-head-closed-head-vs-shipped.md`
- Closed Q decisions:
  - D11 Scope + Head Identity Boundary
  - D12 Declared Port Namespace + Head Alignment
  - D13 External Head Body Semantics
  - D14 Rule Projection Sugar
  - D15 Closed-Head Validator + Inspect Utilities
- Branch: `v0.2.0-t4-head-closed-head-audit-2026-05-25`

> Synthesis is required because the T4 audit closed five decisions spanning existing-head identity, declared-port alignment, external-head body semantics, projection sugar, closed-head inspect utilities, and the T4/T5 evidence boundary.

## 1. Scope Of Synthesis

This synthesis re-buckets T4 Stage 1 audit rows after D11-D15 review.

It does not implement Head behavior and does not replace per-slice blueprints. It produces the implementation ladder and synchronization obligations for the T4 Head + closed-head tranche.

## 2. 5-Bucket Classification

### 2.1 Blueprint-Eligible

| Item | Destination | Reason |
|---|---|---|
| Existing-head id + content digest validation | T4.1 | D11 locks same id + same digest as the inline/existing-head identity path and same id + different digest as `RuleExprError`. |
| Existing-head version mismatch warning | T4.1 | D11 locks `warnings.warn(..., UserWarning)` once per evaluation validation path. |
| Public `head=` call-shape preservation | T4.1 | D11 inherits D6/T3L.3: invalid public `head=` types remain `SDKStoreError`, success remains `list[CandidateSet]`. |
| Private branch-total declared-port helper | T4.1 | D12 rejects public `expr.declared_ports` and locks a private deterministic helper. |
| Head port namespace validation | T4.1 | D12 locks head `ports.keys` subset-or-equal to branch-total declared ports with exact `PortType` compatibility. |
| Same-name port ambiguity / equivalence | T4.1 | D12 locks ambiguity rejection unless D8 join materialization proves same-name sources equivalent. |
| External head body concatenation | T4.2 | D13 lifts T3L.3 external-head rejection and adds alias-scoped head body atoms to every branch. |
| Head-port link equality atoms | T4.2 | D13 locks D12-based equality links between head ports and expression declared-port sources. |
| Separate head-link provenance | T4.2 | D13 distinguishes head-port links from D8 user-authored join materialization for future evidence. |
| `Rule.projection(*port_names)` public sugar | T4.2 | D14 locks same-name positional projection returning application `Rule`, with rename deferred. |
| Private recognizable projection-head shape | T4.2 | D14 preserves shipped `Rule.where` non-empty invariant while preventing placeholder atoms from materializing. |
| Projection `PortType` from D12 declared ports | T4.2 | D14 locks projection-specific validation because projection construction lacks expression context. |
| Closed-head strict v1 validator | T4.3 | D15 locks value `Var == Const` and entity-ref primary identity literal binding as the only v1 closure forms. |
| `inspect.is_closed` and `inspect.unbound_ports` | T4.3 | D15 locks inspect-output placement and rejects fields on `Rule` / RuleExpr. |
| Missing schema metadata conservative behavior | T4.3 | D15 locks false-positive avoidance for entity-ref closedness. |
| T4 user-facing docs | T4.3 | Public behavior spans head identity, projection, external heads, and inspect utilities; docs should land after implementation behavior is stable. |

### 2.2 Cross-Doc Blocked

| Item | Required synchronization | Timing |
|---|---|---|
| Track plan T4 row | Replace T4.1-T4.5 placeholder ladder with Stage 1-3 anchor plus T4.1-T4.3 implementation ladder. | This synthesis commit. |
| D11-D15 reviewed status | Add §9 reviewed rows to each D-doc so Stage 3 cites reviewed decisions, not proposed-only records. | This synthesis commit. |
| Projection recognizer spoofing mitigation | D14 intentionally leaves exact recognizer contract to implementation blueprint. | T4.2 blueprint §5/§6 invariants. |
| T4/T5 closed-head caller boundary | D15 owns validator and inspect reporting; T5 owns manual explain / row.close caller paths. | T4.3 blueprint non-goals and T5 deferred bucket. |

### 2.3 No Independent Action

| Item | Reason |
|---|---|
| Public `expr.declared_ports` property | D12 rejects public property; implementation uses private helper. |
| Public `ClosedHeadStatus` DTO | D15 rejects public DTO; fields live on inspect output. |
| Public projection DTO | D14 rejects public projection DTO; `Rule.projection(...)` returns application `Rule`. |
| T3L.3 minimal head rejection behavior as final state | D13 supersedes it in T4; no independent preservation except tests that old error is lifted after T4. |
| Rename projection syntax | D14 defers rename to v2; no T4 implementation slice should add it. |
| General field literal closedness | D15 rejects for v1; no implementation action in T4. |
| Transitive/cross-port equality closedness | D15 rejects for v1; no implementation action in T4. |
| `head.desc` evidence rendering | D11 preserves `desc` as metadata, but evidence narrative rendering is T5-owned. |

### 2.4 Already Aligned

| Item | Evidence |
|---|---|
| Application `Rule` already first-class | T1.1 shipped application `Rule` with `where`, `ports`, `desc`, `content_digest`, and `port_types`. |
| T3L.3 public RuleExpr execution entrypoint | `fg.eval.evaluate(application_rule|rule_expr, head=...)` already exists with minimal head behavior. |
| RuleExpr branch lowering substrate | T3L.1 provides private branch/occurrence/port binding and materialization substrate. |
| Adapter matrix behavior | T3L.2/T3L.3 provide native/Souffle/ProbLog materialization and PyReason classifier behavior. |
| RuleExpr inspect surface | T3.5 provides `RuleExprInspect`, `PortInspect`, `OccurrenceInspect`, and stable structural fields. |
| Schema primary identity metadata | SDK schema + application schema runtime preserve `Identity(primary_key=True)` and identity predicate metadata. |
| Missing `head=` rejection | T3L.3 already requires `head=` for RuleExpr/application Rule evaluation; D11 preserves the SDK call-shape bucket. |
| Explicit `.join_by_ports(...)` syntax | T3.4 already shipped explicit same-name join expansion; D12 consumes the D8 materialization result and rejects auto-join. |
| Existing `inspect.ports` descriptors | T3.5 already ships `PortInspect`; D15 adds closed-head utility fields without replacing the port descriptor surface. |
| Application `Rule.desc` metadata | T1.1 shipped `desc` validation and rendering; D11 keeps it as Head metadata without creating evidence output. |

### 2.5 Deferred / Later Tranche

| Item | Deferral |
|---|---|
| `EvaluateResult`, `EvaluateRow`, `row.close()` | T5. |
| `fg.eval.explain(...)` and manual closed-head replay | T5. |
| Explanation / EvidenceGraph / WhyNot public surfaces | T5. |
| Projection rename syntax | Later projection decision after T4 v1. |
| General field literal closure | Later closed-head v2 if user need is proven. |
| Transitive equality and cross-port equality closure | Later closed-head v2. |
| Public structured warning / diagnostic DTOs | T5 or later diagnostics decision; T4 uses existing exceptions and Python warnings. |
| T1.3 final SDK `Rule` hard-cut | Separate T5-era hard-cut boundary; T4 continues staged application `Rule` imports. |

## 3. Recommended Blueprint Phase Order

### T4.1: Head Identity + Declared-Port Foundation

Predicted class: M.

Purpose:

- Build shared Head validation substrate before changing external-head execution behavior.
- Lock D11 identity/warning rules and D12 declared-port semantics behind private helpers.

Must include:

- central private head classification helper for inline / external / projection categories, with D14 projection detection reserved for T4.2 if not implemented yet;
- D11 existing-head `(id, content_digest)` validation;
- D11 version mismatch `UserWarning` behavior;
- D12 private branch-total declared-port helper;
- D12 exact `PortType` compatibility;
- D12 same-name source ambiguity rejection and D8 join-materialization equivalence recognition;
- T3L.3 public result shape preservation;
- tests for inline existing-head validation, stale digest rejection, version warning, undeclared head port, branch-partial declared ports, and same-name ambiguity.

Must not include:

- external-head body concatenation;
- `Rule.projection(...)`;
- closed-head inspect fields;
- public `expr.declared_ports`;
- T5 result/evidence surfaces.

Acceptance anchors:

- D11 §4.1-§4.7; D12 §4.1-§4.8; D6/T3L.3 public error boundary.

### T4.2: External + Projection Head Execution

Predicted class: M.

Purpose:

- Lift T3L.3 external-head rejection and implement the new public projection sugar using the T4.1 validation foundation.

Must include:

- D13 external-head body atoms added to every executable branch;
- D13 private head alias variable rewriting;
- D13 head-port link equality atoms after D8 joins;
- D13 separate head-link provenance metadata kept private;
- D14 `Rule.projection(*port_names)` public classmethod;
- D14 private recognizable projection-head shape and anti-spoofing contract;
- D14 projection placeholder atoms not materialized as filters;
- D14 projection `PortType` copied from D12 declared-port map;
- tests for external-head filters, OR branch head body application, aggregate-containing external head behavior, projection subset/all-ports, projection output order, and projection placeholder exclusion.

Must not include:

- projection rename syntax;
- public projection DTOs;
- adapter grammar expansion;
- closed-head inspect fields unless Stage 3/blueprint explicitly folds them in;
- T5 result/evidence surfaces.

Acceptance anchors:

- D13 §4.1-§4.9; D14 §4.1-§4.9; D12 declared-port helper; T3L.1/T3L.2 materialization substrate.

### T4.3: Closed-Head Inspect Utilities + Docs

Predicted class: M.

Purpose:

- Ship C72 inspect utilities and document the completed T4 Head behavior.

Must include:

- D15 strict v1 closed-head validator;
- value-port direct `Var == Const` and `Const == Var` detection;
- entity-ref primary identity closure using schema index identity predicates;
- compound primary identity all-fields-required behavior;
- missing schema metadata conservative behavior;
- `is_closed` and `unbound_ports` on inspect output, without removing existing inspect fields;
- projection heads closed-by-construction after D12 validation;
- user-facing docs for head identity, declared ports, external heads, projection sugar, and closed-head inspect utilities.

Must not include:

- `fg.eval.explain(...)`;
- `row.close()`;
- `EvaluateResult` / `EvaluateRow`;
- Explanation / EvidenceGraph / WhyNot;
- general field literal closure;
- transitive or cross-port equality closure.

Acceptance anchors:

- D15 §4.1-§4.10; D14 projection closure; T3.5/T3.6 inspect/docs style.

## 4. Cadence Reminders For Implementing Blueprints

- Carry forward T3/T3L discipline: preemptive scope locking, executable-quality specs, Step 4.6 grep, A-fallback amendment if implementation shape exceeds the blueprint, and Step 4.7 fix commits when review finds coverage gaps.
- Each T4.x blueprint must cite Stage 1 audit + D11-D15 by section.
- Each T4.x blueprint must include negative-action gates for:
  - no `CandidateSet` / `EvidenceEnvelope` / `EvaluateResult` public shape change;
  - no public `expr.declared_ports`;
  - no projection rename syntax;
  - no public Head/projection/closed-head DTO export beyond locked inspect fields;
  - no new public error subclass;
  - no adapter grammar upgrade;
  - no `fg.eval.explain`, `row.close`, Explanation, or WhyNot surface.
- T4.1 should isolate shared validation helpers so T4.2 and T4.3 consume the same substrate.
- T4.2 should include a projection recognizer spoofing preflight and exact private-shape tests.
- T4.3 should include docs grep for T5 terms so docs do not promise explain/result/evidence behavior.
- G7 baselines should include the final T3 later preservation suite plus the new T4 tests as they accumulate.
- Do not archive this synthesis until the final consuming T4 blueprint archives.

## 5. Audit Trail Of Stage 2 Closure

| Commit | Artifact | Event |
|---|---|---|
| `8fae97b2` | Stage 1 audit | Draft T4 head / closed-head shipped-state audit |
| `9e1254d1` | D11 | Draft scope + head identity boundary |
| `1c83c416` | D11 | Clarify identity scope and warning rationale; reviewed clean |
| `12fb96a2` | D12 | Draft declared port namespace + head alignment |
| `cf99a616` | D12 | Clarify join equivalence and D14 boundary; reviewed clean |
| `84e5323a` | D13 | Draft external head body semantics |
| `5a292d9c` | D13 | Clarify aggregate/PyReason and output schema wording; reviewed clean |
| `3b39806a` | D14 | Draft projection sugar; reviewed clean v1 |
| `4416868d` | D15 | Draft closed-head validator + inspect utilities |
| `126e6a41` | D15 | Clarify closed-head invariant and T5 boundary; reviewed clean |

## 6. Stage 2 Decision Coverage

| Audit question | Decision owner | Outcome |
|---|---|---|
| Q1 T4 scope post-T3L.3 | D11 | T4 owns C52-C60 + C72 remaining Head behavior while preserving T3L.3 public result boundary. |
| Q2 declared ports source | D12 | Private branch-total declared-port helper; no public `expr.declared_ports`. |
| Q3 existing head identity + warning rules | D11 | `(id, content_digest)` identity; digest mismatch errors; version mismatch warns and proceeds. |
| Q4 external head body semantics | D13 | External head body atoms are alias-scoped and conjoined into every executable branch. |
| Q5 `Rule.projection(...)` shape | D14 | Public same-name projection classmethod returns application `Rule` with private recognizable placeholder shape. |
| Q6 closed-head algorithm + schema input | D15 | Strict v1: value direct literal equality and entity-ref primary identity literal binding only. |
| Q7 inspect field location | D15 | `is_closed` / `unbound_ports` live on inspect output, not `Rule` or RuleExpr. |
| Q8 T4 error / warning buckets | D11-D15 | `RuleValidationError` for construction, `RuleExprError` for semantic validation, `SDKStoreError` for SDK call shape, `UserWarning` for version drift. |
| Q9 T4/T5 closed-head evidence boundary | D15 | T4 ships validator + inspect reporting only; T5 owns explain/result/evidence/row.close. |
| Q10 slice split | This synthesis | T4.1 foundation, T4.2 external/projection execution, T4.3 closed-head inspect/docs. |

## 7. Acceptance For This Synthesis

- [x] Stage 1 audit Q1-Q10 mapped to D11-D15 or Stage 3.
- [x] D11-D15 reviewed rows recorded.
- [x] All audit rows and C52-C60/C72 commitments classified into exactly one bucket.
- [x] Recommended phase order is consistent with D11-D15 dependencies.
- [x] Track plan sync rows defined for T4.1-T4.3.
- [x] Cadence reminders carry forward T3/T3L cycle discipline patterns.
- [x] Audit trail current as of `126e6a41`.

Lifecycle: this synthesis stays in `workflow/audit/active/` until the final consuming T4 blueprint archives, or until a later synthesis supersedes it.
