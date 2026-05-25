# Task Blueprint: T4.2 External + Projection Head Execution

- Status: scoped
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Class: M (predicted)
- Related Modules:
  - `src/factgraph/application/protocol/rule.py`
  - `src/factgraph/application/protocol/rule_expr_lowering.py`
  - `src/factgraph/sdk/store.py`
  - `tests/application/protocol/test_rule_expr_head_validation.py`
  - `tests/application/protocol/test_rule_expr_lowering.py`
  - `tests/application/protocol/test_rule_expr_lowering_adapter.py`
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
  - `workflow/blueprints/archive/2026-05-25_t4-1-head-identity-declared-port-foundation.md`
  - `workflow/blueprints/archive/2026-05-25_t3l-1-internal-lowering-native.md`
  - `workflow/blueprints/archive/2026-05-25_t3l-2-adapter-matrix-parity.md`
  - `workflow/blueprints/archive/2026-05-25_t3l-3-public-dispatch-diagnostics-docs.md`
- Audit Log:
  - [2026-05-25_t4-2-external-projection-head-execution.audit.md](./2026-05-25_t4-2-external-projection-head-execution.audit.md)

## 0. Scope Locks

### In scope

- D13 external-head body materialization:
  - alias-scope external head body variables under a private, non-user-addressable head alias;
  - concatenate external head body atoms into every executable RuleExpr branch;
  - add D13 head-port link equality atoms that bind each `head.ports` key to the D12 declared branch source for that port;
  - keep D13 head-port link metadata private and distinct from D8 `RuleExprJoinMaterialization`.
- D14 `Rule.projection(*port_names)` sugar:
  - public classmethod on application `Rule`;
  - same-name positional string-only v1 API;
  - private recognizable `Rule` shape satisfying shipped non-empty `Rule.where` and `ports` invariants;
  - placeholder atoms are validation-only and never materialized as filters;
  - argument-order output preservation.
- Three-way head dispatch in the RuleExpr evaluation path:
  - inline head: existing T3L.3 behavior remains unchanged after T4.1 validation;
  - external head: D13 materializes head body and head-port links;
  - projection head: D14 recognizer bypasses D11 identity matching and uses D13 head-port links without materializing placeholder atoms.
- Replace the T3L.3 external-head `SDKStoreError` rejection in `_evaluate_rule_expr_input(...)` with T4.2 materialization.
- Reuse T4.1 helpers and contracts:
  - `_validate_rule_expr_head_foundation(...)`;
  - `_declared_ports_for_rule_expr_plan(...)`;
  - D12 branch-total declared ports;
  - D12 / T4.1 graph-connectivity same-name equivalence over D8 join records.

### Out of scope

- T5 `EvaluateResult`, Explanation, WhyNot, `row.close()`, public trace/evidence, or result/evidence DTO exports.
- T1.3 final SDK `Rule` flip.
- Adapter grammar expansion or adapter production file edits for Souffle, ProbLog, or PyReason.
- D15 closed-head inspect utilities, `inspect.is_closed`, and `inspect.unbound_ports`; T4.3 owns them.
- Public `expr.declared_ports`.
- Any public projection DTO, public head-link DTO, public trace DTO, or public error subclass.
- `CandidateSet`, `SupportArtifact`, `EvidenceEnvelope`, `CompiledDerivationPlan`, or `DerivationEvaluateRequest` shape changes.
- Public success shape changes; `fg.eval.evaluate(...)` still returns `list[CandidateSet]`.
- Legacy SDK `Inference`, derivation dict, and fallback evaluation behavior changes.
- Projection rename syntax such as `Rule.projection(out_user="user")`.

M-to-L or split triggers:

- external-head implementation requires adapter production changes;
- projection placeholder shape cannot satisfy shipped `Rule` invariants without relaxing `Rule.where` globally;
- head-port links require public result/evidence shape changes;
- D13 and D14 cannot fit safely in one feature slice after Step 4.6 or implementation spike;
- closed-head inspect or T5 result semantics become necessary to complete T4.2 tests.

If any trigger appears, pause for a reviewed A-fallback amendment before code.

## 1. Inputs

Canonical sources:

- T4 Stage 3 synthesis assigns T4.2 to external + projection head execution at lines 147-177:
  - D13 external head body atoms added to every executable branch;
  - D13 private head alias variable rewriting;
  - D13 head-port link equality atoms after D8 joins;
  - D13 private head-link provenance;
  - D14 `Rule.projection(*port_names)` public classmethod;
  - D14 private recognizable projection-head shape;
  - D14 projection placeholder atoms not materialized;
  - D14 projection `PortType` copied from D12 declared-port map.
