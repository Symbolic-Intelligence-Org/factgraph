# Q5 Decision: T3 Slice Split And Bool Guard Timing

- Status: adopted
- Created: 2026-05-24
- Last Updated: 2026-05-24
- Authority: design constraint; locks the T3 RuleExpr slice ladder and bool-guard timing before Stage 3 synthesis and implementing blueprints.
- Inputs:
  - `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md` Q5, Q6, Q7, A1-A15, and frictions.
  - `workflow/design/decisions/active/2026-05-24_t3-d1-public-surface-operand-boundary.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d2-join-constraint-construction.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d3-inspect-coexistence.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d4-structural-equality-hash.md`
  - Track plan `workflow/design/design-points/archive/rule-expression-and-proof-track-plan.zh.md:180-196`
- Outputs / Downstream:
  - Stage 3 T3 synthesis.
  - T3.x per-slice blueprints.
  - Track-plan synchronization for T3.2 shrinkage and T3.6 docs/examples.
- Related:
  - `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
- Branch: `v0.2.0-t3-ruleexpr-audit-2026-05-24`
- Depends on: adopted T3-D1, T3-D2, T3-D3, and T3-D4.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

The Stage 1 audit identified that T3 is too large for one blueprint. The track plan already listed T3.1-T3.5, but audit review found two required synchronizations:

- T3.2 is narrower than the original track-plan row because T1.4 already shipped `.as_`, `RuleOccurrence`, `RulePortRef`, and alias validation.
- T3.6 docs/examples and later execution-lowering slices are audit recommendations beyond the current T3.1-T3.5 track-plan list.

Adopted D1-D4 now lock the major axes:

- D1: public surface and operand boundary.
- D2: join constraint construction via `.eq(...)`, `.join_by_ports(...)` deferred.
- D3: inspect coexistence and return shape.
- D4: structural equality/hash and join symmetry.

This decision turns those constraints into the T3 slice ladder.

## 2. Scope

This decision locks:

- Initial T3 slice order.
- Whether T3 is authoring-only or executable in its first tranche.
- Which slice owns `RuleExpr.__bool__` and Rule bool guards.
- Where `.join_by_ports(...)` lands.
- Where docs/examples land.
- What Stage 3 synthesis must write back to the track plan.

## 3. Non-scope

This decision does not lock:

- Exact file/module placement.
- Exact DTO field implementation beyond D1-D4.
- Detailed Every-Proof-Path Reach Rule algorithm.
- Detailed inspect descriptor field set beyond D3 minimum.
- Adapter execution lowering for RuleExpr.
- T5 legacy `Rule` hard-cut timing.
- ADR lifecycle/template consistency cleanup.

## 4. Decision

### 4.1 T3 first tranche is authoring and inspection only

The initial T3 slice ladder ships RuleExpr authoring values, joins, validation, and inspect surfaces.

It does not ship adapter execution lowering for composite RuleExpr. Execution lowering is deferred until after T3 inspect is stable and requires a later decision or synthesis update.

### 4.2 T3.1: Base RuleExpr value and bool guards

T3.1 owns:

- Public exports from D1: `RuleExpr`, `RuleExprError`, `ExplicitBoolError`.
- Internal non-exported `_RuleExpr`, `_AndGroup`, `_OrGroup`.
- `&` / `|` operators.
- `RuleExpr.all(...)` and `RuleExpr.any(...)`.
- AND/OR flattening.
- Immutability.
- Structural equality/hash baseline from D4 for groups without joins.
- Operand acceptance/rejection from D1.
- `RuleExpr.__bool__` raising `ExplicitBoolError`.
- Application `Rule.__bool__` raising `ExplicitBoolError`.

Bool guards are included in T3.1 rather than delayed. Reason: once `&` / `|` exist, accidental Python boolean contexts become a primary correctness risk. Delaying bool guards would allow the exact ambiguity C27 is meant to prevent.

Legacy SDK `Rule.__bool__` is not changed in T3.1 because D1 preserves the T1.3 staged legacy namespace and T5 owns the legacy hard-cut.

### 4.3 T3.2: Expression-scope occurrence validation

T3.2 owns only expression-scope rules that were not already shipped by T1.4:

- alias uniqueness within a RuleExpr.
- repeated same Rule requires explicit aliases.
- default alias usage when a Rule appears once.
- diagnostics for duplicate aliases and repeated unaliased Rules.

T3.2 does not re-ship `.as_`, `RuleOccurrence`, `RulePortRef`, or alias regex validation; T1.4 already owns those.

### 4.4 T3.3: `.join(...)` and Every-Proof-Path Reach Rule

T3.3 owns:

- `RulePortRef.eq(...) -> RuleJoinConstraint` from D2.
- `.join(...)` over AND groups.
- rejection of `.join(...)` on OR groups or single Rules where parent requires it.
- Every-Proof-Path Reach Rule validation.
- self-join semantics for `a.user.eq(a.user)`.
- structural handling of join constraints as required by D4.

T3.3 does not include `.join_by_ports(...)` unless Stage 3 synthesis deliberately merges it back in after confirming it is trivial.

### 4.5 T3.4: `.join_by_ports(...)`

T3.4 owns C58 `.join_by_ports(*explicit_names)`.

It uses the T3.3 `RuleJoinConstraint` shape and must provide diagnostics for:

- missing requested ports.
- requested ports present on fewer than two occurrences.
- ambiguous expansion across more than two occurrences.
- explicit-name-only behavior; no silent same-name-port joining.

### 4.6 T3.5: RuleExpr inspect

T3.5 owns D3 inspect behavior:

- `fg.rules.inspect(application_rule)` returns `RuleExprInspect`.
- `fg.rules.inspect(rule_expr)` returns `RuleExprInspect`.
- legacy SDK Rule / Inference dict inspect remains unchanged.
- `RuleExprInspect` minimum fields and render helpers.
- single-Rule inspect coercion implementation shape: transient RuleExpr value or synthesized inspect-only view.

T3.5 must consume D2 join constraints and D4 canonicalization semantics.

T3.5 may internally split into T3.5a (core `RuleExprInspect` minimum from D3) and T3.5b (rich descriptors: C49 `OccurrenceInspect`, C50 `AtomDescriptor`, C51 render contract, C59 `PortInspect`, plus D3-deferred `templates`, `port_visibility`, and `ports`) if blueprint preflight shows scope risk. This decision locks the ownership of that work in the inspect tranche but does not force it into one blueprint.

### 4.7 T3.6: Docs and examples

T3.6 owns user-facing docs and examples after the authoring and inspect slices are stable.

Docs must:

- use D1's staged import style with `ApplicationRule`, `RuleExpr`, and `build_application_rule`.
- show `.eq(...)` join syntax from D2.
- explain `&` / `|` Python precedence and required parentheses for mixed AND/OR expressions (C24).
- explain bool guards.
- explain same-name ports do not auto-join.
- explain inspect return-shape differences between legacy and RuleExpr inputs from D3.

Stage 3 synthesis should add T3.6 to the track plan because the current track plan stops at T3.5.

### 4.8 Later: RuleExpr execution lowering

RuleExpr execution lowering is not part of T3.1-T3.6.

Execution lowering should be a later L- or M-class tranche after T3 authoring/inspect behavior stabilizes. It must decide adapter semantics and how composite RuleExprs map to proof/evaluation machinery.

### 4.9 Track-plan synchronization

Stage 3 synthesis must update the track plan to reflect:

- T3.2 shrinkage due to T1.4 substrate.
- T3.6 docs/examples as an explicit slice.
- execution lowering as a later tranche, not part of initial T3 authoring/inspect tranche.

## 5. Rejected Alternatives

### Option A: Implement all T3 commitments in one blueprint

- **Why rejected**: T3 contains 18 audited commitments/seams and several adopted cross-cutting decisions. One blueprint would recreate T2.3c-style churn.

### Option B: Delay bool guards until after joins

- **Why rejected**: bool guards protect the moment `&` / `|` become available. Delaying them allows accidental truthiness and undermines C27.

### Option C: Include execution lowering in T3.1

- **Why rejected**: execution lowering is not required to validate authoring IR, occurrence rules, joins, or inspect. It would pull adapter semantics into the first slice and expand L-class risk.

### Option D: Merge `.join_by_ports(...)` into base `.join(...)` by default

- **Why rejected**: D2 intentionally deferred `.join_by_ports(...)`; it has separate expansion and diagnostic rules.

### Option E: Ship docs first

- **Why rejected**: docs before stable authoring syntax would either under-specify T3 or promise details that D2/D3/D4 deliberately deferred to implementation slices.

## 6. Supporting Evidence

- Stage 1 audit Q5 recommends slice split before coding.
- D1 locks public surface, operand boundary, and legacy SDK Rule rejection.
- D2 locks `.eq(...)` join constraints and defers `.join_by_ports(...)`.
- D3 locks inspect coexistence and minimum RuleExprInspect behavior.
- D4 locks equality/hash and join constraint normalization.
- Parent C27 requires bool guard errors.
- Track plan lines 180-196 list T3.1-T3.5 and need synchronization after audit amendments.

## 7. Consequences

### 7.1 Downstream unblocking

This decision unblocks Stage 3 synthesis and prevents per-slice blueprints from re-litigating the basic T3 order.

### 7.2 Required follow-up actions

Stage 3 synthesis must:

- Convert this ladder into blueprint-ready acceptance gates.
- Update the track plan rows for T3.2 and T3.6.
- Preserve the execution-lowering deferral.
- Cross-reference D1-D4 in every relevant slice.

### 7.3 Blueprint gating

No T3.1 blueprint should begin until this D5 is adopted and the Stage 3 synthesis is drafted.

## 8. Acceptance Criteria

- [ ] Stage 3 synthesis uses T3.1-T3.6 order from this decision.
- [ ] T3.1 includes bool guards.
- [ ] T3.2 excludes already-shipped T1.4 `.as_` substrate work.
- [ ] T3.3 excludes `.join_by_ports(...)` unless Stage 3 explicitly merges it.
- [ ] T3.5 preserves legacy inspect dict behavior.
- [ ] T3.6 docs/examples are represented in the track plan.
- [ ] Execution lowering is deferred outside the initial T3.1-T3.6 tranche.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-24 | proposed | Decision drafted | D1-D4 were adopted; D5 converts their constraints plus audit Q5-Q7 into a concrete T3 slice ladder. |
| 2026-05-24 | adopted | P2 amendment cleared, Stage 2 closure-ready | D5 P2 framing sharpening landed in 1d2e4c8f; reviewer pass confirmed adoption prerequisites; all 5 T3 Stage 2 decisions (D1-D5) now adopted. |
