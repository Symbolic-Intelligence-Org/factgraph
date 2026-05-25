# D12 Decision: T4 Declared Port Namespace And Head Alignment

- Status: proposed
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: proposed design constraint; locks the canonical T4 declared-port namespace and C54 head port alignment semantics.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t4-head-closed-head-vs-shipped.md` Q2, F4, F5, WC2, and §6 C54 triage.
  - D11 `workflow/design/decisions/active/2026-05-25_t4-d11-scope-head-identity-boundary.md` §4.1, §4.2, §4.5, and §4.7.
  - Parent design `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §5.3, C54, and C56 interaction.
  - Track plan `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md:210-230`.
  - Shipped `src/factgraph/application/protocol/rule.py:35-39`, `:47-108`, and `:145-185`.
  - Shipped `src/factgraph/application/protocol/rule_expr_inspect.py:36-135`, `:161-172`, `:212-228`, and `:243-257`.
  - Shipped `src/factgraph/application/protocol/rule_expr_lowering.py:42-72`, `:95-134`, `:320-334`, `:352-385`, `:388-439`, and `:448-536`.
  - Shipped `src/factgraph/application/protocol/rule_expr.py:217-236`, `:255-280`, and `:295-330`.
- Outputs / Downstream:
  - D13 external-head body semantics uses D12 head alignment.
  - D14 `Rule.projection(...)` uses D12 declared ports.
  - D15 closed-head validation and inspect utilities use D12 declared ports.
  - Stage 3 T4 synthesis and per-slice blueprints.
- Related:
  - `workflow/design/decisions/active/2026-05-25_t4-d11-scope-head-identity-boundary.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d7-lowering-plan-shape.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d8-join-lowering-semantics.md`
- Branch: `v0.2.0-t4-head-closed-head-audit-2026-05-25`
- Depends on: D11 reviewed.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

Parent C54 states that head alignment is by external port names:

- `head.ports.keys` must be drawn from `expr.declared_ports`;
- internal `Var` names are Rule implementation details;
- same-name ports do not silently join by themselves.

The shipped code has no public `expr.declared_ports` API. It has two relevant substrates:

1. T3.5 inspect derives user-facing `PortInspect` descriptors and `unjoined_same_name_ports`.
2. T3L.1 lowering derives private `RuleExprOccurrenceBinding` / `RuleExprPortBinding` records per occurrence and branch.

D12 decides which substrate is canonical for T4 head validation and how multi-branch / multi-occurrence ambiguity is handled.

## 2. Scope

This decision locks:

- the canonical declared-port definition for T4;
- whether D12 introduces a public `expr.declared_ports` property;
- head `ports` key subset semantics;
- `PortType` compatibility for head alignment;
- same-name multi-occurrence ambiguity rules;
- OR branch / branch-total availability rules;
- error bucket for head port namespace failures.

## 3. Non-Scope

This decision does not lock:

- external-head body concatenation; D13 owns it;
- `Rule.projection(...)` representation; D14 owns it;
- closed-head literal binding algorithm; D15 owns it;
- T5 result/evidence DTOs;
- automatic joins for same-name ports;
- public rename syntax for projected ports;
- adapter grammar changes.

## 4. Decision

### 4.1 T4 declares ports through a private deterministic helper, not a public `expr.declared_ports` property

D12 does not add a public `expr.declared_ports` property to RuleExpr values.

T4 should introduce or specify a private helper category equivalent to:

```python
@dataclass(frozen=True)
class RuleExprDeclaredPort:
    name: str
    port_type: PortType
    branch_sources: tuple[RuleExprDeclaredPortBranchSource, ...]
```

Exact helper names are implementation details. The data categories are binding:

- external public port name;
- `PortType`;
- per-branch source information sufficient to prove each runtime branch can bind the port unambiguously;
- occurrence aliases and source port names used for diagnostics.

The helper is private application/protocol substrate. D14 and D15 may consume it. Public inspect may later expose derived fields, but D12 itself does not create a public RuleExpr API.

