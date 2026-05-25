# Task Blueprint: T4.1 Head Identity + Declared-Port Foundation

- Status: scoped
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Class: M (predicted)
- Related Modules:
  - `src/factgraph/application/protocol/rule.py`
  - `src/factgraph/application/protocol/rule_expr.py`
  - `src/factgraph/application/protocol/rule_expr_lowering.py`
  - `src/factgraph/application/protocol/rule_expr_inspect.py`
  - `src/factgraph/sdk/store.py`
  - `tests/application/protocol/test_rule_expr_lowering.py`
  - `tests/application/protocol/test_rule_expr_head_validation.py` (new, expected)
  - `tests/sdk/test_rule_expr_evaluate.py`
- Related Docs:
  - `workflow/audit/active/2026-05-25_t4-head-closed-head-vs-shipped.md`
  - `workflow/audit/active/2026-05-25_post-q-t4-head-closed-head-synthesis.md`
  - `workflow/design/decisions/active/2026-05-25_t4-d11-scope-head-identity-boundary.md`
  - `workflow/design/decisions/active/2026-05-25_t4-d12-declared-port-namespace.md`
  - `workflow/design/decisions/active/2026-05-25_t4-d13-external-head-body-semantics.md`
  - `workflow/design/decisions/active/2026-05-25_t4-d14-rule-projection-sugar.md`
  - `workflow/design/decisions/active/2026-05-25_t4-d15-closed-head-inspect.md`
  - `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md`
  - `workflow/blueprints/archive/2026-05-25_t3l-1-internal-lowering-native.md`
  - `workflow/blueprints/archive/2026-05-25_t3l-2-adapter-matrix-parity.md`
  - `workflow/blueprints/archive/2026-05-25_t3l-3-public-dispatch-diagnostics-docs.md`
- Audit Log:
  - [2026-05-25_t4-1-head-identity-declared-port-foundation.audit.md](./2026-05-25_t4-1-head-identity-declared-port-foundation.audit.md)

## 1. Problem

T3L.3 shipped public RuleExpr execution through `fg.eval.evaluate(rule_expr_or_application_rule, head=...)`, but its head handling is deliberately narrow: inline heads work, external heads are rejected, and there is no branch-total declared-port validation foundation.

T4 Stage 1, D11, D12, and Stage 3 synthesis assign T4.1 to build the shared foundation before T4.2 changes external/projection behavior:

- existing-head identity must be validated by `(id, content_digest)`;
- same id + same digest + different version must warn and proceed;
- same id + different digest must fail as head/expression semantic validation;
- declared ports must be computed privately and branch-totally, not as a public RuleExpr property;
- head ports must align by public port name and exact `PortType`;
- same-name sources must be rejected unless explicit D8 join materialization proves equivalence;
- public success remains existing `list[CandidateSet]`.

Canonical drivers:

- T4 Stage 3 synthesis section 3 assigns T4.1 to "Head Identity + Declared-Port Foundation".
- D11 section 4.1-4.7 locks T4 scope, existing-head identity, warning behavior, error buckets, and T4/T5 separation.
- D12 section 4.1-4.8 locks the private branch-total declared-port helper and head namespace validation.
- D6 section 4.6 and T3L.3 preserve SDK call-shape errors as `SDKStoreError`.
- T3L.1/T3L.2 provide private lowering branch, occurrence, port binding, join materialization, and adapter substrate.
- T3L.3 provides the public dispatch insertion point and public result boundary.

This slice is M-class because it touches shared private lowering validation, public SDK evaluation behavior for stale head identity, focused tests, and foundation contracts consumed by T4.2/T4.3. It is not L-class because Stage 1-3 already settled the scope split and T4.1 excludes external-head body concatenation, projection sugar, closed-head inspect utilities, and T5 result/evidence surfaces.

M-to-L triggers:

