# D6 Decision: T3 Later Public Entrypoint And Head Dependency

- Status: proposed
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: proposed design constraint; locks the public execution entrypoint and minimal head dependency boundary for the T3 later RuleExpr execution-lowering tranche.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t3-later-execution-vs-shipped.md` Q1, Q2, F2, F4, F9, F10, and §10 D6 mapping.
  - D5 `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md` §4.8 execution-lowering deferral.
  - Parent design `workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md` §4.1, §4.9, and §5.1-§5.4.
  - Track plan `workflow/design/design-points/archive/rule-expression-and-proof-track-plan.zh.md:180-196`.
  - Shipped `src/factgraph/sdk/store.py:406-434` and `src/factgraph/sdk/store.py:2197-2264`.
  - Shipped `src/factgraph/application/protocol/rule_expr.py:134-179`.
- Outputs / Downstream:
  - D7 RuleExpr lowering plan shape.
  - D8 join lowering semantics.
  - D9 adapter support matrix.
  - D10 evaluation result / evidence boundary.
  - Stage 3 T3 later synthesis and per-slice blueprints.
- Related:
  - `workflow/audit/active/2026-05-25_t3-later-execution-vs-shipped.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d1-public-surface-operand-boundary.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md`
- Branch: `v0.2.0-t3-later-execution-audit-2026-05-25`
- Depends on: T3.1-T3.6 archived and T3 later Stage 1 audit reviewed clean.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

T3.1-T3.6 shipped RuleExpr authoring, joins, inspect, and docs. D5 deliberately deferred execution lowering until after inspect was stable. The selected T3 later tranche now owns that deferred work.

The Stage 1 audit found that `fg.eval.evaluate(...)` is still inference-oriented:

- `_SDKEvalManager.evaluate(...)` delegates to `SDKStore.evaluate(...)`.
- `SDKStore.evaluate(...)` recognizes legacy derivation-like objects, derivation dicts, and direct core `Store.evaluate(...)` arguments.
- There is no application `Rule` / RuleExpr dispatch branch.

The parent design uses a public shape:

```python
fg.eval.evaluate(expr, head=some_rule)
```

but full Head / closed-head behavior is its own T4 track. D6 decides whether T3 later blocks on T4, ships no public path, or ships a minimal public entrypoint with only the head subset required to execute RuleExpr bodies.

## 2. Scope

This decision locks:

- Whether T3 later owns a public `fg.eval.evaluate(...)` RuleExpr entrypoint.
- What input types the entrypoint accepts.
- Whether `head=` is required.
- Which minimal head validations belong to T3 later.
- Which head / closed-head behaviors remain T4.
- How legacy SDK `Inference` evaluation is preserved.
- The error-bucket boundary for public call shape vs RuleExpr/head semantic errors.

## 3. Non-scope

This decision does not lock:

- The canonical lowering plan shape; D7 owns it.
- AND / OR lowering details; D7 owns them.
- Join lowering details; D8 owns them.
- Adapter support / rejection matrix; D9 owns it.
- Evaluation result DTOs, WhyNot, proof frame, or evidence schema; D10/T5 own them.
- Full T4 Head / closed-head utilities.
- T5 legacy SDK `Rule` hard-cut or final top-level `Rule` flip.
- Stable cross-process RuleExpr digest or named/saved RuleExpr.

## 4. Decision

### 4.1 T3 later owns the public `fg.eval.evaluate(rule_expr, *, head=...)` entrypoint

T3 later should extend the existing `fg.eval.evaluate(...)` public entrypoint so callers can evaluate:

- an application protocol `Rule`;
- a RuleExpr value.

The public target shape is:

```python
from factgraph.sdk import ApplicationRule, RuleExpr, build_application_rule

