# D7 Decision: T3 Later RuleExpr Lowering Plan Shape

- Status: proposed
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: proposed design constraint; locks the canonical internal RuleExpr lowering target and AND/OR branch model for the T3 later execution-lowering tranche.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t3-later-execution-vs-shipped.md` Q3, Q4, F3, F6, F7, F8, F10, and §10 D7 mapping.
  - D6 `workflow/design/decisions/active/2026-05-25_t3-later-d6-public-entrypoint-head-dependency.md`.
  - D4 `workflow/design/decisions/active/2026-05-24_t3-d4-structural-equality-hash.md`.
  - D5 `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md` §4.8 execution-lowering deferral.
  - Parent design `workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md` §4.1 and §5.1-§5.4.
  - Shipped `src/factgraph/application/protocol/rule_expr.py:73-236` and `src/factgraph/application/protocol/rule_expr.py:295-330`.
  - Shipped `src/factgraph/application/protocol/derivation.py:21-43` and `src/factgraph/application/derivation_runtime.py:69-139`.
  - Shipped `src/factgraph/core/store/_evaluate.py:33-49` and `src/factgraph/core/store/types.py:8-14`.
- Outputs / Downstream:
  - D8 join lowering semantics.
  - D9 adapter support matrix.
  - D10 evaluation result / evidence boundary.
  - Stage 3 T3 later synthesis and per-slice blueprints.
- Related:
  - `workflow/audit/active/2026-05-25_t3-later-execution-vs-shipped.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d6-public-entrypoint-head-dependency.md`
  - `workflow/design/decisions/active/2026-05-24_t3-d4-structural-equality-hash.md`
- Branch: `v0.2.0-t3-later-execution-audit-2026-05-25`
- Depends on: T3.1-T3.6 archived, Stage 1 audit reviewed clean, and D6 reviewed clean.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

D6 chooses the public entrypoint shape:

```python
fg.eval.evaluate(rule_expr_or_application_rule, *, head=head_rule)
```

D6 also locks that C35 single-application-`Rule` coercion happens at this dispatch entry and that D7 owns the lowering mechanism for same-id/same-digest projection onto an inline head occurrence.

The Stage 1 audit identifies two unresolved D7 questions:

- Q3: what is the canonical internal result of lowering RuleExpr?
- Q4: how do nested AND/OR RuleExpr trees map to executable branches?

Shipped runtime already has `CompiledDerivationPlan`, `CompiledHeadCall`, and `DerivationEvaluateRequest`, and `evaluate_derivation_plans(...)` evaluates those plans by calling `evaluate_store(...)`. Those are downstream runtime shapes, not authoring-layer RuleExpr shapes.

## 2. Scope

This decision locks:

- the canonical internal output type of RuleExpr lowering;
- how a single application `Rule` input is represented after D6 C35 coercion;
- how `_RuleOperand`, `_AndGroup`, and `_OrGroup` lower to branch sets;
- how alias-local variable privacy is represented before D8 join lowering;
- how deterministic branch order and branch identity are assigned;
- how D6 head information is carried forward without importing full T4 Head semantics;
- which facts D8/D9/D10 must consume from the lowering plan.

## 3. Non-scope

This decision does not lock:

- the exact dataclass names or file placement for the future implementation;
- the exact equality atom / variable-unification semantics for joins; D8 owns that;
- adapter support, adapter rejection, or grammar floor; D9 owns that;
- result wrappers, support-artifact schema, WhyNot, proof frame, or evidence mapping; D10/T5 own those;
- full T4 Head / closed-head behavior;
- public `lower(...)` / debug helpers;
- a stable cross-process RuleExpr digest.

## 4. Decision

### 4.1 Canonical lowering target is a private `RuleExprLoweringPlan`

RuleExpr lowers first to a new internal, non-public plan shape, referred to here as `RuleExprLoweringPlan`.

`RuleExprLoweringPlan` is the canonical internal result for T3 later lowering. It is not exported from `factgraph.sdk`, not documented as public API, and not used as a replacement for `RuleExprInspect`.

The plan should be able to materialize existing runtime shapes after D8-D10 decisions, especially `CompiledDerivationPlan` / `DerivationEvaluateRequest`, but those runtime DTOs are not the canonical RuleExpr lowering result.

Rationale:

- `CompiledDerivationPlan` already fits runtime evaluation, but only stores `body_ir`, `heads`, and engine metadata. It does not preserve RuleExpr aliases, occurrence identities, join provenance, or OR-branch origin.
- `RuleExprInspect` preserves authoring information, but it is a read-only projection for users and must not become execution IR.
- A private RuleExpr-specific plan lets D8/D9/D10 consume authoring provenance before the final runtime materialization discards or transforms it.

### 4.2 Minimum plan fields

The future implementation should keep the exact field names private, but D7 locks the minimum information the plan must carry:

```python
@dataclass(frozen=True)
class RuleExprLoweringPlan:
    source_kind: Literal["rule", "rule_expr"]
    head: ApplicationRule
    head_binding: RuleExprHeadBinding
    branches: tuple[RuleExprLoweringBranch, ...]
    occurrence_map: tuple[RuleExprOccurrenceBinding, ...]
    canonical_key: tuple[object, ...]