- Track plan T4.2 row at lines 220-223 names this as additive public head behavior + private materialization.
- D13 section 4.1-4.9 locks external-head body semantics.
- D14 section 4.1-4.9 locks projection sugar semantics.
- D11 and D12 remain the prerequisite identity / declared-port foundation.
- T4.1 archived blueprint records that external-head body concatenation and `Rule.projection(...)` were explicitly deferred to T4.2.
- T3L.1/T3L.2/T3L.3 provide lowering, materialization, adapter, and public SDK dispatch substrate.

Shipped source read before drafting:

- `src/factgraph/application/protocol/rule.py`
  - `Rule` fields and construction invariants are lines 47-66.
  - ports must be `Var`s appearing in `where` at lines 80-87.
  - `Rule.port_types` and `Rule.content_digest` are lines 93-108.
  - `Rule.as_(...)` remains lines 125-127.
- `src/factgraph/application/protocol/rule_expr_lowering.py`
  - `RuleExprPortBinding` / `RuleExprOccurrenceBinding` / `RuleExprHeadBinding` are lines 43-96.
  - `RuleExprEvaluationTrace` is lines 161-213.
  - T4.1 `RuleExprDeclaredPortBranchSource`, `RuleExprDeclaredPort`, and `RuleExprHeadValidation` are lines 222-278.
  - `_materialize_adapter_derivation_plan(...)` currently rejects external heads at lines 299-310.
  - `_validate_rule_expr_head_foundation(...)` is lines 371-425.
  - `_declared_ports_for_rule_expr_plan(...)`, `_branch_declared_port_sources(...)`, and `_same_name_bindings_are_joined(...)` are lines 428-518.
  - `_head_binding(...)` still returns only `inline` or `external` at lines 760-777.
  - `_head_var_names(...)` still rejects non-inline heads at lines 780-788.
  - `_alias_var_map(...)`, `_rewrite_atom(...)`, and `_rewrite_term(...)` are lines 812-905.
- `src/factgraph/sdk/store.py`
  - `_evaluate_rule_expr_input(...)` is lines 2333-2389.
  - T4.1 validation is already called before the external-head rejection at lines 2365-2370.
- `src/factgraph/core/rules/where_ast.py`
  - `Origin`, `Var`, `PredAtom`, and `CmpAtom` are lines 13-51.

Pre-draft grep summary:

- `_validate_rule_expr_head_foundation` is consumed only by helper tests and `SDKStore._evaluate_rule_expr_input(...)`.
- `head_binding.kind == "external"` exists in `_materialize_adapter_derivation_plan(...)` and `_evaluate_rule_expr_input(...)`.
- `Rule.projection` has no production implementation; hits are design docs, historical docs, and unrelated `projection` helper names.
- D13 head-port link terms appear only in active audit / decision docs.
- `_branch_declared_port_sources` and `_same_name_bindings_are_joined` are T4.1 private helper internals.
- `RuleExprHeadValidation.declared_ports` has no production downstream reader.
- `Origin(source="authoring", path="Rule.projection")` has no production implementation.

No pre-draft grep result requires an A-fallback amendment.

## 2. Plan

### 2.1 Three-way head classification

T4.2 should make head kind explicit in private lowering:

```python
RuleExprHeadBinding.kind: Literal["external", "inline", "projection"]
```

or equivalent private state. If the exact field is widened, the upper bound for this slice is exactly `external`, `inline`, and `projection`.

Classification order:

1. Projection recognizer runs first during `RuleExprHeadBinding` construction, before D11 inline id + digest matching. Exact projection-head values become `projection` and bypass D11 identity matching.
2. Same id + same digest + one occurrence remains `inline`.
3. Different id, same id + different digest before T4.1 validation, or no exact match remains `external`.
4. T4.1 validation still owns stale digest and ambiguous same-id same-digest rejection before materialization.

Inline heads:

- keep T3L.3 materialization behavior;
- do not concatenate head body atoms;
- derive head output vars from the inline occurrence as today.

External heads:

- use D13 branch-wise head body concatenation;
- use D13 head-port link equality atoms;
- preserve D12 validation and D11 identity failures from T4.1.

Projection heads:

- are exact `Rule.projection(...)` values;
- bypass D11 identity matching;
- use D12 declared-port validation;
- contribute D13 head-port links only;
- never materialize placeholder atoms.

### 2.2 D13 external-head materialization

T4.2 should replace the current external-head blocker in `_materialize_adapter_derivation_plan(...)`.