### 4.2 Execution declared ports are branch-total, not whole-expression union

For head alignment, a declared port is available only if every D7/T3L branch can bind that port.

This rejects partial OR-branch output:

- If branch `b0` exposes `user` and branch `b1` does not, then `user` is not valid for `head.ports`.
- If all branches expose `user` with compatible `PortType`, then `user` is declared.

Rationale:

- output rows must have the same head port columns for every successful branch;
- `list[CandidateSet]` has no public branch-specific schema wrapper;
- C54's `expr.declared_ports` should mean "safe to project from the expression", not "appears somewhere".

T3.5 `RuleExprInspect.ports` may remain a whole-expression union for user visibility. It is not the canonical execution declared-port set.

### 4.3 Same-name sources must be unambiguous per branch

Within each branch, a head port name is unambiguous when exactly one source port with that name exists in the branch.

If multiple sources with the same public port name exist in a branch, D12 allows the port only when those sources are proven equivalent by explicit RuleExpr join materialization for that port and compatible `PortType`.

Otherwise, the port is ambiguous and invalid for head alignment.

This preserves the T3 rule:

- same-name ports do not auto-join;
- `.join_by_ports(...)` or explicit `.eq(...)` joins provide the required equivalence;
- unjoined same-name ports remain diagnostic hints, not implicit semantics.

### 4.4 `PortType` compatibility is exact `PortType == PortType`

All branch sources for a declared port name must have the same `PortType`.

The head Rule port with that name must also have the exact same `PortType`.

This inherits D8's `PortType` compatibility rule:

- `entity_ref` ports match only the same `entity_type`;
- `value` ports match value ports;
- future `PortType` fields participate in dataclass equality unless a later decision supersedes D12.

If a port name appears as both an entity-ref port and a value port, or as two different entity types, it is not a valid head-alignment declared port.

### 4.5 Head port key alignment is subset-or-equal by public name

For T4, "head.ports keys subset of `expr.declared_ports`" means subset-or-equal under strict validation.

All `head.ports` keys must exist in the D12 declared-port map. Equality is allowed:

```python
Rule.projection(*all_declared_port_names)
```

is valid once D14 defines projection sugar.

No head port key may align by internal `Var` name. Only `ports` mapping keys are considered public names.

### 4.6 Head internal `Var` names never participate in alignment

Head alignment uses:

- `head.ports.keys`;
- `head.port_types`;
- D12 declared-port names and `PortType`s.

It does not use:

- `head.ports[name].name`;
- source Rule internal variable names;
- alias-local execution variable names;
- rendered desc placeholders except for normal `Rule` construction validation.

The shipped `Rule` constructor already requires each head port `Var` to appear in `head.where`; D14 may need a projection-specific representation decision because C56 projection sugar conflicts with current non-empty `Rule.where` invariants.

### 4.7 Multiple same-id inline head matches are ambiguous without a selector

D11 delegates duplicate same-id multi-occurrence matching to D12/D13.

D12 locks the default rule:

- if a supplied head Rule matches more than one expression occurrence by id + content digest, the inline head target is ambiguous;
- T4 v1 rejects that case with `RuleExprError`;
- users must disambiguate by changing the expression shape, using a distinct projection head once D14 exists, or waiting for a later alias-selection feature.

D12 does not introduce a `head_alias=` parameter or public selector syntax.

### 4.8 Head namespace failures use `RuleExprError`

D12 inherits D11's error bucket:

- undeclared head port name raises `RuleExprError`;
- head port `PortType` mismatch raises `RuleExprError`;
- branch-partial declared port raises `RuleExprError`;
- ambiguous same-name source raises `RuleExprError`;
- multiple same-id inline head matches raise `RuleExprError`.

Missing or invalid `head=` type remains `SDKStoreError` per T3L.3/D11.

## 5. Rejected Alternatives

### Option A: Add public `expr.declared_ports` immediately