- implementing external-head body concatenation;
- adding `Rule.projection(...)`;
- adding `inspect.is_closed` or `inspect.unbound_ports`;
- creating a public `expr.declared_ports` API;
- changing public success away from `list[CandidateSet]`;
- exporting head/declared-port DTOs or adding a public error subclass;
- changing adapter grammar or T5 evidence/result surfaces.

If any trigger appears during Step 4.6 or implementation, pause for a reviewed blueprint amendment before code.

## 2. Goals

1. Add private T4 head validation substrate for RuleExpr lowering plans:
   - classifies inline vs external head state using D11 identity rules;
   - widens private occurrence metadata with rule version, or adds equivalent private lookup data, so D11 version mismatch warnings can compare the supplied head version to the matched occurrence version;
   - validates stale same-id/different-digest heads before T3L.3's external-head rejection;
   - emits D11 version mismatch warnings for same id + same digest + different version.

2. Add private branch-total declared-port computation:
   - declared ports exist only when every D7/T3L branch can bind the port;
   - data includes public port name, `PortType`, branch sources, occurrence alias, source port name, and source execution var diagnostics;
   - helper remains private to application protocol/lowering code.

3. Add D12 head port namespace validation:
   - every `head.ports` key must exist in the private declared-port map;
   - `head.port_types[name]` must exactly equal the declared `PortType`;
   - internal `head.ports[name].name` and source internal var names do not participate in alignment.

4. Add D12 same-name ambiguity handling:
   - per branch, exactly one source for a port name is unambiguous;
   - multiple same-name sources are valid only when explicit D8 join materialization proves equivalence for that public port name and all `PortType`s match;
   - otherwise raise `RuleExprError`.

5. Preserve T3L.3 public behavior outside the T4.1 foundation:
   - external heads still raise the T3L.3 public `SDKStoreError` until T4.2;
   - public result remains `list[CandidateSet]`;
   - legacy SDK `Inference` / derivation dict paths remain unchanged;
   - adapter behavior remains unchanged.

6. Add focused tests for D11/D12 foundation behavior:
   - same id + same digest inline head still evaluates;
   - same id + same digest + different version warns once and proceeds;
   - same id + different digest raises `RuleExprError`;
   - undeclared head port raises `RuleExprError`;
   - branch-partial declared port raises `RuleExprError`;
   - same-name ambiguity raises unless explicit `.eq(...)` / `.join_by_ports(...)` materializes equivalence;
   - `PortType` mismatch raises `RuleExprError`.

## 3. Non-goals

- No external-head body concatenation. T4.2 owns D13.
- No `Rule.projection(...)`. T4.2 owns D14.
- No closed-head validator, `inspect.is_closed`, or `inspect.unbound_ports`. T4.3 owns D15.
- No public `expr.declared_ports` property.
- No public head classification, declared-port, or projection DTO export.
- No public result wrapper, `EvaluateResult`, `EvaluateRow`, Explanation, WhyNot, `row.close()`, or `fg.eval.explain(...)`.
- No `CandidateSet`, `SupportArtifact`, `EvidenceEnvelope`, `CompiledDerivationPlan`, or `DerivationEvaluateRequest` shape change.
- No adapter production file edits or grammar expansion.
- No projection rename syntax.
- No T1.3 final SDK `Rule` hard-cut.
- No new public error subclass.
- No mutation of RuleExpr authoring, inspect return shape, equality/hash, joins, or `join_by_ports` syntax.

## 4. Current Context

### 4.1 Application Rule identity and port substrate

`src/factgraph/application/protocol/rule.py` already provides the Head substrate:

- `PortType` is a frozen dataclass at lines 35-39.
- `Rule` fields `id`, `where`, `ports`, `version`, and `desc` are lines 47-55.
- `Rule.__post_init__` requires non-empty `where` and non-empty `ports` at lines 57-66.
- `Rule.__post_init__` validates each port key and ensures the `Var` appears in `where` at lines 80-87.
- `Rule.port_types` exposes inferred `PortType` values at lines 93-99.
- `Rule.content_digest` is deterministic over ports and where atoms at lines 101-108.

