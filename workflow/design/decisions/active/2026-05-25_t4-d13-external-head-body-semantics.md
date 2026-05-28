# D13 Decision: T4 External Head Body Semantics

- Status: proposed
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: proposed design constraint; locks how external `head=Rule` bodies participate in T4 RuleExpr execution.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t4-head-closed-head-vs-shipped.md` Q4, F1, F5, F6, F8, and §6 C55 triage.
  - D11 `workflow/design/decisions/active/2026-05-25_t4-d11-scope-head-identity-boundary.md` §4.1, §4.2, §4.3, §4.5, and §4.7.
  - D12 `workflow/design/decisions/active/2026-05-25_t4-d12-declared-port-namespace.md` §4.1-§4.8.
  - Parent design `workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md` §5.1-§5.5 and C52-C55.
  - T3L.3 archived blueprint `workflow/blueprints/archive/2026-05-25_t3l-3-public-dispatch-diagnostics-docs.md` §5.5 and §10.
  - Shipped `src/factgraph/application/protocol/rule_expr_lowering.py:42-134`, `:237-280`, `:320-334`, `:352-385`, `:388-482`, and `:506-536`.
  - Shipped `src/factgraph/application/protocol/rule.py:47-108`.
  - D7 `workflow/design/decisions/active/2026-05-25_t3-later-d7-lowering-plan-shape.md` §4.5-§4.8.
  - D8 `workflow/design/decisions/active/2026-05-25_t3-later-d8-join-lowering-semantics.md` §4.1-§4.11.
- Outputs / Downstream:
  - D14 `Rule.projection(...)` decides projection-head construction using D13 external-head behavior where needed.
  - D15 closed-head validation applies to D13 external-head bodies.
  - Stage 3 T4 synthesis and per-slice blueprints.
- Related:
  - `workflow/design/decisions/active/2026-05-25_t4-d11-scope-head-identity-boundary.md`
  - `workflow/design/decisions/active/2026-05-25_t4-d12-declared-port-namespace.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d8-join-lowering-semantics.md`
- Branch: `v0.2.0-t4-head-closed-head-audit-2026-05-25`
- Depends on: D11 and D12 reviewed.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

T3L.3 intentionally rejected external-head body concatenation:

```text
evaluate(rule_expr, head=external_head)
  -> SDKStoreError("include the head rule as an expression occurrence")
```

That was correct for T3 later. T4 now owns the Head track. Parent C55 says a head Rule is an ordinary Rule body and should not have evaluate-specific grammar restrictions.

D13 decides whether T4 keeps T3L.3's rejection or implements external-head semantics. It also decides how external head atoms interact with D7 branch lowering, D8 join materialization, D12 declared ports, aggregates, and adapter support.

## 2. Scope

This decision locks:

- whether T4 lifts T3L.3 external-head rejection;
- where external head body atoms enter the private lowering/materialization pipeline;
- how external head variables are isolated;
- how head ports connect to D12 declared expression ports;
- materialized atom ordering and provenance categories;
- how external heads interact with OR branches, joins, aggregates, and adapters;
- error buckets for external-head semantic failures.

## 3. Non-Scope

This decision does not lock:

- `Rule.projection(...)` construction; D14 owns it;
- closed-head literal validation; D15 owns it;
- public result-shape replacement for `list[CandidateSet]`;
- T5 `EvaluateResult`, `row.close()`, `Explanation`, or WhyNot;
- adapter grammar expansion;
- public alias-selection syntax such as `head_alias=`;
- public rename syntax for projected ports.

## 4. Decision

### 4.1 T4 lifts T3L.3 external-head rejection

T4 should implement external-head body semantics instead of preserving T3L.3's rejection.

An external head is a supplied application `Rule` that is not the same id + same content digest as exactly one expression occurrence.

D11 identity validation still runs first:

- same id + different digest rejects as stale/conflicting identity;
- same id + same digest + multiple matches rejects as ambiguous per D12;
- same id + same digest + one match remains inline and does not use D13 external-head concatenation;
- different id is an external head.

### 4.2 External head body atoms are conjoined into every executable branch

For each D7/T3L branch, D13 materialization adds the external head body to that branch.

Conceptual branch materialization:

```text
branch body atoms
  + alias-scoped external head body atoms
  + RuleExpr explicit join equality atoms
  + head-port link equality atoms