expr = active_user.as_("a") & recent_order.as_("b")
candidates = fg.eval.evaluate(expr, head=head_rule, engine="native")
```

Single application `Rule` inputs are coerced through the same C35 boundary as inspect and authoring: a single `Rule` is accepted wherever RuleExpr is accepted.

This C35 coercion happens at the `fg.eval.evaluate(...)` dispatch entry, before any D7-owned lowering.

### 4.2 `head=` is required for RuleExpr execution in this tranche

RuleExpr has no head/projection/claim by design. Therefore T3 later evaluation requires an explicit `head=` when the first positional input is an application `Rule` or RuleExpr value.

Calling `fg.eval.evaluate(expr)` without `head=` must fail with clear guidance that `head=` is required for RuleExpr execution.

Rationale: this avoids silently choosing a projection, avoids pulling closed-head inference into T3 later, and keeps the parent §4 design boundary intact.

### 4.3 `head=` accepts only application protocol `Rule` in T3 later

For the RuleExpr execution path, `head=` accepts:

- `factgraph.application.protocol.Rule`;
- `factgraph.sdk.ApplicationRule` (same runtime type).

It rejects:

- legacy SDK `Rule`;
- legacy SDK `Inference`;
- dict/spec payloads;
- atom lists;
- strings;
- `RuleExprInspect`.

This follows parent C52: head is a `Rule`. It also preserves D1 staged naming clarity: `factgraph.sdk.Rule` remains legacy until T5.

### 4.4 T3 later ships a minimal head subset, not full T4 Head

T3 later does not wait for the full T4 Head cycle. It owns only the head behavior required to execute a RuleExpr against existing runtime machinery.

Minimal T3 later head behavior:

- validate that `head` is an application `Rule`;
- validate stale same-id head references: same id but different content digest raises;
- allow same id + same content digest as projection onto an occurrence already present in the expression;
- require inline / external head port names to be drawn from the expression's public port namespace;
- pass the lowered head information to whatever plan shape D7 adopts.

Here, "inline head" means the head `Rule` is already present as an occurrence in the expression body; "external head" means the head `Rule` is supplied only through the `head=` keyword. D7 decides the lowering mechanism for same-id/same-digest projection onto an inline occurrence, including any alias or plan representation needed to execute that projection.

Deferred to T4:

- closed-head semantics and utilities;
- `inspect.is_closed` / `inspect.unbound_ports`;
- closed-head explanation/proof integration;
- multi-head public ergonomics;
- head-specific docs beyond the minimal T3 later execution examples;
- broader Head track commitments C52-C60 not needed for RuleExpr execution lowering.

If Stage 2 or Stage 3 later finds that even this minimal subset cannot be safely isolated, T3 later must pause and request Human re-engagement on whether to run T4 first.

### 4.5 Legacy `Inference` evaluation is preserved

Existing `fg.eval.evaluate(inference_or_derivation_dict, ...)` behavior remains unchanged.

Implementation must dispatch application `Rule` / RuleExpr inputs without changing:

- legacy SDK `Inference` object evaluation;
- structured derivation dict evaluation;
- direct lower-level `Store.evaluate(...)` call compatibility;
- public engine / semantics keyword behavior for existing inputs.

### 4.6 Public error boundary

T3 later should not introduce a new public error subclass in D6.

Error bucket guidance:

- Public call-shape mistakes at `fg.eval.evaluate(...)` use `SDKStoreError` when they are about the SDK entrypoint contract.
- RuleExpr/head semantic validation errors use `RuleExprError` when they are about expression structure, stale head identity, port namespace alignment, or D6-owned head/expression validation preconditions from §4.4.
- Adapter rejection and per-engine error policy are finalized in D9.

This keeps D6 compatible with the Stage 1 audit's Q9 disposition: Q9 is cross-cutting across D6-D9, with D9 owning adapter rejection error policy.

## 5. Rejected Alternatives

### Option A: Require T4 before any T3 later execution work

- **Why rejected**: T3 later can define a narrow head subset sufficient for execution lowering without claiming closed-head semantics. Blocking on all T4 work would pause the selected next track and force a track-order decision before learning anything from lowering design, requiring Human re-engagement on next-track ordering per the Stage 1 audit Q2 candidate analysis.

### Option B: Ship only internal lowering and no public entrypoint

- **Why rejected**: the parent design and T3.6 docs frame RuleExpr as a user-facing authoring surface. Without a public evaluation path, the tranche would complete internal plumbing but still leave the selected user capability unavailable.

### Option C: Accept legacy SDK `Rule` or `Inference` as `head=`

- **Why rejected**: violates D1 staged naming and mixes old SDK DSL semantics with application RuleExpr semantics before the T5 hard-cut.

### Option D: Make `head=` optional

- **Why rejected**: RuleExpr intentionally has no projection or claim. Optional `head=` would require implicit projection selection or closed-head behavior that belongs outside D6.

### Option E: Put full Head / closed-head in T3 later

- **Why rejected**: expands T3 later into T4 and increases cluster size without being required for the first executable RuleExpr path.

## 6. Supporting Evidence

- Stage 1 audit F2 shows `SDKStore.evaluate(...)` has no RuleExpr dispatch today.
- Stage 1 audit F4 identifies the parent head commitments as load-bearing and potentially T4-owned.
- Parent §4.1 says RuleExpr contains no head/projection/claim.
- Parent §5.1 says `head=` accepts `Rule`.
- D1 preserves staged `ApplicationRule` naming and legacy SDK `Rule` rejection.
- D5 defers execution lowering but does not require T4 before T3 later starts.

## 7. Consequences

### 7.1 Downstream unblocking

This decision unblocks:

- D7 lowering plan shape with a known public target.
- D8 join lowering under an execution path requiring `head=`.
- D9 adapter matrix for actual `fg.eval.evaluate(...)` behavior.
- D10 result/evidence boundary using existing `CandidateSet` unless superseded.
- Stage 3 synthesis for T3 later slices.

### 7.2 Required follow-up actions

D7 must decide:

- whether RuleExpr lowers to `CompiledDerivationPlan`, a new internal plan, transient derivation dicts, or adapter-specific structures;
- how `head` information is represented in that chosen plan;
- how single application `Rule` coercion is represented.

D8 must decide:

- how head port namespace alignment interacts with join lowering;
- whether joins become explicit equality atoms, variable unification, or another plan-level construct.

D9 must decide:

- adapter rejection semantics and error policy;
- whether public `engine="pyreason"` is rejected for non-pred RuleExprs or supported for a subset.

D10 must decide:

- whether the D6 public path returns existing `CandidateSet` unchanged or introduces any result wrapper later.

### 7.3 Stage 3 gating

Stage 3 synthesis must not create a blueprint that ships full T4 closed-head behavior under the T3 later tranche unless a superseding reviewed decision changes this boundary.

## 8. Acceptance Criteria

- [ ] Stage 2 D7-D10 cite this D6 decision.
- [ ] Future blueprints preserve legacy `fg.eval.evaluate(inference_or_derivation_dict, ...)` behavior.
- [ ] RuleExpr execution blueprints require `head=` for application `Rule` / RuleExpr inputs.
- [ ] RuleExpr execution blueprints reject legacy SDK `Rule` / `Inference` as `head=`.
- [ ] RuleExpr execution blueprints treat application `Rule` input as a single-rule RuleExpr.
- [ ] Full T4 Head / closed-head utilities remain out of T3 later unless a superseding decision is adopted.
- [ ] No new public error subclass is introduced by D6.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Decision drafted | Stage 1 audit v2 mapped Q1/Q2 to D6. D6 chooses public `fg.eval.evaluate(rule_expr, head=...)` as the target while limiting head ownership to the minimal execution subset. |
| 2026-05-25 | reviewed | Claude Step 4.2 v2 clean | Inline/external head terminology, projection deferral to D7, C35 dispatch location, D6-owned precondition wording, F10 cluster citation, and Q2 T4-first workflow consequence were clarified; D7 unblocked. |