The implementation should split or extend the existing materialization helper so D13 order is preserved:

1. expression branch body atoms;
2. alias-scoped external head body atoms;
3. D8 explicit RuleExpr join equality atoms;
4. D13 head-port link equality atoms in sorted head port-name order.

The four-step order applies by head kind as follows:

| Head kind | Step 1 expression body | Step 2 head body | Step 3 D8 joins | Step 4 D13 head links |
|---|---|---|---|---|
| inline | yes | no | yes | no |
| external | yes | yes, alias-scoped | yes | yes, sorted by port name |
| projection | yes | no | yes | yes, sorted by port name |

Projection does not enter step 2 because D14 section 4.3 makes placeholder atoms validation-only and not materialized as filters.

Because existing `_materialize_branch(...)` currently returns expression body + D8 joins together, implementation may either:

- split it into expression-body and join-materialization phases; or
- introduce a new internal branch-materialization helper that reuses D8 join resolution logic without duplicating public semantics.

External head body variables should be rewritten through the existing alias-local machinery (`_alias_var_map(...)`, `_rewrite_atom(...)`, `_rewrite_term(...)`) using a private alias that cannot collide with public occurrence aliases.

For each runtime branch and each head port:

- find the branch-specific `RuleExprDeclaredPortBranchSource` from T4.1 `RuleExprDeclaredPort.branch_sources`;
- rewrite the head port `Var` through the private head alias map;
- add `CmpAtom(op="eq", lhs=head_alias_local_port_var, rhs=source.alias_local_execution_var)`.

These equality atoms are head-port links, not D8 user joins.

### 2.3 Private D13 head-link metadata

Add private metadata equivalent to:

```python
RuleExprHeadPortLinkMaterialization(
    branch_id: str,
    head_port_name: str,
    source_occurrence_alias: str,
    source_port_name: str,
    materialized_atom_index: int,
)
```

Exact names may differ. Binding constraints:

- no public export;
- separate from `RuleExprJoinMaterialization`;
- trace sidecar remains private;
- future T5 evidence can distinguish user-authored joins from inserted head links.

If `RuleExprEvaluationTrace` is widened, the new field is bounded to private head-port link metadata only; it must not alter public success payloads or adapter request shapes.

### 2.4 D14 `Rule.projection(...)`

Add a public classmethod on application `Rule`:

```python
Rule.projection(*port_names: str) -> Rule
```

Construction rules:

- at least one port name;
- every argument is a non-empty string;
- duplicate names rejected;
- no keyword rename syntax;
- returns an application `Rule`, not a public projection DTO.

Private recognizable shape:

- deterministic private `Rule.id` derived from the ordered port-name tuple;
- `ports` maps each requested output name to a generated private `Var`;
- `where` is non-empty and mentions every generated port `Var`;
- placeholder atoms carry `Origin(source="authoring", path="Rule.projection")`;
- recognizer must also check generated id pattern, generated `Var` pattern, atom count, atom shape, atom origins, and `ports`/`where` consistency to reduce accidental spoofing.

Suggested placeholder shape:

- one private `PredAtom` per requested port, with private predicate id and one generated port `Var`; or
- an equivalent private atom shape that satisfies current `Rule.__post_init__` and is easy to recognize exactly.

Placeholder atoms are a representation device. They must not be materialized as body filters.

### 2.5 Projection-head validation and materialization

Projection heads use the D12 declared-port map, not placeholder `Rule.port_types`, for evaluation validation.

For each projected port:

- requested name must exist in the branch-total declared-port map;
- requested name must be unambiguous or D8-joined equivalent per T4.1;
- output `PortType` is copied from the declared-port map for validation and future inspect use;
- head link atoms bind generated projection vars to branch source vars.

Output order:

- `Rule.projection("user", "state")` preserves argument order in `head.ports`;
- `CompiledHeadCall.head_var_names` must preserve that requested order for output payload ordering.
- `_head_var_names(...)` must return head-side variables for external and projection heads:
  - inline heads keep returning inline occurrence alias-local port vars as in T3L.3;
  - external heads return private head-alias-local port vars, which D13 head-link atoms equate to the branch source vars;
  - projection heads return generated projection port vars, which D13 head-link atoms equate to the branch source vars.

This separates D13 materialization ordering from D14 output payload ordering: head-link atoms are sorted by port name for stable `materialized_atom_index`, while output columns preserve `head.ports` / projection argument order.

### 2.6 SDK dispatch wiring

`SDKStore._evaluate_rule_expr_input(...)` should keep current call-shape behavior:

