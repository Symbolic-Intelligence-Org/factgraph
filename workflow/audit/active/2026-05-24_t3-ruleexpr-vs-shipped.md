# Audit: T3 RuleExpr vs Shipped Runtime

- Status: complete
- Created: 2026-05-24
- Last Updated: 2026-05-24
- Authority: working triage document; informs but does not lock implementation. Implementation decisions follow only after audit-row review.
- Inputs:
  - Parent design: `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` sections 3.6, 4, 5.9, and 5.10.
  - Track plan: `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md` section 1.2.6 / T3 rows.
  - Shipped source files read completely per Rule 1, listed in section 1.
- Outputs / Downstream:
  - Stage 2 T3 RuleExpr decision docs.
  - Stage 3 T3 RuleExpr synthesis.
  - T3.x per-slice blueprints after synthesis.
- Related:
  - `workflow/blueprints/archive/2026-05-23_t1-4-alias-port-contract.md`
  - `workflow/blueprints/archive/2026-05-23_t1-4-alias-port-contract.audit.md`
  - `workflow/memory/current.md`
- Source intent: compare parent RuleExpr commitments against shipped T1/T2 runtime after T1.4 and T2.3 closure.
- Branch: `v0.2.0-t3-ruleexpr-audit-2026-05-24`

## 1. Scope

Primary surfaces read completely per Rule 1:

| Layer | File | Path / line anchors |
|---|---|---|
| Parent design | Rule-expression essay | `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:160-226`, `:397-699`, `:1298-1306`, `:1484-1533` |
| Track plan | Rule-expression track plan | `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md:115`, `:180-196` |
| Application protocol | Rule DTO and T1.4 occurrence substrate | `src/factgraph/application/protocol/rule.py:1-540` |
| Application protocol | Public protocol exports | `src/factgraph/application/protocol/__init__.py:1-176` |
| SDK top level | Transitional public SDK namespace | `src/factgraph/sdk/__init__.py:1-94` |
| SDK DSL bridge | `build_application_rule` and canonicalization | `src/factgraph/sdk/dsl/application_rule.py:1-308` |
| SDK DSL legacy | Legacy `Rule` / `Inference` / `Query` runtime | `src/factgraph/sdk/dsl/rule.py:1-594` |
| SDK DSL branch | Current explicit branch identity DTO | `src/factgraph/sdk/dsl/branch.py:1-37` |
| SDK DSL package | Public DSL exports | `src/factgraph/sdk/dsl/__init__.py:1-28` |
| SDK store | Current `fg.run`, `fg.evaluate`, and `fg.rules.inspect` behavior | `src/factgraph/sdk/store.py:1-3315` |
| Tests | T1.4 alias/port contract tests | `tests/application/protocol/test_rule.py:130-258` |
| Tests | Current branch inspection tests | `tests/test_branch_identity_rule_inspect.py:1-255` |

Out of scope for this Stage 1 audit:

- Implementing RuleExpr code.
- Choosing final Stage 2 decisions.
- Rewriting docs or examples.
- Changing the T1.3 staged top-level `Rule` decision.
- Adapter lowering for RuleExpr execution.

## 2. Inputs

Parent section 3.6 defines the port and occurrence semantics that T1.4 partially shipped. The nine commitments at lines 188-196 are the closest source of truth for occurrence aliasing, explicit joins, AND-spine reachability, repeated-rule aliasing, occurrence-local joins, unjoined same-name-port inspection, and evidence rendering.

Parent section 4 expands RuleExpr as a user-facing expression layer. The commitment table at lines 680-699 locks C23-C35 and C49-C51:

- C23: `&` / `|` operators and `RuleExpr.all/any` factories.
- C24: Python precedence accepted, docs must explain parentheses for OR.
- C25: AND/OR flattening.
- C26: internal `_RuleExpr`, `_AndGroup`, `_OrGroup` are not public API.
- C27: `RuleExpr.__bool__` and `Rule.__bool__` raise explicit errors.
- C28: occurrence aliasing with `.as_`; default alias is `rule.id`; repeated same Rule needs explicit alias.
- C29: aliases are local to the expression and unique.
- C30: join rules.
- C31: Every-Proof-Path Reach Rule.
- C32: `fg.rules.inspect(expr)` returns `RuleExprInspect` with rich authoring diagnostics.
- C33: RuleExpr values are immutable; `.join` and `.as_` return new values.
- C34: structural equality and same-process hashing normalize commutative AND/OR.
- C35: a single Rule is accepted where RuleExpr is accepted.
- C49-C51: rich occurrence and atom descriptors plus render surfaces.

