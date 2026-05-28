# D11 Decision: T4 Scope And Head Identity Boundary

- Status: proposed
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: proposed design constraint; locks the T4 post-T3L.3 scope boundary and existing-head identity / warning semantics.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t4-head-closed-head-vs-shipped.md` Q1, Q3, F1, F3, F8, F9, and §6 commitment triage.
  - Parent design `workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md` §5.0-§5.7, C52-C60, and C72 boundary references.
  - Track plan `workflow/design/design-points/archive/rule-expression-and-proof-track-plan.zh.md:210-230`.
  - D6 `workflow/design/decisions/active/2026-05-25_t3-later-d6-public-entrypoint-head-dependency.md` §4.4 and §4.6.
  - T3L.3 archived blueprint `workflow/blueprints/archive/2026-05-25_t3l-3-public-dispatch-diagnostics-docs.md`.
  - Shipped `src/factgraph/application/protocol/rule.py:47-108`.
  - Shipped `src/factgraph/application/protocol/rule_expr.py:333-334`.
  - Shipped `src/factgraph/application/protocol/rule_expr_lowering.py:506-536`.
  - Shipped `src/factgraph/sdk/store.py:2210-2387`.
- Outputs / Downstream:
  - D12 declared-port namespace and head port alignment.
  - D13 external-head body semantics.
  - D14 `Rule.projection(...)` sugar.
  - D15 closed-head validator and inspect utilities.
  - Stage 3 T4 synthesis and per-slice blueprints.
- Related:
  - `workflow/audit/active/2026-05-25_t4-head-closed-head-vs-shipped.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d6-public-entrypoint-head-dependency.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d10-evaluation-result-evidence-boundary.md`
- Branch: `v0.2.0-t4-head-closed-head-audit-2026-05-25`
- Depends on: T3 later cycle archived, memory-consolidated, pushed, and T4 Stage 1 audit reviewed clean v1.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

T3L.3 shipped the first public RuleExpr execution path:

```python
fg.eval.evaluate(rule_expr_or_application_rule, head=head_rule, engine="native")
```

That path is intentionally narrow:

- it requires `head=`;
- it accepts only application protocol `Rule` as `head=`;
- it rejects external-head body concatenation;
- it returns existing `list[CandidateSet]`;
- it does not expose T5 `EvaluateResult`, `Explanation`, or WhyNot surfaces.

The T4 Stage 1 audit found that parent Head commitments remain broader than T3L.3:

- C52-C60 define first-class Head behavior over application `Rule`;
- C53 requires id + content digest identity and version mismatch warning;
- C54 requires port-name alignment against `expr.declared_ports`;
- C55 expects ordinary Rule body grammar for heads;
- C56 introduces `Rule.projection(...)`;
- C72 adds closed-head inspect utilities.

D11 decides the foundational scope and identity boundary so later T4 decisions do not each re-litigate T3L.3 inheritance or existing-head identity.

## 2. Scope

This decision locks:

- what T4 owns after T3L.3;
- what remains T5 or later;
- whether T4 reuses or replaces the T3L.3 public evaluation path;
- existing-head identity states for parent C53;
- version mismatch warning mechanism and timing;
- error buckets for identity validation;
- which Stage 1 audit minor polish items are absorbed into Stage 2 decisions.

## 3. Non-Scope

This decision does not lock:

- the canonical `expr.declared_ports` source; D12 owns it;
- external-head body concatenation semantics; D13 owns it;
- `Rule.projection(...)` representation; D14 owns it;
- closed-head algorithm or inspect DTO fields; D15 owns them;
- T5 `EvaluateResult`, `EvaluateRow`, `Explanation`, `row.close()`, or WhyNot;
- adapter grammar changes;
- T1.3 final legacy SDK `Rule` hard-cut;
- public result-shape replacement for `list[CandidateSet]`.

## 4. Decision

### 4.1 T4 owns remaining Head behavior, not T5 result/evidence surfaces

T4 owns the remaining parent Head commitments required before closed-head validation can be used safely:

- C52 first-class `head=Rule` boundary;
- C53 existing-head identity;
- C54 port-name alignment and declared-port namespace;
- C55 external-head body semantics;
- C56 `Rule.projection(...)` sugar;
- C60 `head.desc` as a narrative anchor, as far as Head metadata is concerned;
- C72 closed-head inspect utilities.

T4 does not own:

- `EvaluateResult`;
- `EvaluateRow`;
- public `Explanation`;
- `row.close()`;
- `fg.eval.why_not(...)`;
- public evidence graph narrative rendering.

Those remain T5 unless a later reviewed decision explicitly changes the track boundary.

### 4.2 T4 extends the T3L.3 public path instead of replacing it

T4 keeps the shipped `fg.eval.evaluate(rule_expr_or_application_rule, *, head=head_rule, ...)` path as the base public execution path.

T4 decisions and blueprints may extend that path by:

- replacing T3L.3's external-head rejection with reviewed external-head semantics;
- adding shared head validation helpers used by evaluation and inspect;
- adding projection sugar that produces application `Rule` values acceptable to the same path;
- adding closed-head inspect utilities.

T4 must not replace the T3L.3 success result shape. Public success continues to return `list[CandidateSet]` until T5 changes it.

### 4.3 Existing-head identity is `(id, content_digest)`, with version as warning-only metadata

For T4, an existing head is recognized by matching a supplied `head` Rule against Rule occurrences in the expression.

Identity states:

1. Same id + same `content_digest` + same `version`: treat as the same Rule.
2. Same id + same `content_digest` + different `version`: treat as the same Rule and emit a warning.
3. Same id + different `content_digest`: reject as stale or conflicting Rule identity.
4. Different id: not the same existing Rule; it is independent and is handled by the external / inline semantics locked by D12/D13.

`version` is not part of `content_digest` and must not become part of equality / hash / join behavior in T4. It is warning-only metadata for user mistakes.

### 4.4 Version mismatch warning uses Python `warnings.warn(...)`

T4 implements parent C53's version mismatch warning through Python's `warnings.warn(...)`, not through a new public DTO or result field.

Minimum behavior:

- Warning category: `UserWarning` unless a later implementation blueprint justifies a narrower internal warning category without exporting a new public type.
- Emission timing: during explicit head validation for a public evaluation / head-inspection operation, not during `Rule` construction.
- Emission frequency: at most once per validation invocation per matched head/occurrence pair.
- Message content: include head id, supplied version, matched occurrence version, and state that id + content digest matched.

`UserWarning` is the default because this is user-facing context about metadata drift, not a runtime anomaly. `RuntimeWarning` remains reserved for actual runtime/environment anomalies.

This directly addresses the Stage 1 audit Q3 warning-mechanism gap: D11 rejects SDK warning DTOs, docs-only warnings, and persistent audit records for T4. T5 may later introduce structured warning surfaces as part of result/evidence redesign.

### 4.5 Identity validation errors use `RuleExprError`

T4 keeps D6's error-bucket boundary:

- Public call-shape mistakes at `fg.eval.evaluate(...)` use `SDKStoreError`.
- Head / expression semantic validation errors use `RuleExprError`.
- Rule DTO construction invariants use `RuleValidationError`.

Therefore:

- same id + different digest raises `RuleExprError`;
- duplicate same-id matching across multiple expression occurrences is D12/D13 territory, but it inherits the same `RuleExprError` bucket for incompatible digest or ambiguous identity cases;
- head port namespace mismatch raises `RuleExprError`;
- closed-head semantic validation failures raise `RuleExprError` unless D15 adopts a more specific existing bucket;
- missing or invalid `head=` type continues to use `SDKStoreError`.

T4 does not add a new public error subclass.

### 4.6 `head.desc` is preserved as Head metadata, but evidence rendering remains T5

T4 should preserve `head.desc` and keep it available wherever Head metadata is carried.

T4 may document that `head.desc` is recommended for future evidence readability, but it must not implement T5 evidence narrative rendering. D15 closed-head inspect utilities may read `desc` only as metadata; they must not create public explanation output.

### 4.7 D11 intentionally defers the F2/F5/Q2/Q5 interaction to D12-D14

Stage 1 review WC2 noted that projection sugar, inline-head matching, and declared-port source interact.

D11 records the dependency but does not resolve it:

- D12 locks the canonical declared-port namespace.
- D13 locks external-head body semantics and whether T3L.3 rejection is superseded.
- D14 locks `Rule.projection(...)` representation under shipped `Rule.where` non-empty invariants.

No T4 blueprint may implement projection or external-head semantics before D12-D14 are reviewed.

## 5. Rejected Alternatives

### Option A: Treat T3L.3 as already completing T4

- **Why rejected**: T3L.3 intentionally shipped a minimal head subset. It rejects external heads, lacks projection sugar, lacks declared-port API, lacks version warning behavior, and lacks closed-head inspect utilities.

### Option B: Block T4 until T5 result/evidence redesign

- **Why rejected**: T4 can lock Head validation and closed-head inspect utilities without shipping `EvaluateResult`, `Explanation`, or WhyNot. Blocking on T5 would unnecessarily couple the selected Head track to the largest future redesign.

### Option C: Replace `list[CandidateSet]` with `EvaluateResult` in T4

- **Why rejected**: D10 and T3L.3 explicitly preserve `list[CandidateSet]`. `EvaluateResult` belongs to T5.

### Option D: Include `version` in Rule identity

- **Why rejected**: shipped content identity is id + content digest. Parent C53 treats version mismatch as warning, not identity failure. Including version in identity would turn a warning case into a different Rule.

### Option E: Make version mismatch an error

- **Why rejected**: parent C53 requires warning and proceed semantics for same id + same digest + different version. Raising would make harmless metadata drift block evaluation.

### Option F: Use SDK warning DTOs or result fields for version mismatch

- **Why rejected**: T4 does not own a public result wrapper or warning DTO. Python warnings provide a narrow, testable, non-shape-changing mechanism.

### Option G: Docs-only warning for version mismatch

- **Why rejected**: parent C53 says version mismatch warns. Docs-only behavior would make the commitment non-executable.

### Option H: Persist version mismatch into audit/support artifacts in T4

- **Why rejected**: this would create evidence/result coupling that belongs to T5. T4 only needs a caller-visible validation warning.

## 6. Supporting Evidence

- Parent C53 defines id + content digest identity and version mismatch warning.
- Shipped `Rule` has `version` and deterministic `content_digest`.
- Shipped RuleExpr canonical identity is `(rule.id, rule.content_digest)`.
- Shipped T3L lowering identifies inline heads by same id + same content digest.
- D6 §4.6 already separates SDK call-shape errors from RuleExpr/head semantic validation errors.
- T3L.3 public path currently rejects external heads, proving T4 still has remaining Head work.
- Stage 1 audit F2 shows `Rule.projection(...)` must be decided separately because shipped `Rule.where` is non-empty.
- Stage 1 audit F7 shows closed-head utilities are not shipped.

## 7. Consequences

### 7.1 Downstream unblocking

D11 unblocks:

- D12 declared-port namespace and C54 alignment.
- D13 external-head body semantics.
- D14 projection sugar.
- D15 closed-head validator and inspect utilities.
- Stage 3 T4 synthesis.

### 7.2 Implementation constraints

Future T4 implementation must:

- centralize head identity validation so evaluation, external-head handling, projection, and inspect do not diverge;
- preserve T3L.3 legacy path behavior;
- use `warnings.warn(...)` for version mismatch;
- keep identity validation out of `Rule.__post_init__`;
- avoid new public warning/error/result DTOs;
- avoid T5 result/evidence surfaces.

### 7.3 Stage 3 gating

Stage 3 synthesis must not create a blueprint that implements projection, external-head body concatenation, or closed-head utilities before D12-D15 are reviewed.

## 8. Acceptance Criteria

- [ ] D12-D15 cite D11 for T4/T5 scope and existing-head identity.
- [ ] T4 blueprints do not replace `list[CandidateSet]` success return shape.
- [ ] Existing-head same id + same digest + different version emits a Python warning and proceeds.
- [ ] Existing-head same id + different digest raises `RuleExprError`.
- [ ] Public call-shape errors continue to use `SDKStoreError`.
- [ ] No T4 blueprint adds a new public error, warning, result, or evidence DTO.
- [ ] `Rule.__post_init__` remains free of evaluation-specific head identity warnings.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Decision drafted | T4 Stage 1 audit v1 mapped Q1/Q3 to D11. D11 locks T4 post-T3L.3 scope, existing-head id/digest identity, version mismatch warning mechanics, and error buckets; D12-D15 remain responsible for declared ports, external heads, projection, and closed-head utilities. |
| 2026-05-25 | proposed-amend | Step 4.2 v1 precision amendments | Clarified that duplicate same-id multi-occurrence matching belongs to D12/D13 while inheriting D11's `RuleExprError` bucket, and added the `UserWarning` rationale for version mismatch warnings. |
| 2026-05-25 | reviewed | Claude Step 4.2 v2 clean | WC1 multi-occurrence territory and WC2 UserWarning rationale addressed; D11 substrate sound; D12 unblocked. |
