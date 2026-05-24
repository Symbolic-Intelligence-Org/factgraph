# Synthesis: T3 RuleExpr Post-Q Bucketing

- Status: complete
- Created: 2026-05-24
- Last Updated: 2026-05-24
- Authority: working triage document; informs but does not lock implementation. Final scope decisions live in implementing blueprints per CADENCE Stage 3.
- Inputs:
  - `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d1-public-surface-operand-boundary.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d2-join-constraint-construction.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d3-inspect-coexistence.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d4-structural-equality-hash.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md`
- Outputs / Downstream:
  - T3.1-T3.6 blueprint ladder.
  - Track-plan synchronization patch for T3 rows.
  - Per-slice acceptance gates and preservation invariants.
- Related:
  - `workflow/blueprints/archive/2026-05-23_t1-4-alias-port-contract.md`
- Source audit: `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
- Closed Q decisions:
  - D1 Public Surface And Operand Boundary
  - D2 Join Constraint Construction
  - D3 Inspect Coexistence
  - D4 Structural Equality And Hash
  - D5 Slice Split And Bool Guard Timing
- Branch: `v0.2.0-t3-ruleexpr-audit-2026-05-24`

> Synthesis is required because the T3 audit closed five Q decisions spanning blueprint-eligible work, cross-doc blocked work, already-aligned substrate, and deferred execution lowering.

## 1. Scope Of Synthesis

This synthesis re-buckets T3 Stage 1 audit rows after D1-D5 adoption.

It does not implement RuleExpr and does not replace per-slice blueprints. It produces the blueprint-ready ladder and the synchronization obligations that must appear before T3.1 enters implementation.

## 2. 5-Bucket Classification

### 2.1 Blueprint-Eligible

| Item | Destination | Reason |
|---|---|---|
| C23 operators `&` / `|` and `RuleExpr.all/any` | T3.1 | D1 locks public surface; D5 assigns base value to T3.1. |
| C24 Python precedence documentation | T3.6 | D5 requires docs explain `&` / `|` precedence and parentheses. |
| C25 AND/OR flattening | T3.1 | D4 locks commutative/flattened equality; D5 assigns to T3.1. |
| C26 internal `_RuleExpr` / `_AndGroup` / `_OrGroup` hidden | T3.1 | D1 locks exports and internal hidden classes. |
| C27 bool guards | T3.1 | D5 explicitly moves RuleExpr/application Rule bool guards into T3.1. |
| C28-C29 occurrence alias expression-scope validation | T3.2 | T1.4 substrate already shipped; T3.2 owns expression-scope uniqueness/repeated-rule validation. |
| C30-C31 `.join(...)` and Every-Proof-Path Reach Rule | T3.3 | D2 locks `.eq(...)` constraint constructor; D5 assigns join/reach to T3.3. |
| C32 RuleExprInspect minimum surface | T3.5a or T3.5 | D3 locks return shape; D5 allows T3.5 internal split. |
| C33 immutability | T3.1 | D4 locks immutable structural values. |
| C34 structural equality/hash | T3.1 baseline, T3.3 joins | D4 locks equality/hash; join normalization lands with T3.3. |
| C35 single Rule coercion | T3.1 / T3.5 | D1/D4 lock API-boundary coercion; D3 locks inspect return shape. |
| C49-C51 rich inspect descriptors/render | T3.5b if split | D5 assigns ownership to inspect tranche and allows internal split. |
| C58 `.join_by_ports(...)` | T3.4 | D2 defers; D5 assigns a separate slice. |
| C59 inspect.ports / PortInspect | T3.5b if split | D5 assigns ownership to inspect tranche. |

### 2.2 Cross-Doc Blocked

| Item | Required synchronization | Timing |
|---|---|---|
| Track plan T3 commitment count | Change 17/14 drift to the 18 audited commitments/seams: C23-C35, C49-C51, C58, C59 | Stage 3 follow-up before T3.1 blueprint scoped anchor |
| Track plan T3.2 scope | Mark T3.2 as expression-scope validation only because T1.4 shipped `.as_`, `RuleOccurrence`, `RulePortRef`, alias regex | Stage 3 follow-up before T3.1 blueprint scoped anchor |
| Track plan T3.6 | Add docs/examples as an explicit slice | Stage 3 follow-up before T3.1 blueprint scoped anchor |
| Track plan execution lowering | Mark RuleExpr execution lowering as later tranche, not T3.1-T3.6 | Stage 3 follow-up before T3.1 blueprint scoped anchor |
| ADR lifecycle disclaimer mismatch | Current decision docs repeat template text saying adopted stays active, while T1.3 archived an accepted decision with its blueprint | Separate cadence cleanup or Stage 3 governance note; not a T3 implementation blocker |

### 2.3 No Independent Action

| Item | Reason |
|---|---|
| Parent final `factgraph.sdk.Rule` naming | D1 preserves T1.3 staged naming; T5 hard-cut owns final flip. |
| Parent `a.user == b.person` syntax | D2 chooses `.eq(...)` for initial T3; exact `==` syntax is a possible future wrapper decision. |
| Self-join final semantics | D2 assigns to T3.3 blueprint/reach-rule validation; no separate decision needed before T3.3. |
| RuleExprInspect coercion implementation shape | D3 assigns to T3.5 blueprint; return-shape contract already locked. |

### 2.4 Already Aligned

| Item | Evidence |
|---|---|
| T1.4 occurrence substrate | `Rule.as_`, `RuleOccurrence`, `RulePortRef`, alias regex, frozen/hashable DTOs already shipped. |
| T1.2 bridge returns application Rule | `build_application_rule(...)` already returns application protocol Rule and is exported from SDK top-level by T1.3. |
| T1.3 staged SDK namespace | `Rule` legacy, `ApplicationRule` application Rule, `LegacyRule` explicit alias. |
| T2.3 aggregate-bearing Rules | Aggregate substrate/adapters are orthogonal Rule operands for T3. |
| Legacy branch inspect | D3 preserves current legacy dict behavior. |

### 2.5 Deferred / Later Tranche

| Item | Deferral |
|---|---|
| RuleExpr adapter/execution lowering | Later L- or M-class tranche after authoring/inspect stabilizes. |
| Stable cross-process RuleExpr digest | Not in T3; D4 keeps `__hash__` same-process only. |
| Exact parent `==` join syntax | Future wrapper/syntax decision if needed. |
| T5 final top-level `Rule` flip | T5 legacy `.eval` / old-rule hard-cut. |
| Legacy `Inference` migration | Future T5 or separate migration decision. |

## 3. Recommended Blueprint Phase Order

### T3.1: Base RuleExpr Value And Bool Guards

Dependencies:

- D1 public surface and operand boundary.
- D4 structural equality/hash baseline.
- D5 bool guard timing.

Must include:

- `RuleExpr`, `RuleExprError`, `ExplicitBoolError` exported from `factgraph.sdk`.
- Internal `_RuleExpr`, `_AndGroup`, `_OrGroup` not exported.
- `&` / `|` operators.
- `RuleExpr.all(...)` / `RuleExpr.any(...)`.
- AND/OR flattening.
- immutable values.
- equality/hash for join-free expressions.
- application Rule and RuleExpr operand acceptance.
- legacy SDK Rule rejection.
- `RuleExpr.__bool__` and application `Rule.__bool__` raising `ExplicitBoolError`.

### T3.2: Expression-Scope Occurrence Validation

Dependencies:

- T3.1 base RuleExpr tree.
- T1.4 occurrence substrate.

Must include:

- expression-scope alias uniqueness.
- repeated same Rule requires explicit aliases.
- default alias behavior when Rule appears once.
- diagnostics for duplicate aliases and repeated unaliased Rules.

Must not re-ship `.as_`, `RuleOccurrence`, `RulePortRef`, or alias regex validation.

### T3.3: `.join(...)` And Every-Proof-Path Reach Rule

Dependencies:

- D2 join constraint construction.
- D4 join normalization semantics.
- T3.1 / T3.2 RuleExpr tree and occurrence validation.

Must include:

- `RulePortRef.eq(...) -> RuleJoinConstraint`.
- `.join(...)` over AND groups.
- rejection of `.join(...)` on OR groups or single Rules where required.
- Every-Proof-Path Reach Rule validation.
- self-join decision.
- join constraint symmetry and duplicate normalization.

### T3.4: `.join_by_ports(...)`

Dependencies:

- T3.3 join mechanics.

Must include:

- explicit-name-only join expansion.
- missing-port diagnostics.
- fewer-than-two-occurrence diagnostics.
- ambiguous more-than-two-occurrence expansion handling.

### T3.5: RuleExpr Inspect

Dependencies:

- D3 inspect coexistence.
- D2 join constraint shape.
- D4 canonicalization semantics.
- T3.1-T3.3 authored expression shape.

May split:

- T3.5a: core `RuleExprInspect` minimum from D3.
- T3.5b: C49-C51/C59 rich descriptors and D3-deferred `templates`, `port_visibility`, `ports`.

Must preserve legacy SDK Rule / Inference dict inspect behavior.

### T3.6: Docs And Examples

Dependencies:

- T3.1-T3.5 stable public behavior.

Must include:

- staged import examples using `ApplicationRule`, `RuleExpr`, and `build_application_rule`.
- `.eq(...)` join syntax.
- `&` / `|` precedence and parentheses.
- bool guards.
- same-name ports do not auto-join.
- inspect return-shape differences.

### Later Tranche: RuleExpr Execution Lowering

Dependencies:

- T3 authoring and inspect stable.
- New decision/synthesis if execution semantics affect adapters/proof runtime.

## 4. Cadence Reminders For Implementing Blueprints

- T3.1 must be L/M scoped carefully because it touches public SDK exports and application Rule bool behavior.
- Every T3.x blueprint must cite adopted D1-D5 by section.
- No T3.x implementation should change legacy `factgraph.sdk.Rule` semantics unless a superseding T1.3/T5 decision exists.
- D2 `.eq(...)` is the only initial join constraint syntax.
- D4 forbids cross-type `application_rule == rule_expr` equality.
- D5 forbids execution lowering in T3.1-T3.6.
- T3.5 must preserve legacy inspect dict output.
- Track-plan synchronization should happen before T3.1 scoped anchor or as the first doc-only step in the T3.1 blueprint.
- The ADR lifecycle disclaimer mismatch is a governance cleanup item; do not let it block T3 implementation, but record it in the first T3.1 blueprint non-goals or follow-up list.

## 5. Audit Trail Of Stage 2 Closure

| Commit | Artifact | Event |
|---|---|---|
| `1c84dba4` | Stage 1 audit | Draft T3 RuleExpr vs shipped audit |
| `a88cfcd0` | Stage 1 audit | Sharpen Stage 2 framing |
| `2a403550` | D2/D3 | Draft D2/D3 decisions |
| `158a7156` | D2/D3 | P2 framing amendment |
| `735bc93a` | D2/D3 | Adopt D2/D3 |
| `5656726e` | D1/D4 | Draft D1/D4 decisions |
| `4c845615` | D1/D4 | P2 framing amendment |
| `3c898511` | D1/D4 | Adopt D1/D4 |
| `a9ec6046` | D5 | Draft D5 decision |
| `1d2e4c8f` | D5 | P2 framing amendment |
| `81bcec29` | D5 | Adopt D5 |

## 6. Acceptance For This Synthesis

- [x] All audit drift rows and cross-doc seams classified into a bucket.
- [x] Recommended phase order is consistent with D1-D5 dependencies.
- [x] Cadence reminders capture Q-derived constraints.
- [x] Audit trail current as of `81bcec29`.

Lifecycle: this synthesis stays in `workflow/audit/active/` until the final consuming T3 blueprint archives, or until a later synthesis supersedes it.