Parent section 5.9 adds C58, `.join_by_ports(*explicit_names)`, with an explicit-name contract and no silent same-name-port joins. Parent section 5.10 adds C59, `inspect.ports`, a likely T3/T4 seam for later head and visualization work. Lines 1298-1306 distinguish same-process `__hash__` from cross-process content digests, which matters for C34.

Track plan section 1.2.6 marks T3 as L-class because it combines C23-C35 and C49-C51 and requires Stage 1 audit plus multi-decision Stage 2 before per-slice blueprints.

Commitment count note: this audit covers C23-C35 (13 commitments), C49-C51 (3 commitments), plus C58/C59 seams (2 commitments), for 18 audited commitments. The track plan currently contains count drift: line 115 says 17 commitments, while line 182 says 14. This is a track-plan synchronization issue, not an audit coverage gap, and should be resolved in Stage 3 synthesis.

## 3. Triage Table

5-state classification per CADENCE Stage 1:

- **(a) shipped covers** — honors design intent.
- **(b) small gap** — minor move / rename / metadata sync.
- **(c) shape conflict** — semantic or structural mismatch requires decision.
- **(d) genuinely new** — no shipped equivalent.
- **(e) deferred-aligned** — design defers and shipped honors.

### 3.1 A-series: Architectural commitments

| Row | Commitment | Shipped state | Classification | Notes |
|---|---|---|---|---|
| A1 | C23 operators `&` / `|` and `RuleExpr.all/any` | No `RuleExpr` export in `factgraph.sdk` or `factgraph.sdk.dsl`; application `Rule` instances do not support `&` / `|` | (d) genuinely new | Runtime smoke: `r & r` and `r | r` raise Python `TypeError`; no factories exist. |
| A2 | C24 Python precedence accepted and documented | No RuleExpr operators exist | (d) genuinely new | Once `&` / `|` exist, precedence mostly follows Python; docs still need explicit parentheses guidance. |
| A3 | C25 flatten AND/OR groups | No `_AndGroup` / `_OrGroup` exists | (d) genuinely new | Needs canonical construction and equality decisions. |
| A4 | C26 internal `_RuleExpr` / `_AndGroup` / `_OrGroup` hidden | No namespace exists | (d) genuinely new | Need module placement and export decision. |
| A5 | C27 bool guards for RuleExpr and Rule | `bool(application Rule)` is currently truthy because no `__bool__`; legacy DSL `Rule` also has no explicit guard | (c) shape conflict | Adding `Rule.__bool__` is a public behavior change. T3 must decide which Rule class(es) get the guard before T5 final top-level flip. |
| A6 | C28 `.as_` aliasing and default alias `rule.id` | T1.4 shipped `Rule.as_(alias=None)`, `RuleOccurrence`, and `RulePortRef` in application protocol | (b) small gap | Occurrence DTO substrate is present, but RuleExpr repeated-rule alias validation is new. |
| A7 | C29 alias uniqueness local to expression | No expression object exists to own alias scope | (d) genuinely new | Requires RuleExpr validation and error model. |
| A8 | C30 explicit `.join(...)` rules | No join object or constraint representation exists | (d) genuinely new | Also blocked by RulePortRef equality / constraint construction decision. |
| A9 | C31 Every-Proof-Path Reach Rule | No RuleExpr tree or join reachability validator exists | (d) genuinely new | Needs Stage 2 decision for algorithm and diagnostics. |
| A10 | C32 / C49-C51 rich `fg.rules.inspect(expr)` | `fg.rules.inspect` exists but returns legacy dicts for legacy Rule/Inference only | (c) shape conflict | `src/factgraph/sdk/store.py:2088-2089`, `:2907-2964` are current legacy inspect paths. Need coexistence plan. |
| A11 | C33 RuleExpr immutability | T1.4 occurrence DTOs are frozen; no RuleExpr value exists | (d) genuinely new | Implementation can follow frozen dataclass pattern. |
| A12 | C34 structural equality / same-process hash | No RuleExpr value exists; parent distinguishes `__hash__` from content digest at lines 1298-1306 | (d) genuinely new | Needs canonical commutative equality and join-order treatment decision. |
| A13 | C35 single Rule accepted where RuleExpr accepted | No RuleExpr-consuming API exists | (d) genuinely new | Needs coercion boundary decision. |
| A14 | C58 `.join_by_ports(*explicit_names)` | No RuleExpr joins exist | (d) genuinely new | Needs inclusion timing decision: same slice as `.join` or later T3.x. |
| A15 | C59 `inspect.ports` / `PortInspect` | No RuleExpr inspect object exists; current branch inspect surfaces branch atom details only | (d) genuinely new | Likely T3.5 / T4 seam; do not silently include in T3.1. |