- missing / invalid `head=` remains `SDKStoreError`;
- semantic validation remains `RuleExprError`;
- public result remains `list[CandidateSet]`;
- legacy `Inference` and derivation dict paths remain unchanged.

T4.2 should remove the current T3L.3 external-head `SDKStoreError` branch after T4.1 validation. It should then call the same adapter materialization path for inline, external, and projection heads.

PyReason behavior:

- T4.2 does not expand PyReason grammar.
- External head bodies containing non-pred atoms, aggregate atoms, or head-link equality atoms should remain subject to the existing D9/T3L.2/T3L.3 adapter support policy.
- If PyReason cannot support a valid T4.2 plan, public rejection remains `SDKStoreError` through the existing adapter support conversion path.

### 2.7 Tests

Production changes should be covered by:

- new application protocol tests for projection construction, projection recognizer, external-head materialization, and head-port link metadata;
- SDK tests for public external-head success, projection success, error buckets, and legacy preservation.

Expected focused coverage:

- external head body filters rows in native execution;
- external head body is applied to every OR branch;
- external head variables do not collide with expression occurrence variables;
- external head ports link by public port key, not internal `Var` name;
- external head entity-ref and value ports materialize through head links;
- aggregate-containing external head body preserves existing native / adapter behavior and PyReason rejection policy;
- projection construction rejects no args, non-string args, empty-string args, and duplicate names;
- projection all-ports and subset success cases;
- projection preserves argument order;
- projection undeclared port rejection;
- projection supports both entity-ref and value declared ports;
- projection placeholder atoms do not appear in materialized branch bodies;
- inline-head behavior and T4.1 validation behavior remain green.

### 2.8 Diagnostics and docs

Diagnostics:

- projection construction failures use `RuleValidationError`;
- projection evaluation failures use `RuleExprError`;
- external-head semantic validation failures use `RuleExprError`;
- adapter unsupported-engine failures remain public `SDKStoreError`;
- no new public error subclass.

Docs:

- no broad user-facing docs update in T4.2 unless tests require a tiny API note;
- T4.3 owns the full Head / projection / closed-head docs pass, per Stage 3 synthesis;
- if T4.2 adds a small API note, it must not mention T5 `EvaluateResult`, Explanation, WhyNot, or closed-head inspect fields.

## 3. Code Changes

Expected production edits:

1. `src/factgraph/application/protocol/rule.py`
   - add `Rule.projection(...)`;
   - add private projection helper constants / shape checks if they belong naturally with `Rule`;
   - keep `Rule.__post_init__` invariants intact.

2. `src/factgraph/application/protocol/rule_expr_lowering.py`
   - widen or otherwise extend private head binding/classification to represent projection heads;
   - add private projection recognizer if it does not live in `rule.py`;
   - add D13 head-port link metadata;
   - replace the external-head blocker in `_materialize_adapter_derivation_plan(...)`;
   - split / extend branch materialization to enforce D13 atom order;
   - update `_head_var_names(...)` for external/projection heads using head ports and D13 link vars;
   - keep `__all__: list[str] = []`.

3. `src/factgraph/sdk/store.py`
   - remove the current external-head `SDKStoreError` rejection after T4.1 validation;
   - preserve call-shape errors and legacy dispatch paths.

Expected test edits:

- `tests/application/protocol/test_rule_expr_head_validation.py` or a new focused lowering test file for D13/D14 helper behavior.
- `tests/sdk/test_rule_expr_evaluate.py` for public external/projection execution.
- Existing T3L/T4.1 focused suites should remain green.

No adapter production file edits are expected.

## 4. Verification Gates

G7 baseline before feature implementation:

```bash
PYTHONPATH=src python -m unittest \
  tests.application.protocol.test_rule \
  tests.application.protocol.test_rule_expr \
  tests.sdk.test_ruleexpr_inspect \
  tests.sdk.test_rule_naming \
  tests.application.protocol.test_rule_aggregate \
  tests.test_branch_identity_rule_inspect \
  tests.application.protocol.test_rule_expr_lowering \
  tests.application.protocol.test_rule_expr_lowering_adapter \
  tests.sdk.test_rule_expr_evaluate \
  tests.application.protocol.test_rule_expr_head_validation \
  -v
```

Expected baseline: 145 tests OK.

Post-feat gates:

- T4.2 focused application protocol tests;
- T4.2 focused SDK tests;
- full preservation command above plus new T4.2 tests;
- touched-file ruff:

```bash
ruff check \
  src/factgraph/application/protocol/rule.py \
  src/factgraph/application/protocol/rule_expr_lowering.py \
  src/factgraph/sdk/store.py \
  tests/application/protocol/test_rule_expr_head_validation.py \
  tests/sdk/test_rule_expr_evaluate.py
```