T4.1 should consume these fields. It must not relax `Rule` construction invariants.

### 4.2 RuleExpr lowering substrate

`src/factgraph/application/protocol/rule_expr_lowering.py` provides private DTOs and helpers:

- `RuleExprPortBinding` records occurrence alias, public port name, `PortType`, source `Var`, and alias-local execution `Var` at lines 42-58.
- `RuleExprOccurrenceBinding` records alias, rule id, content digest, and port bindings at lines 61-72.
- `RuleExprHeadBinding` is currently `Literal["external", "inline"]` at lines 75-92.
- `RuleExprLoweringBranch` records branch id, path, occurrence aliases, body atoms, and pending joins at lines 95-110.
- `RuleExprLoweringPlan` records source kind, head, head binding, branches, occurrence map, and canonical key at lines 113-134.
- `RuleExprJoinMaterialization` records branch id, join key, left/right occurrence/port names, and materialized atom index at lines 137-150.

Existing plan building is at lines 320-334. It assigns branch ids, creates the occurrence map, and calls `_head_binding(...)`.

Current `_head_binding(...)` at lines 506-525 only treats same id + same digest as inline; same id + different digest falls through to external. T4.1 must add the D11 stale-head semantic error before that fallback is exposed as the T3L.3 external-head `SDKStoreError`.

### 4.3 Branch and join substrate

RuleExpr branch lowering and join materialization already expose the data D12 needs:

- `_lower_operand(...)` rewrites body atoms and creates one `RuleExprPortBinding` per rule port at lines 352-385.
- `_lower_and(...)` builds cartesian branch products and carries pending joins at lines 388-401.
- `_lower_or(...)` creates alternative branches at lines 404-413.
- `_concat_branches(...)` combines body atoms, occurrence aliases, paths, and pending joins at lines 416-439.
- `_assign_branch_ids(...)` creates deterministic `b{idx}` branch ids at lines 442-445.
- `_materialize_branch(...)` deduplicates pending joins, resolves endpoints, checks exact `PortType`, appends equality atoms, and records `RuleExprJoinMaterialization` at lines 448-482.

T4.1 declared-port validation should reuse this private substrate. It should not depend on `RuleExprInspect.ports`, which D12 keeps as user-facing union visibility rather than execution truth.

### 4.4 RuleExpr authoring and inspect boundaries

`src/factgraph/application/protocol/rule_expr.py` has explicit join semantics:

- `_expand_join_by_ports(...)` expands public port-name joins into pairwise `.eq(...)` constraints at lines 255-272.
- `_port_refs_for_name(...)` selects references for direct AND operands at lines 275-280.
- `_validate_join_reach(...)` keeps joins on the direct AND spine at lines 295-307.
- `_validate_endpoint_matches_operand(...)` checks source rule port, `Var`, and `PortType` at lines 318-330.
- `_rule_identity(...)` returns `(id, content_digest)` at lines 333-334.

`src/factgraph/application/protocol/rule_expr_inspect.py` has public inspect DTOs:

- `PortInspect` is lines 36-50.
- `RuleExprInspect` fields are lines 89-117.
- `RuleExprInspect.ports` is lines 133-135.
- `_inspect_rule_expr(...)` fills occurrences, joins, unjoined same-name hints, and `_ports` at lines 161-172.

T4.1 should not change inspect fields. T4.3 owns inspect extensions.

### 4.5 Public SDK dispatch boundary

`src/factgraph/sdk/store.py` currently owns public RuleExpr evaluation:

- `SDKStore.evaluate(...)` rejects removed kwargs, parses registry/engine/semantics, and dispatches RuleExpr inputs at lines 2210-2240.
- legacy derivation-like objects continue through `to_authoring_payload` at lines 2241-2257.
- structured derivation dicts continue through lines 2258-2272.
- fallback lower-level evaluation remains lines 2273-2286.
- `_evaluate_rule_expr_input(...)` validates one input and `head=`, resolves engine/semantics, lowers application Rule / RuleExpr, rejects external heads, and evaluates at lines 2323-2387.

T4.1 should preserve these public dispatch paths. It may call the new private validation helper before the existing external-head rejection so D11/D12 semantic failures surface as `RuleExprError`.

## 5. Proposed Shape

### 5.1 Private helper location

Implement T4.1 in `src/factgraph/application/protocol/rule_expr_lowering.py` as private substrate consumed by SDK dispatch and future T4.2/T4.3:

- add private frozen DTOs for declared-port data if needed;
- add private helper(s) for head validation and declared-port computation;
- keep `__all__: list[str] = []`;
- do not add protocol exports.

Suggested helper categories:

```python
RuleExprDeclaredPort
RuleExprDeclaredPortBranchSource
RuleExprHeadValidation
_validate_rule_expr_head_foundation(plan) -> RuleExprHeadValidation
_declared_ports_for_rule_expr_plan(plan) -> tuple[RuleExprDeclaredPort, ...]
```

Exact names may differ. The data categories and private boundary are binding.

T4.1 may widen `RuleExprOccurrenceBinding` with a private `rule_version: str | None` field, or keep equivalent private occurrence-version lookup data, because D11 warning messages require both the supplied head version and matched occurrence version. That version metadata must remain warning-only and must not enter canonical identity, hash, join, or branch ordering semantics.

### 5.2 D11 identity validation

Head validation must inspect the plan occurrence map before the T3L.3 external-head rejection.

States:

1. No occurrence has `rule_id == head.id`: external head for T4.2; T4.1 leaves existing SDKStoreError behavior unchanged after declared-port validation policy is satisfied or skipped.
2. Exactly one occurrence has same id + same content digest + same version: inline existing head.
3. Exactly one occurrence has same id + same content digest + different version: inline existing head, emit `warnings.warn(..., UserWarning)` once per validation invocation.
4. One or more occurrences have same id + different content digest: raise `RuleExprError`.
5. More than one occurrence matches same id + same content digest: raise `RuleExprError` for ambiguous inline head, per D11 section 4.7 and D12 section 4.7 multi-occurrence ambiguity handling.

Version is warning-only metadata. It must not enter content digest, equality, hashing, canonical key, or join behavior.

Warning message minimum fields:

- head id;
- supplied head version;
- matched occurrence version;
- statement that id + content digest matched.

### 5.3 Branch-total declared-port computation

Compute declared ports from `RuleExprLoweringPlan.branches` and `occurrence_map`.

For each branch:

1. Gather all `RuleExprPortBinding` records whose `occurrence_alias` appears in the branch.
2. Group by public `port_name`.
3. If a group has one source, it is branch-valid.
4. If a group has multiple sources, it is branch-valid only when:
   - all sources have equal `PortType`;
   - explicit D8 join materialization or equivalent pending-join endpoint reach proves all same-name sources equivalent for that branch.
5. Otherwise the port is ambiguous for that branch.

A declared port exists for the whole expression only when every branch has a branch-valid source for that public name and all branch-valid sources share the exact same `PortType`.

Branch-partial ports are invalid for head alignment.

### 5.4 Same-name equivalence proof

D12 allows same-name multi-source ports only when user-authored joins prove equivalence.

T4.1 implementation may use either:

- `RuleExprJoinMaterialization` records from materializing branch joins; or
- an equivalent private resolver over branch pending joins that uses the same D8 canonical endpoint and `PortType` checks.

The proof must count both direct `.eq(...)` joins and `.join_by_ports(name)` expansions when they materialize same-name endpoint joins.

The proof must not:

- auto-join same-name ports;
- pick a deterministic first source;
- infer equality from same variable names;
- infer equality across OR branches.

### 5.5 Head port namespace validation

For any supplied head Rule:

- every `head.ports` key must exist in the private declared-port map;
- the declared `PortType` must exactly equal `head.port_types[name]`;
- alignment uses public port keys only;
- `head.ports[name].name`, source internal var names, alias-local execution var names, and desc placeholders do not participate in alignment.

Failures raise `RuleExprError`.

This validation should be available before T4.2 so external/projection heads can consume the same helper later. T4.1 should avoid changing external-head execution behavior: external heads still fail with the T3L.3 SDKStoreError until T4.2 lifts that rejection.

### 5.6 Public SDK integration

`SDKStore.evaluate(...)` should stay structurally unchanged except for calling the private T4.1 validation helper inside `_evaluate_rule_expr_input(...)` after lowering and before the existing external-head rejection.

Validation ordering:

1. Identity state 4 (same id + different digest) and state 5 (ambiguous same-id same-digest matches) raise `RuleExprError` before the external-head check.
2. Identity state 3 (same id + same digest + different version) emits `UserWarning` and proceeds.
3. Identity state 1 (external head) runs declared-port validation per §5.5; invalid declared-port alignment raises `RuleExprError`, and valid alignment falls through to the existing T3L.3 external-head `SDKStoreError`.
4. Identity state 2 (inline existing head) runs declared-port validation per §5.5 and proceeds when valid.
5. The T3L.3 external-head `SDKStoreError` remains the final rejection for external-head body concatenation until T4.2.

Public behavior:

- missing/invalid `head=` remains `SDKStoreError`;
- stale same-id/different-digest head raises `RuleExprError`;
- ambiguous inline head raises `RuleExprError`;
- version mismatch emits `UserWarning` and proceeds;
- undeclared head port, branch-partial port, same-name ambiguity, and `PortType` mismatch raise `RuleExprError`;
- external head body concatenation still raises the existing T3L.3 `SDKStoreError`.

### 5.7 Tests

Expected test coverage:

- focused private helper tests in a new `tests/application/protocol/test_rule_expr_head_validation.py`;
- narrow public SDK tests added to `tests/sdk/test_rule_expr_evaluate.py` only where public error/warning behavior is observable;
- preservation suites from T3.1-T3.6 and T3L.1-T3L.3.

Test scenarios:

- inline existing head still evaluates successfully;
- same id + same digest + different version emits one `UserWarning`;
- same id + different digest raises `RuleExprError`;
- duplicate same-id same-digest occurrences raise `RuleExprError`;
- head port missing from branch-total declared map raises `RuleExprError`;
- branch-partial OR port raises `RuleExprError`;
- same-name ambiguity raises `RuleExprError`;
- same-name ambiguity is allowed when `.eq(...)` or `.join_by_ports(...)` proves equivalence;
- exact `PortType` mismatch raises `RuleExprError`;
- external-head body concatenation still raises the T3L.3 `SDKStoreError` until T4.2.

### 5.8 Preemptive scope locks

Do not:

1. implement external-head body concatenation;
2. add `Rule.projection(...)`;
3. add closed-head validator or inspect fields;
4. add public `expr.declared_ports`;
5. export new head/declared-port DTOs;
6. add a new public error subclass;
7. change public success result shape from `list[CandidateSet]`;
8. change `CandidateSet`, `SupportArtifact`, `EvidenceEnvelope`, `CompiledDerivationPlan`, or `DerivationEvaluateRequest` shapes;
9. edit adapter production files;
10. expand PyReason Form 2 grammar;
11. change legacy SDK `Inference` / derivation dict evaluation behavior;
12. change RuleExpr authoring / inspect semantics;
13. introduce T5 `EvaluateResult`, Explanation, WhyNot, `row.close()`, or public trace/evidence surfaces;
14. widen `RuleExprOccurrenceBinding` beyond a private `rule_version: str | None` field, or equivalent private occurrence-version lookup data; version metadata must not enter canonical key, content digest, identity, hash, join, or branch ordering semantics in this slice or future slices.