```

The external head body is applied to every branch, preserving D7 branch count and branch order:

- `a | b` with external head `h` becomes branches `a+h` and `b+h`;
- `a & (b | c)` with external head `h` becomes branches `a+b+h` and `a+c+h`;
- no head body atom is allowed to look through OR branch alternatives or create branch-specific head schemas.

This implements parent C55 without changing RuleExpr authoring semantics.

### 4.3 External head variables are alias-local under a private head alias

External head Rule variables are rewritten before concatenation, exactly as expression occurrences are alias-scoped.

The head alias is private and not user-addressable. It may use an implementation-only label that is not a valid public occurrence alias.

Consequences:

- head internal `Var` names cannot collide with expression occurrence variables;
- head internal `Var` names cannot align ports by name;
- D12's public port-key alignment remains the only alignment path;
- T3.3/T3.4 no-auto-join discipline remains intact.

### 4.4 Head ports link to D12 declared branch sources by equality atoms

For each `head.ports` key, D13 links the external head port variable to the D12-declared expression source for that port in each branch.

Conceptually:

```python
CmpAtom(
    op="eq",
    lhs=head_alias_local_port_var,
    rhs=branch_declared_port_source_var,
)
```

These are head-port link atoms, not RuleExpr authoring joins.

They are produced only after D12 validation proves:

- the head port name exists in the declared-port map;
- every branch can bind that port;
- same-name branch sources are unambiguous or explicitly joined equivalent;
- head `PortType` exactly matches the declared `PortType`.

### 4.5 Head-port link atoms have separate provenance from D8 RuleExpr joins

D13 does not pretend head-port link atoms are user-authored RuleExpr joins.

Implementation should preserve an internal metadata category equivalent to:

```python
@dataclass(frozen=True)
class RuleExprHeadPortLinkMaterialization:
    branch_id: str
    head_port_name: str
    source_occurrence_alias: str
    source_port_name: str
    materialized_atom_index: int