Full `ruff check src tests` remains optional because unrelated pre-existing repo issues have existed outside this slice.

Pytest remains deferred per existing SIGSEGV environment lock. `tests.test_public_inference_factgraph_create` remains excluded because failures are pre-existing and unrelated to RuleExpr / Head work.

## 5. Risks

- **Materialization ordering drift**: existing `_materialize_branch(...)` appends D8 joins. T4.2 must preserve D13 ordering by splitting or carefully extending helper internals.
- **Projection spoofing**: user-authored Rules could attempt to mimic projection metadata. Recognizer must combine Origin, id pattern, generated Var pattern, atom shape, atom count, and ports/where consistency.
- **PyReason compatibility**: D13 head-link equality atoms and non-pred external head body atoms may cause existing PyReason classifier rejection. This is expected under D9/T3L.2 policy; do not expand PyReason grammar in T4.2.
- **Aggregate x external head interaction**: external head bodies containing aggregate atoms make every branch aggregate-containing, so the existing D9/T3L.2 PyReason classifier rejects the whole query through adapter policy. T4.2 must not relax aggregate-side rejection or modify the PyReason classifier.
- **T4.1 graph-connectivity contract**: T4.2 must consume declared-port branch sources as already validated. It must not reimplement same-name ambiguity with a different equivalence rule.
- **Placeholder atom escape**: projection placeholder atoms must never enter final materialized body IR, traces as runtime atoms, or adapter request bodies.
- **Result shape drift**: adding head-link metadata must stay private; public success remains `list[CandidateSet]`.

## 6. Rollback / Recovery

Rollback should be straightforward if T4.2 remains scoped:

- revert `Rule.projection(...)`;
- restore `_materialize_adapter_derivation_plan(...)` external-head rejection and `_head_var_names(...)` inline-only behavior;
- remove T4.2 tests;
- leave T4.1 validation helpers intact.

If feature work discovers external/projection should split, pause before feat commit and amend this blueprint into T4.2a/T4.2b.

## 7. Preemptive Scope Locks

This slice must not:

1. change public success result away from `list[CandidateSet]`;
2. export public projection/head-link/trace DTOs;
3. add `EvaluateResult`, Explanation, WhyNot, `row.close()`, or public evidence APIs;
4. add closed-head inspect fields (`is_closed`, `unbound_ports`);
5. expose public `expr.declared_ports`;
6. change legacy SDK `Inference`, derivation dict, or fallback evaluate behavior;
7. edit Souffle / ProbLog / PyReason production adapter files;
8. expand adapter grammar or PyReason Form 2 support;
9. implement projection rename syntax;
10. relax `Rule.where` or `Rule.ports` non-empty invariants globally;
11. make projection placeholder atom shape part of public semantics;
12. conflate D13 head-port link metadata with D8 user-authored join metadata;
13. change `CandidateSet`, `SupportArtifact`, `EvidenceEnvelope`, `CompiledDerivationPlan`, or `DerivationEvaluateRequest` shapes;
14. perform the T1.3 final SDK `Rule` naming flip;
15. add new public error subclasses;
16. update broad docs with T5/closed-head claims.

## 8. Implementation Steps

1. Add `Rule.projection(...)` with private placeholder shape and construction tests.
2. Add private projection recognizer and exact anti-spoofing checks.
3. Extend private head classification / binding to include projection.
4. Add D13 head-port link metadata DTO.
5. Split or extend materialization to produce expression atoms, external head atoms, D8 joins, and D13 links in the locked order.
6. Update `_head_var_names(...)` for external and projection heads.
7. Replace SDK external-head rejection with head-aware materialization path.
8. Add application protocol tests for helper/materialization behavior.
9. Add SDK tests for public external/projection success and diagnostics.
10. Run G7 + focused + ruff gates.

## 9. Reviewer Focus

Claude should verify:

1. the blueprint keeps T4.2 limited to D13 + D14;
2. T4.1 validation remains the prerequisite and is reused, not duplicated;
3. external-head materialization order matches D13 section 4.6;
4. head-port links use D12 declared branch sources by public port key;
5. projection placeholder atoms cannot materialize as filters;
6. projection recognizer anti-spoofing is specific enough for implementation;
7. public result shape and adapter files remain untouched;
8. PyReason limitations are treated as adapter-policy rejections, not grammar expansion work;
9. G7 baseline starts from the post-T4.1 145-test gate.

## 10. Outcome / Deviations

Pending implementation.