### 5.9 Validation layers

Layer 1: SDK public call-shape validation remains in `SDKStore.evaluate(...)`.

Layer 2: T4.1 head identity validation over `RuleExprLoweringPlan`.

Layer 3: T4.1 declared-port and head namespace validation over branch-total private data.

Layer 4: Existing T3L.3 external-head rejection, adapter matrix, and runtime evaluation.

## 6. Invariants

- Public success remains `list[CandidateSet]`.
- Public missing/invalid `head=` remains `SDKStoreError`.
- Head/expression semantic validation failures use `RuleExprError`.
- Version mismatch warning is `UserWarning` and warning-only.
- Declared-port data stays private.
- Branch-total declared-port semantics are deterministic.
- Same-name ports do not auto-join.
- External-head body concatenation remains unimplemented in T4.1.
- T4.2 and T4.3 consume, not replace, the T4.1 private foundation.

## 7. Acceptance Criteria

1. Step 4.6 grep runs before implementation and records results in the paired audit log.

2. G7 baseline records 131 OK before implementation using the T3 later final preservation gate.

3. Inline same-id + same-digest head evaluation still returns `list[CandidateSet]`.

4. Same id + same digest + different version emits exactly one `UserWarning` per validation invocation and proceeds.

5. Same id + different digest raises `RuleExprError`.

6. Duplicate same-id same-digest inline head matches raise `RuleExprError`.

7. Undeclared head port raises `RuleExprError`.

8. Branch-partial OR declared port raises `RuleExprError`.

9. Same-name ambiguous sources raise `RuleExprError` unless explicit join materialization proves equivalence.

10. Explicit `.eq(...)` and `.join_by_ports(...)` equivalence permit same-name head projection when `PortType`s match.

11. Head `PortType` mismatch raises `RuleExprError`.

12. External-head body concatenation remains rejected with the existing T3L.3 `SDKStoreError` guidance.

13. Legacy SDK `Inference` / derivation dict evaluation tests remain green.

14. No public DTO/export/result shape changes are introduced.

15. Final gate includes T3.1-T3.6 + T3L.1-T3L.3 preservation tests plus new T4.1 focused tests.

16. `ruff` passes if Python files are changed.

## 8. Implementation Plan

1. Run Step 4.6 pre-implementation greps from the paired audit log.

2. Record G7 baseline before implementation.

3. If Step 4.6 finds existing head/declared-port helpers or public API collisions, pause for A-fallback scope amendment.

4. Add private declared-port DTO/helper substrate in `rule_expr_lowering.py`.

5. Add private head validation helper consuming D11 identity and D12 declared-port rules.

6. Wire the helper into `_evaluate_rule_expr_input(...)` after lowering and before external-head rejection.

7. Add focused private helper tests and public SDK warning/error tests.

8. Run focused tests, full preservation gate, and `ruff`.

9. Complete Step 4.7 review; fix P1/P2 findings before closure.

10. Close §10, transition `scoped -> implemented`, archive the blueprint pair, and consolidate memory.

## 9. Reviewer Focus

Review should pay special attention to:

- whether T4.1 stays within D11/D12 and does not implement D13/D14/D15;
- whether stale same-id/different-digest now uses `RuleExprError`, not external-head `SDKStoreError`;
- whether version warning is warning-only and does not alter identity;
- whether declared ports are branch-total rather than inspect union;
- whether same-name ambiguity is rejected without explicit join materialization;
- whether exact `PortType` equality is preserved;
- whether public result shape and legacy dispatch paths remain unchanged;
- whether Step 4.6 grep covers projection/closed-head/T5 scope creep.

## 10. Outcome

Pending.