### 3.2 I-series: Invariants and protocols

| Row | Invariant | Shipped state | Classification | Notes |
|---|---|---|---|---|
| I1 | T1.4 occurrence DTO substrate | `Rule.as_`, `RuleOccurrence`, and `RulePortRef` shipped in `src/factgraph/application/protocol/rule.py:122-170` and exported at `__init__.py:74` | (a) shipped covers | This is the main substrate T3 can consume. |
| I2 | Public ports are `Rule.ports` keys, not internal Var names | T1.1/T1.4 preserve `ports: Mapping[str, Var]`; T1.4 tests cover same port name with different internal Vars | (a) shipped covers | Parent section 3.6 C54-style contract is already represented in Rule DTO. |
| I3 | Application Rule content digest excludes occurrence aliases | T1.4 tests cover alias-independent content digest | (a) shipped covers | T3 expression digest/equality remains new. |
| I4 | T1.2 bridge produces application Rule | `build_application_rule` returns `factgraph.application.protocol.Rule` at `application_rule.py:46-82` | (a) shipped covers | T3 should use this for SDK-created Rule operands. |
| I5 | SDK top-level staged naming | `factgraph.sdk.Rule` is legacy, `ApplicationRule` aliases application protocol Rule, per T1.3 | (a) shipped covers | T3 examples must not assume final top-level `Rule` flip already happened. |
| I6 | Legacy Branch identity inspect | `Branch` DTO exists and `fg.rules.inspect` reports branch ids / atom ids in tests | (a) shipped covers | T3 inspect must not regress branch identity behavior. |
| I7 | T2.3 aggregate rules remain orthogonal | T2.3a-d touched Rule ports only through existing application Rule validation | (a) shipped covers | T3 should treat aggregate-bearing Rules as normal Rule operands. |

### 3.3 D-series: Discrepancies between current and proposed

| Row | Discrepancy | Current state | Required Stage 2 decision |
|---|---|---|---|
| D1 | Parent examples say `Rule`, but T1.3 keeps `factgraph.sdk.Rule` legacy until T5 | `factgraph.sdk.Rule is factgraph.sdk.dsl.Rule`; `factgraph.sdk.ApplicationRule` is the application Rule | Decide RuleExpr operand/public import story before T5. |
| D2 | `fg.rules.inspect` name is already occupied by legacy inspect dict output | Store inspect accepts legacy SDK Rule/Inference and returns dicts | Decide polymorphic coexistence vs new inspect entry point and object-vs-dict return. |
| D3 | Parent wants `Rule.__bool__` to raise; current Rule values are truthy | Application Rule and legacy SDK Rule have no explicit `__bool__` guard | Decide which classes receive bool guard and in which T3 slice. |
| D4 | Parent join examples use `a.user == b.person`; T1.4 `RulePortRef` is a frozen value object with normal equality semantics | Dataclass equality is used for DTO value equality and hashability | Decide how join constraints are constructed without breaking T1.4 value equality expectations. |
| D5 | Parent wants C34 commutative equality/hashing; current implementation has no RuleExpr canonical form | Only Rule content digest exists, and parent says `__hash__` is same-process only | Decide canonical equality and hash treatment for AND/OR, aliases, and joins. |
| D6 | `RuleExprInspect` rich object conflicts with existing dict inspect style | Current inspect payload is branch-oriented dict | Decide inspect DTO shape and compatibility boundary. |

### 3.4 N-series: Non-discrepancies