```

Minimum branch information:

```python
@dataclass(frozen=True)
class RuleExprLoweringBranch:
    branch_id: str
    path: tuple[int, ...]
    occurrence_aliases: tuple[str, ...]
    body_atoms: tuple[object, ...]
    pending_joins: tuple[RuleJoinConstraint, ...]
```

Minimum occurrence binding information:

```python
@dataclass(frozen=True)
class RuleExprOccurrenceBinding:
    alias: str
    rule_id: str
    content_digest: str
    port_bindings: tuple[RuleExprPortBinding, ...]
```

Minimum port-binding information:

```python
@dataclass(frozen=True)
class RuleExprPortBinding:
    occurrence_alias: str
    port_name: str
    port_type: object
    source_var: object
    alias_local_execution_var: object
```

Minimum head-binding information:

```python
@dataclass(frozen=True)
class RuleExprHeadBinding:
    kind: Literal["external", "inline"]
    head_rule_id: str
    head_content_digest: str
    projection_occurrence_alias: str | None
```

`canonical_key` provides stable internal plan identity for cache keying, equality checks in tests, and debug labels. It is derived from the D4 canonical RuleExpr structure plus D6 head-binding category and head identity, not from incidental construction order.

This is a conceptual contract, not a public DTO commitment. Stage 3 blueprints may choose internal helper names, but they must preserve these data categories.

### 4.3 `CompiledDerivationPlan` remains the downstream runtime materialization target

After D8 resolves joins and D9 resolves adapter support, a `RuleExprLoweringPlan` may materialize one or more `CompiledDerivationPlan` values.

D7 locks the direction of travel:

```text
RuleExpr / application Rule
  -> RuleExprLoweringPlan
  -> CompiledDerivationPlan / DerivationEvaluateRequest
  -> evaluate_derivation_plans(...) / evaluate_store(...)
```

D7 does not require every implementation slice to materialize the runtime plan immediately. A first implementation slice may stop at an internal lowering plan if Stage 3 chooses that split. However, implementations must not bypass the `RuleExprLoweringPlan` categories by lowering directly from RuleExpr into adapter-specific strings or adapter-specific rule bodies.

### 4.4 Single application `Rule` input lowers as a one-branch plan

The D6 C35 single-`Rule` input path is represented the same way as a one-rule RuleExpr:

- `source_kind="rule"`;
- one occurrence binding using the same aliasing rules as T3.1 C35 coercion;
- one branch with that occurrence's alias-scoped body atoms;
- no pending joins;
- D6 head binding carried separately.

This avoids a parallel execution path for bare application `Rule` values and keeps public behavior aligned with T3.5 inspect, where application Rule inspect is a one-element AND group.

### 4.5 Occurrence lowering namespaces variables by occurrence alias before concatenation

Rule internals may reuse `Var` names across distinct rules. RuleExpr composition must not turn same-named private variables into joins.

Therefore each `_RuleOperand` lowers to alias-scoped copies of its `rule.where` atoms before any AND concatenation:

```text
occurrence alias "a", Var("u") -> alias-local execution variable for ("a", "u")
occurrence alias "b", Var("u") -> alias-local execution variable for ("b", "u")
```

The plan must keep a port-binding map from each declared `RulePortRef` to its alias-local execution variable. D8 consumes that map when deciding whether explicit joins lower to equality atoms, variable unification, or another internal construct.

This lock is the execution counterpart of T3.3/T3.4's "same-name ports do not auto-join" discipline.

The concrete alias-local variable representation is an implementation detail for Stage 3. It may be a renamed `Var`, wrapper object, or another runtime-local identity as long as equality between distinct occurrence variables cannot happen by private source variable name alone.

### 4.6 AND lowers by cartesian product over child branch sets

Each expression node lowers to a branch set:

```python
def lower(expr) -> tuple[RuleExprLoweringBranch, ...]:
    if isinstance(expr, _RuleOperand):
        return (lower_operand(expr),)
    if isinstance(expr, _AndGroup):
        return lower_and(expr)
    if isinstance(expr, _OrGroup):
        return lower_or(expr)