- **Why rejected**: T4 needs a stable validation substrate first. Public API can be exposed later through inspect/docs after D12-D15 prove the shape.

### Option B: Use T3.5 `RuleExprInspect.ports` as the execution source of truth

- **Why rejected**: inspect ports are a whole-expression union and lose branch-total availability. They are useful user-facing descriptors, not sufficient execution head alignment semantics.

### Option C: Use whole-expression union for head alignment

- **Why rejected**: OR branches could produce rows missing requested head ports. The existing public result shape has no branch-specific schema wrapper to express that.

### Option D: Use intersection by name only and ignore `PortType`

- **Why rejected**: entity-ref/value conflicts and entity-type mismatches would become silent output shape bugs.

### Option E: Auto-join same-name ports for head projection

- **Why rejected**: violates the T3 explicit-join rule and audit gates. Same-name ports are hints until explicitly joined.

### Option F: Permit ambiguous same-name sources and pick deterministic first source

- **Why rejected**: deterministic ambiguity is still ambiguity. It would make head output depend on implementation ordering instead of user-authored joins.

### Option G: Align head by internal `Var` name

- **Why rejected**: directly violates C54's encapsulation principle. Internal vars are private to each Rule.

### Option H: Add `head_alias=` selector in D12

- **Why rejected**: alias selection is new public API. D12 can reject ambiguous multi-match now; a later decision may add explicit selector ergonomics if users need it.

## 6. Supporting Evidence

- Stage 1 audit F4 found no shipped `expr.declared_ports` property.
- Shipped inspect exposes union-like `ports` descriptors and unjoined same-name hints.
- Shipped lowering has branch and occurrence binding data needed for branch-total validation.
- T3L.1/T3L.2 branch lists already preserve branch ids and occurrence aliases.
- D8 already locked exact `PortType` compatibility for join materialization.
- T3.3/T3.4 rejected automatic same-name joins unless users call `.join_by_ports(...)`.
- Parent C54 says alignment is by external port name, not internal var.
- D11 assigns duplicate same-id multi-occurrence matching to D12/D13 while preserving `RuleExprError` bucket inheritance.

## 7. Consequences

### 7.1 Downstream unblocking

D12 unblocks:

- D13 external-head body semantics, because D13 can align external head ports against D12 declared ports.
- D14 projection sugar, because D14 can validate projected port names against D12 declared ports.
- D15 closed-head inspect utilities, because D15 can report unbound ports against the same declared namespace.

### 7.2 Implementation constraints

Future implementation should:

- compute declared ports from private lowering/branch binding data, not from inspect union alone;
- keep helper APIs private unless a later reviewed decision exposes them;
- reject branch-partial and ambiguous same-name sources before materialization;
- reuse D8 join materialization or equivalent join reach data to prove same-name source equivalence;
- keep `RuleExprInspect.ports` backward-compatible unless D15 explicitly extends inspect.

### 7.3 Stage 3 gating

Stage 3 synthesis must ensure any projection or external-head blueprint includes D12 declared-port validation tests before implementing public behavior.

## 8. Acceptance Criteria

- [ ] D13-D15 cite D12 for declared-port semantics.
- [ ] T4 implementation does not add public `expr.declared_ports` unless a later reviewed decision does so.
- [ ] Head port keys align by public name and exact `PortType`, not internal `Var`.
- [ ] Branch-partial port names are rejected for head alignment.
- [ ] Ambiguous unjoined same-name sources are rejected for head alignment.
- [ ] Explicitly joined same-name compatible sources may be treated as equivalent for head alignment.
- [ ] Multiple same-id inline head matches raise `RuleExprError` in T4 v1.
- [ ] Existing `RuleExprInspect.ports` remains compatible as a user-facing union descriptor unless D15 extends it.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Decision drafted | T4 Stage 1 audit Q2/F4 and D11 §4.7 mapped to D12. D12 chooses a private branch-total declared-port helper, exact `PortType` compatibility, no auto-join, and `RuleExprError` for head namespace failures. |