```

Exact helper names are private. The important distinction is:

- D8 `RuleExprJoinMaterialization` tracks explicit user-authored joins;
- D13 head-port link metadata tracks equality atoms inserted to connect an external head to expression output ports.

Future T5 evidence can then explain "join" and "head projection link" differently.

### 4.6 Materialization order is deterministic

For external heads, D13 extends D8's deterministic ordering:

1. expression branch body atoms;
2. alias-scoped external head body atoms;
3. D8 explicit RuleExpr join equality atoms in canonical join order;
4. D13 head-port link equality atoms in sorted head port-name order.

`materialized_atom_index` for both D8 join metadata and D13 head-link metadata is the final 0-based index in this combined branch body.

This order ensures all source variables appear before equality constraints that link them.

### 4.7 Parent C55 ordinary Rule body grammar applies to external head bodies

T4 external head bodies accept the same atom grammar as application `Rule.where`.

D13 does not add evaluate-specific head grammar restrictions:

- `PredAtom`, `CmpAtom`, `InAtom`, `BuiltinAtom`, `NotAtom`, and aggregate-containing allowed Rule atoms remain allowed when valid for `Rule`;
- aggregate atoms remain subject to the shipped T2.3 aggregate rules;
- adapter support remains engine-specific per D9/T3L.2 behavior.

External head bodies containing aggregate atoms make every branch aggregate-containing per §4.2, so the existing D9/T3L.2 PyReason classifier rejects the whole query under the adapter matrix policy.

If an engine cannot support a valid head body atom, the adapter rejection path remains D9/T3L.2/T3L.3 style. D13 does not expand adapter grammar.

### 4.8 External head body constraints are filters, not output schema declarations

Head output shape is still determined by `head.ports.keys`.

External head body atoms function as filters or constraints. They do not declare output columns: only `head.ports.keys` declares output column names. Head body atoms may reference variables present in `head.ports`, adding constraints on those columns, but cannot extend the output schema.

This preserves parent §5.5: ports define output shape; where provides constraints.

### 4.9 External head semantic failures use `RuleExprError`

D13 inherits D11/D12 error buckets:

- stale same-id different digest raises `RuleExprError`;
- ambiguous same-id matches raise `RuleExprError`;
- undeclared head port raises `RuleExprError`;
- head port `PortType` mismatch raises `RuleExprError`;
- malformed external head body after Rule construction raises `RuleExprError`;
- invalid public `head=` type remains `SDKStoreError`;
- adapter rejections remain `SDKStoreError` at the public SDK boundary when they are engine support failures.

D13 does not add a new public error subclass.

## 5. Rejected Alternatives

### Option A: Keep T3L.3 external-head rejection throughout T4

- **Why rejected**: T4 owns Head behavior. Keeping the rejection would leave parent C55 unresolved and make external head Rules unusable beyond the T3 later workaround.

### Option B: Require users to include every head as an expression occurrence

- **Why rejected**: this preserves T3L.3's workaround as the only behavior and makes `head=Rule` less than first-class for distinct projection/filter heads.

### Option C: Concatenate external head atoms once outside the branch list

- **Why rejected**: D7/D9 runtime shape is branch-list based. Head filters must apply to every branch without changing branch identity or output schema.

### Option D: Reuse the head Rule id as a public occurrence alias

- **Why rejected**: head variable isolation is implementation detail and must not collide with user aliases or create a public selector.

### Option E: Link head ports by internal `Var` name

- **Why rejected**: violates C54 and D12. Port keys, not internal vars, are public alignment.

### Option F: Treat head-port link equality atoms as D8 user joins

- **Why rejected**: they are inserted by the head projection mechanism, not authored by the user. Conflating them would mislead future evidence and join diagnostics.

### Option G: Restrict external head bodies to predicate-only atoms

- **Why rejected**: violates parent C55. Adapter-specific unsupported atoms should be rejected by adapter support policy, not by a head-only grammar.

### Option H: Add public `head_alias=` now

- **Why rejected**: D12 already rejects ambiguous same-id inline matches in the current tranche. A selector can be considered later if user demand appears.

## 6. Supporting Evidence

- T3L.3 archived blueprint explicitly deferred external-head body concatenation to the Head track.
- Parent C55 says head.where has no evaluate-specific grammar restriction.
- D7 branch model supports adding atoms to each branch without changing RuleExpr authoring shape.
- D8 already provides equality atom materialization and internal provenance patterns.
- D12 gives D13 a branch-total declared-port map and exact `PortType` compatibility rule.
- T2.3 aggregate substrate already applies to ordinary application Rule bodies.
- D9/T3L.2 adapter matrix already distinguishes supported engines and PyReason rejection.
- D10/T5 boundary requires internal provenance to remain private until a future result/evidence surface.

## 7. Consequences

### 7.1 Downstream unblocking

D13 unblocks:

- D14 projection sugar, because projection heads can rely on D13 external-head mechanics when they are not inline occurrences.
- D15 closed-head validation, because D15 can validate closed external heads against the same head body / port link model.
- Stage 3 T4 synthesis, because T4 now has a concrete external-head answer.

### 7.2 Implementation constraints

Future implementation should:

- extend the private T3L lowering/materialization substrate rather than adding a parallel SDK-only path;
- preserve T3L.3 inline-head behavior for same id + same digest + one match;
- add external head body atoms to every branch;
- add head-port link equality atoms after D8 explicit joins;
- preserve separate provenance for D8 joins and D13 head links;
- keep helper DTOs private;
- keep adapter production files unchanged unless a later blueprint explicitly scopes adapter work.

### 7.3 Stage 3 gating

Stage 3 synthesis must ensure any external-head implementation blueprint tests:

- external head body filters rows;
- external head internal vars do not collide with expression vars;
- head port links use D12 declared ports, not internal vars;
- OR branches all receive head body atoms;
- aggregate-containing head bodies preserve existing aggregate behavior;
- PyReason / adapter unsupported cases reject through existing adapter policy.

## 8. Acceptance Criteria

- [ ] D14-D15 cite D13 for external-head semantics.
- [ ] T4 implementation lifts T3L.3 external-head rejection only after D12 validation is available.
- [ ] External head body atoms are alias-scoped under a private head alias.
- [ ] External head body atoms are added to every branch.
- [ ] Head ports link to branch declared-port sources through equality atoms.
- [ ] D8 join materialization metadata remains distinct from D13 head-link metadata.
- [ ] External head body grammar is ordinary application Rule grammar.
- [ ] Adapter grammar is not expanded by D13.
- [ ] External-head semantic failures use `RuleExprError`; public adapter rejections use the existing `SDKStoreError` boundary.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Decision drafted | T4 Stage 1 audit Q4/F6 and D11/D12 deferred scope mapped to D13. D13 lifts T3L.3 external-head rejection and defines branch-wise alias-scoped head body concatenation plus explicit head-port link atoms. |
| 2026-05-25 | proposed-amend | Claude Step 4.2 v1 follow-up | WC1 aggregate-in-head-body PyReason rejection interaction and WC2 head.ports output-schema wording clarified. |
| 2026-05-25 | reviewed | Claude Step 4.2 v2 clean | WC1 aggregate/PyReason cross-link and WC2 output-schema wording addressed; D13 substrate sound; D14 unblocked. |