| Row | Verified shipped behavior | Evidence |
|---|---|---|
| N1 | T1.4 `Rule.as_()` default alias uses `rule.id` and validates identifier shape | `tests/application/protocol/test_rule.py:130-258` |
| N2 | Missing occurrence port has explicit vs attribute error conventions | `RuleOccurrence.port` and `__getattr__` in `rule.py:151-170` |
| N3 | Application Rule serialization already supports AggregateAtom terms | `rule.py:486-499` |
| N4 | SDK bridge rejects legacy Branch / OR / RuleRef in new application Rule path | `sdk/dsl/application_rule.py:85-147` |
| N5 | Top-level SDK has no accidental RuleExpr surface | `src/factgraph/sdk/__init__.py:1-94`; runtime smoke confirmed no `RuleExpr` / `ExplicitBoolError` |

## 4. Open Questions

Each question should become a Stage 2 decision doc or be folded into a combined decision if tightly coupled.

### Q1. Public RuleExpr surface before T5 final `Rule` flip

T1.3 intentionally keeps `factgraph.sdk.Rule` as the legacy SDK Rule. T3 parent examples assume a final world where "Rule" denotes the application Rule. T3 must decide the interim user-facing import path:

- Use `factgraph.sdk.ApplicationRule` operands only.
- Allow both `ApplicationRule` and application protocol `Rule`.
- Provide a `RuleExpr` factory namespace that clearly rejects legacy SDK `Rule`.
- Defer user-facing examples until T5.

This blocks C23/C35 docs and examples.

### Q2. Join constraint construction over `RulePortRef`

Parent examples use `(a & b).join(a.user == b.person)`. T1.4 `RulePortRef` currently has value equality and hashability. Overloading `RulePortRef.__eq__` to produce a join constraint would break ordinary value equality unless another path is chosen.

Candidate options:

- Keep dataclass equality and use an explicit method, e.g. `a.user.eq(b.person)` (**substrate-preserving**).
- Override equality to produce join constraints and add another equality API for DTO tests (**substrate-breaking**; it changes T1.4 `RulePortRef` value-equality expectations and set/dict behavior).
- Introduce a wrapper from `RuleOccurrence` that is not the DTO itself (**substrate-preserving** if T1.4 DTO equality remains untouched).
- Accept parent `==` syntax and migrate T1.4 equality tests accordingly (**substrate-breaking** unless implemented through a wrapper layer).

This blocks C30 and likely determines the RuleExpr join IR.

### Q3. `fg.rules.inspect` coexistence and return shape

Current `fg.rules.inspect(rule_or_inference)` returns dicts for legacy DSL Rule/Inference. Parent C32 wants `fg.rules.inspect(expr)` to return a `RuleExprInspect` object with rich fields and render helpers.

Decision points:

- Polymorphic same method or separate method.
- Object DTO vs dict payload.
- Whether legacy inspect output remains unchanged.
- Three-way input split: legacy SDK `Rule` / `Inference`, single application `Rule` accepted via C35 coercion, and full `RuleExpr` should each have an explicit return-shape contract.
- How branch inspect and RuleExpr inspect share atom descriptors.

This blocks C32, C49-C51, and C59.

### Q4. Structural equality, hashing, and canonical form

Parent C34 requires semantically equivalent commutative AND/OR groups to be equal and hash-equal in-process. Decisions needed:

- Canonical order for AND/OR children.
- Whether join order is canonicalized.
- Whether occurrence aliases are part of identity.
- How single Rule coercion affects equality.
- Whether content digests are separate from `__hash__`.

This blocks C25, C33, and C34.

### Q5. Slice split and bool-guard timing

The track plan says T3 is L-class and should split into sub-slices. This audit suggests bool guards, join constraints, and inspect are separable risk clusters. Decide initial slice boundaries before coding:

- T3.1 base RuleExpr IR and `&` / `|`.
- T3.2 occurrence alias scope / repeated rule validation. T1.4 already shipped `.as_`, `RuleOccurrence`, `RulePortRef`, and alias regex validation, so this slice is significantly narrower than the original track-plan row.
- T3.3 join constraints and Every-Proof-Path reach.
- T3.4 bool guards.
- T3.5 inspect.
- T3.6 docs/examples.

This blocks Stage 3 synthesis.

### Q6. `.join_by_ports` inclusion timing

C58 can be implemented with `.join` or after `.join`. It carries separate pairwise semantics, explicit-name restrictions, and missing-port diagnostics. Decide whether it is in the same decision as joins or a later slice.

### Q7. Execution lowering boundary

Parent T3 includes authoring and inspection semantics; execution/adapters for composite RuleExpr may be later. Decide whether initial T3 ships authoring-only structures, inspect-only lowering, or execution for one backend.