```

For `_AndGroup`, D7 chooses cartesian-product branch composition:

```python
def lower_and(group):
    child_sets = [lower(child) for child in canonical_child_order(group.children)]
    branches = []
    for product in cartesian_product(*child_sets):
        branches.append(
            concat_branches(
                product,
                pending_joins=group.joins,
            )
        )
    return tuple(branches)
```

Consequences:

- `a & b` yields one branch containing alias-scoped atoms from `a` and `b`.
- `a & (b | c)` yields two branches: `a+b` and `a+c`.
- `(a | b) & (c | d)` yields four branches.
- Joins attached to the current AND group are attached to every product branch as `pending_joins`; D8 decides how those joins become executable constraints.

### 4.7 OR lowers by concatenating alternatives, not by multiplying siblings

For `_OrGroup`, D7 chooses branch alternatives:

```python
def lower_or(group):
    branches = []
    for child in canonical_child_order(group.children):
        branches.extend(lower(child))
    return tuple(branches)
```

Consequences:

- `a | b` yields two branches, one per alternative.
- `(a & b) | c` yields two branches: `a+b` and `c`.
- OR itself never carries joins because shipped `_OrGroup.join(...)` and `_OrGroup.join_by_ports(...)` reject and instruct authors to distribute joins into AND branches.

### 4.8 Branch order and branch ids are deterministic

Branch ids are internal but must be deterministic:

- branch ids use the final branch order, e.g. `b0`, `b1`, `b2`;
- branch order is derived from the canonical RuleExpr child ordering used for equality/hash, not incidental Python construction order;
- branch `path` records the canonical traversal path so D10 can map future support artifacts back to RuleExpr alternatives.

This avoids semantically equal expressions producing different support labels or cache keys solely because operands were written in a different order.

### 4.9 Empty branches are impossible unless a future decision explicitly adds them

Shipped `RuleExpr.all(...)` / `RuleExpr.any(...)` reject empty operand lists, and application `Rule` bodies are AND-only rule bodies. D7 therefore treats empty branch sets as an internal error, not a meaningful execution value.

If a future T4/T5 decision needs identity rules, empty heads, or empty proof branches, that decision must explicitly supersede this D7 constraint.

### 4.10 Head binding is carried in the plan but full head execution semantics remain outside D7

`RuleExprLoweringPlan` carries D6 head information in `head` and `head_binding`.

Minimum head-binding categories:

- external head: `head` supplied only through the D6 `head=` keyword;
- inline head: same id + same content digest as an occurrence already present in the expression body;
- projection target: optional occurrence alias for inline heads.

D7 locks the representation boundary only. It does not decide:

- whether the head rule's own body atoms are concatenated with RuleExpr body atoms;
- whether head projection lowers through `CompiledHeadCall`, `head_spec`, or both;
- closed-head behavior;
- evidence mapping for head projection.

Those remain Stage 3/D8/D10/T4 responsibilities unless a later decision supersedes D7.

Although D7 does not choose final head execution semantics, the `head_binding` category constrains downstream planning: external heads require Stage 3 or a later decision to decide whether and how to concatenate head body atoms, while inline projection targets give downstream lowering an occurrence alias that is already represented in the RuleExpr body.

### 4.11 RuleExprInspect is explicitly not execution IR

Implementation may use inspect-like helper logic for diagnostics, but `RuleExprInspect`, `OccurrenceInspect`, `AtomDescriptor`, and `PortInspect` are not lowering-plan fields and are not runtime IR.

If diagnostics need render strings, they should derive them from the private lowering plan or call inspect at the edge. Execution must not depend on user-facing inspect DTO shape.

### 4.12 Plan-construction error bucket

D7 does not introduce a new error subclass.

Plan-construction errors use `RuleExprError` when they are about RuleExpr lowering invariants, including:

- empty branch sets under §4.9;
- occurrence alias collisions or alias-local variable binding failures under §4.5;
- missing or malformed plan categories from §4.2.

This extends D6 §4.6's Q9 disposition for the D7 scope. Adapter-time rejections, engine grammar failures, and per-engine error policy remain D9 scope.

## 5. Rejected Alternatives

### Option A: Lower directly to `CompiledDerivationPlan` as the canonical result

- **Why rejected**: `CompiledDerivationPlan` is the right downstream runtime shape, but it does not carry enough RuleExpr provenance for D8 joins or D10 evidence. Making it canonical would force provenance into ad hoc side channels later.

### Option B: Lower to transient derivation dict payloads

- **Why rejected**: derivation dicts are a legacy/public interchange shape around current SDK evaluation. They are too loose for alias-local variable privacy, branch provenance, and D8/D9 validation.

### Option C: Lower separately per adapter

- **Why rejected**: adapter-specific lowering would duplicate AND/OR distribution and join semantics across native, Souffle, ProbLog, and PyReason. D9 should decide adapter support after D7/D8 define one shared semantic plan.

### Option D: Use `RuleExprInspect` as the plan

- **Why rejected**: inspect DTOs are public authoring projections. They intentionally include user-facing render contracts and discoverability hints, not execution lowering invariants.

### Option E: Interpret RuleExpr recursively at evaluation time without a plan

- **Why rejected**: it would bypass existing derivation runtime, make adapter parity harder, and leave D10 without stable branch / occurrence provenance.

### Option F: Represent OR as multiple public evaluation calls

- **Why rejected**: it would make OR branch handling observable through repeated runtime calls and complicate result/evidence ordering. The branch set should stay internal and deterministic.

## 6. Supporting Evidence

- Shipped `_RuleExpr` equality and hash are canonicalized, with `_canonical_children(...)` sorting child canonical forms.
- Shipped `_AndGroup.join(...)` normalizes joins and validates direct AND reach; D7 can carry `pending_joins` without re-deciding reach.
- Shipped `_OrGroup.join(...)` and `_OrGroup.join_by_ports(...)` reject; D7 therefore does not need to support joins attached to OR nodes.
- Shipped `CompiledDerivationPlan` requires non-empty `heads` and has `body_ir` but no RuleExpr provenance fields.
- Shipped `evaluate_derivation_plans(...)` flattens `CandidateSet` results from one or more compiled plans without an application-side wrapper.
- Shipped `evaluate_store(...)` consumes `where`, `head_vars`, `target_pred_id`, and optional `head`; it has no RuleExpr object boundary.
- D5 §4.8 intentionally deferred execution lowering until after T3.1-T3.6 authoring and inspect were stable; D7 is the first Stage 2 decision consuming that deferral.

## 7. Consequences

### 7.1 Downstream unblocking

This decision unblocks:

- D8: consumes alias-scoped port bindings and `pending_joins`.
- D9: consumes the branch model and can decide which engines support branch-list WhereIR or require rejection/splitting.
- D10: consumes branch ids, paths, and occurrence mappings when deciding evidence/result boundaries.
- Stage 3 synthesis: can split implementation into internal plan construction, join materialization, adapter support, and public dispatch slices.

### 7.2 Required D8 follow-up

D8 must decide:

- how `pending_joins` become executable constraints;
- whether D8 uses equality atoms, variable unification, or plan-level constraints;
- how duplicate normalized joins are represented after lowering;
- how join errors reference D7 branch ids and occurrence aliases.

### 7.3 Required D9 follow-up

D9 must decide:

- whether each engine supports the D7 branch model directly;
- whether a D7 branch set materializes to one branch-list `CompiledDerivationPlan`, multiple compiled plans, or a rejected engine path;
- how adapter grammar differences interact with alias-scoped variables and aggregate atoms.

### 7.4 Required D10 follow-up

D10 must decide:

- whether public results remain existing `CandidateSet` values;
- whether any support/evidence metadata exposes D7 branch ids, occurrence aliases, or joins;
- how much provenance must be preserved for future T5 EvaluateResult / WhyNot.

## 8. Acceptance Criteria

- [ ] D8 cites D7 and uses `pending_joins` plus alias-scoped port bindings as its input boundary.
- [ ] D9 cites D7 and decides branch-list vs multi-plan vs rejection behavior per engine.
- [ ] D10 cites D7 and decides whether branch/occurrence provenance is public, internal, or deferred.
- [ ] Future implementation blueprints introduce no public SDK export for `RuleExprLoweringPlan`.
- [ ] Future implementation blueprints keep RuleExprInspect out of execution IR.
- [ ] Future implementation blueprints preserve same-name-port no-auto-join by alias-scoping occurrence variables before AND concatenation.
- [ ] Future implementation blueprints treat OR as deterministic branch alternatives, not repeated public evaluation calls.
- [ ] Future implementation blueprints keep full T4 Head / closed-head behavior out of D7-owned plan construction.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Decision drafted | D7 chooses a private `RuleExprLoweringPlan` as canonical internal lowering target, with deterministic branch sets for AND/OR lowering and existing `CompiledDerivationPlan` reserved as downstream runtime materialization. |
| 2026-05-25 | proposed-amend | Step 4.2 v1 precision amendments | Defined minimum `RuleExprPortBinding` / `RuleExprHeadBinding` categories; documented `canonical_key`; added D7 plan-construction error bucket; clarified alias-local variable representation and head-binding downstream consequences. |
| 2026-05-25 | reviewed | Claude Step 4.2 v2 clean | WC1/WC2/WC4 plus N1-N3 addressed; D7 lowering plan categories and Q9 plan-construction error bucket reviewed clean; D8 unblocked. |