## 5. Frictions

- **Legacy top-level `Rule` friction**: user-facing examples cannot blindly follow parent final-state syntax until T5 final flip.
- **RulePortRef equality friction**: T1.4 value equality is useful and tested; parent join syntax wants `==` as DSL construction.
- **Inspect shape friction**: existing inspect returns dicts; parent wants richer objects with render helpers.
- **Bool guard friction**: adding `Rule.__bool__` changes behavior for any caller that currently relies on truthiness.
- **Hash/canonical friction**: commutative equality is easy to state but needs precise canonicalization for joins, aliases, and single-rule coercion.
- **Scope-size friction**: T3 covers 18 audited commitments/seams (C23-C35, C49-C51, C58, C59); direct implementation without decisions would reproduce T2.3c-style review churn.

## 6. Cross-doc seams

- **T4/T5 naming seam**: T1.3 final `Rule` flip is deferred to the T5 legacy `.eval` / old-rule hard-cut. T3 must not silently assume it.
- **T4 head integration seam**: C59 `inspect.ports` may feed future head authoring; do not overfit T3 inspect to current Branch inspect only.
- **Adapter execution seam**: T2.3 aggregate adapters are complete, but RuleExpr composition over multiple Rules likely needs separate adapter/evaluation design.
- **Evidence rendering seam**: C49-C51 evidence/render descriptors overlap with later proof UI work. Stage 2 should separate authoring inspect from runtime evidence where possible.

## 7. Recommendations For Stage 2 And Synthesis

Recommended Stage 2 decision docs:

1. **T3-D1 Public surface and operand boundary**
   - Resolve `ApplicationRule` vs final `Rule` naming during the staged T1.3 period.
   - Explicitly decide how legacy SDK `Rule` is rejected or handled.
2. **T3-D2 Join constraint construction**
   - Resolve `RulePortRef.__eq__` conflict and join IR representation.
   - Include `.join_by_ports` timing if tightly coupled.
3. **T3-D3 Inspect coexistence**
   - Resolve `fg.rules.inspect` polymorphism and return shape.
   - Include C49-C51 descriptor shape and render helpers.
4. **T3-D4 Structural equality and hash**
   - Resolve canonical forms, alias participation, and join ordering.
5. **T3-D5 Slice split and bool guard timing**
   - Convert L-class audit outcomes into concrete T3.x slice order.

Recommended Stage 3 synthesis outputs:

- One explicit T3 scope ladder, likely T3.1 through T3.6.
- A cross-slice contract preservation table for T1.1-T1.4 and T2.3a-d.
- A public docs sequence that avoids promising final `Rule` naming before T5.
- A clear "authoring-only vs executable" boundary for initial T3 slices.

Tentative slice order after decisions:

1. T3.1 RuleExpr base IR, `&` / `|`, `RuleExpr.all/any`, flattening, immutability.
2. T3.2 occurrence alias uniqueness and repeated-rule validation. T1.4 already shipped the occurrence DTO substrate, so Stage 3 should narrow this slice to expression-scope validation rather than re-shipping `.as_`.
3. T3.3 join constraints and Every-Proof-Path reach.
4. T3.4 bool guards if not included in T3.1.
5. T3.5 inspect surface.
6. T3.6 docs and examples. This slice is an audit recommendation beyond the current track-plan T3.1-T3.5 list; Stage 3 synthesis should decide whether to sync it into the track plan.
7. Later adapter/evaluation lowering slices if Stage 2 chooses executable RuleExpr. These slices are also beyond the current track-plan T3.1-T3.5 list and require Stage 3 confirmation before blueprinting.

## 8. Audit Method Notes

- This audit was created after the T1 Track and T2.3 AggregateExpr full track were archived and memory-synced.
- The audit uses the full L-class cadence entry point rather than a direct blueprint, per track plan T3 classification.
- Rule 1 source-read discipline was applied to every in-scope shipped source file listed in section 1.
- Runtime smoke was used only to confirm absence/presence claims; file:line citations remain the primary evidence.
- No code or blueprint implementation files were changed by this audit.

## 9. Audit Completeness Checklist

- [x] All in-scope rows triaged.
- [x] All open Qs surfaced.
- [x] All frictions enumerated.
- [x] Out-of-scope explicitly listed.
- [x] Recommendations provided.
