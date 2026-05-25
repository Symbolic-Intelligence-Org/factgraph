# Task Blueprint: T5.4 Row Close + Manual Explain Closed-Head Gate

- Status: draft
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Class: M (predicted; split if manual explain needs broad runtime/service work)
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Owner: Codex
- Reviewer: Claude
- Related audit: `workflow/blueprints/active/2026-05-25_t5-4-row-close-manual-explain-closed-head-gate.audit.md`
- Source decisions:
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
  - `workflow/audit/active/2026-05-25_post-q-t5-result-evidence-explain-synthesis.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d21-row-close-closed-head-gate.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d25-evaluate-explain-semantics-consistency.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d26-semantics-commitments-scope-adapter-policy.md`
  - `workflow/design/decisions/active/2026-05-25_t4-d15-closed-head-inspect.md`
- Predecessor slices:
  - T5.1 DTO Foundation + Digest Harness archived at `53781419`; feature anchor `a3e96eb6`.
  - T5.2 Public Evaluate Return-Shape Flip archived at `4e590e8a`; feature anchor `7dfadd4e`.
  - T5.3 Explanation Envelope + Live Row Resolver archived at `ba5e5c26`; feature anchor `53551cb6`.

## 0. Scope Locks

### In scope

- Add live `EvaluateRow.close() -> Rule`.
- Preserve detached row behavior: detached `row.close()` raises `DetachedRowError`.
- Construct a closed application head Rule from:
  - the owning `EvaluateResult.head`;
  - the row's public `bindings`;
  - schema identity metadata when entity-ref output ports are present.
- Implement D21 strict closure construction:
  - value ports use `CmpAtom("eq", port_var, Const(row.bindings[port_name]))`;
  - entity-ref ports use `PredAtom(identity_predicate_id, [entity_ref_var, Const(identity_value)])`;
  - atoms are appended in `head.ports` iteration order.
- For projection heads, strip D14 placeholder atoms and emit real closure atoms from row bindings.
- Validate produced and caller-provided closed heads through the T4.3 D15 strict closed-head substrate.
- Add manual SDK eval entrypoint:
  - `fg.eval.explain(expr, head=closed_head, ...) -> Explanation`;
  - validates `head` before entering the D20 explanation pipeline;
  - returns standalone manual `Explanation` with `semantics_source="manual_standalone"` when no row/result anchors exist.
- Consume D19 `closed_head_digest_for(closed_head)`; do not redefine the formula.
- Preserve D25 policy:
  - row-sourced `row.explain()` remains no-arg and unchanged;
  - row-anchored manual replay with mismatched `semantics_digest` raises before `Explanation`;
  - standalone manual explain has no mismatch to compare.
- Add focused tests for row-close value/entity/projection construction, detached close, closed-head gate, manual explain standalone checked scope, and forbidden future-slice surfaces.

### Out of scope

- Public `.eval.why_not(...)`; D22/T5.5 owns no new public why-not surface.
- Why-not fold implementation; T5.5 owns it.
- Final SDK top-level `Rule` naming flip; T5.6/D24 owns it.
- Legacy hard-cut, service routes, OpenAPI, broad docs migration, and old shell removal; T5.7/D23 owns those.
- C73-C78 semantics implementation or adapter production edits; T5.8/D26 or post-T5 owns adapter-touching work.
- General closure inference beyond D15 strict v1:
  - no transitive equality;
  - no cross-port closure;
  - no generic field literal closure;
  - no `InAtom`, `BuiltinAtom`, `NotAtom`, or aggregate-derived closure;
  - no D13 runtime head-port link atoms as closure proof.
- New public closed-head DTO, `ClosedHeadStatus`, or public inspect helper.
- Renderer product API or `Explanation.render()`.
- Service/OpenAPI manual explain route.

### M-to-L triggers

Pause and amend/split if implementation requires:

- new public result or closed-head DTOs;
- broad evaluation runtime redesign;
- service route / OpenAPI changes;
- adapter production edits;
- changing T5.1/T5.2/T5.3 DTO or evaluate contracts;
- changing D19 digest formulas;
- changing D25 semantics mismatch policy;
- changing `Rule.content_digest`;
- changing projection lowering or D14 placeholder semantics;
- relaxing `Rule.where` / `Rule.ports` invariants.

## 1. Inputs

T5.4 consumes the completed row-centric explanation substrate and fills the advanced replay bridge:

- D17 defines live/detached row boundaries and `DetachedRowError`.
- D19 defines `closed_head_digest` and result/replay digest anchors.
- D20 defines the manual `fg.eval.explain(expr, head=closed_head, ...) -> Explanation` output shape and status/evidence matrix.
- D21 defines `row.close()`, closed-head construction, projection placeholder stripping, and the manual explain must-be-closed gate.
- D25 defines semantics consistency:
  - row-sourced `row.explain()` reuses original semantics;
  - row-anchored manual mismatch raises;
  - standalone manual explain records `semantics_source="manual_standalone"`.
- T4.3 D15 defines strict v1 closed-head recognition and the future must-be-closed `RuleExprError` gate.
- T5.3 shipped `Explanation`, `EvaluateRow.explain()`, minimal row-sourced `EvidenceGraph`, and checked-scope copying.

Pre-draft shipped-source reads found:

- `src/factgraph/application/protocol/evaluate_result.py` has `EvaluateRow.explain()` and `_require_live_result()`, but no `EvaluateRow.close()`.
- `src/factgraph/sdk/store.py` has `_SDKEvalManager.evaluate(...)` but no public `eval.explain(...)` entrypoint.
- `src/factgraph/application/protocol/rule_expr_inspect.py` has private `_inspect_closed_head(...)`, `_value_port_is_closed(...)`, and `_entity_ref_port_is_closed(...)` helpers used by T4.3 inspect.
- `src/factgraph/application/protocol/rule.py` exposes `_is_projection_rule(...)`, projection marker constants, and the shipped `Rule` invariants.
- `src/factgraph/application/protocol/schema_runtime.py` exposes identity metadata and `EntityRef` / identity normalization helpers that row-close entity-ref closure can reuse or mirror privately.

## 2. Plan

### 2.1 Add live `EvaluateRow.close()`

Add a public no-argument method:

```python
def close(self) -> Rule: ...
```

Behavior:

- calls `_require_live_result()`;
- raises `DetachedRowError` for detached rows;
- returns an application protocol `Rule`;
- accepts no kwargs;
- does not return `Explanation`, `RuleExprInspect`, dicts, or a public closed-head status.

The method delegates to a private closed-head constructor that receives the row and owning `EvaluateResult`.

### 2.2 Construct closed heads from result head and row bindings

For non-projection heads:

- start from `result.head`;
- preserve:
  - `ports`;
  - `version`;
  - `desc`;
  - existing user-authored `where` atoms;
- append closure atoms for every port in `result.head.ports` order;
- use closed id:

```text
f"{result.head.id}_closed_{row.row_id}"
```

Construction must not use D13 runtime head-port link atoms as closure proof.

### 2.3 Close value ports with direct equality atoms

For each `PortType(kind="value")` output port:

```python
CmpAtom("eq", port_var, Const(row.bindings[port_name]))
```

If the binding is missing, raise `RuleExprError`.

Do not infer closure through `Var == Var`, transitive equality, `InAtom`, `BuiltinAtom`, `NotAtom`, aggregates, or unrelated field predicates.

### 2.4 Close entity-ref ports with primary identity predicate atoms

For each `PortType(kind="entity_ref")` output port:

- normalize the row binding into identity values for that entity type;
- read schema metadata from the SDK/application schema index;
- for every primary identity field, append:

```python
PredAtom(identity_predicate_id, [entity_ref_var, Const(identity_value)])
```

where `identity_predicate_id` comes from:

```python
SchemaIndex.entities[entity_type].identity_predicates[field_name].pred_id
```

and the term order is exactly `[entity_ref_var, Const(identity_value)]`.

Missing schema metadata, missing identity values, incomplete compound identity, or incompatible binding shape raises `RuleExprError`.

Implementation may accept:

- `EntityRef`;
- encoded entity-ref strings when the entity type and identity can be resolved from schema runtime helpers;
- mapping values that contain primary identity fields.

The implementation must not close entity refs with `CmpAtom("eq", entity_var, Const(entity_ref))`.

### 2.5 Strip projection placeholder atoms

If `result.head` is a D14 projection Rule:

- do not copy original projection placeholder atoms;
- build a new ordinary Rule whose body consists of D15 closure atoms produced from row bindings;
- preserve projection output ports and port order;
- make the result fail `_is_projection_rule(...)` by construction;
- compute `closed_head_digest_for(closed_head)` from the produced Rule.

Projection inspect remains closed-by-construction, but `row.close()` must produce a durable closed-head Rule suitable for manual replay.

### 2.6 Validate closed heads with D15 strict gate

After row-close construction, validate the closed Rule:

- use T4.3 `_inspect_closed_head(...)` through a private adapter or equivalent private helper;
- require `is_closed=True`;
- if unbound ports remain, raise `RuleExprError`;
- for entity-ref heads, require schema metadata rather than using D15's read-only conservative "unbound" path.

Manual `fg.eval.explain(..., head=closed_head, ...)` runs the same gate before D20 replay.

### 2.7 Add manual `fg.eval.explain(...)`

Add a read-only eval namespace method:

```python
fg.eval.explain(expr, *, head=closed_head, engine=None, semantics=None, **kwargs) -> Explanation
```

The public entrypoint:

- accepts RuleExpr / application Rule inputs consistent with SDK evaluate;
- requires `head=` application protocol Rule;
- rejects open or malformed heads with `RuleExprError` before `Explanation`;
- rejects unexpected kwargs with `SDKStoreError`;
- does not accept `row=`, `evidence_ref=`, or row-anchored replay in T5.4 unless explicitly added by amendment;
- for standalone manual explain, computes replay context from the current SDK store, expression/head inputs, engine, and optional semantics.

T5.4 may implement standalone manual explain using existing `evaluate(...) -> EvaluateResult` substrate followed by row matching against the closed head, if this stays within SDK scope and does not change T5.2 evaluate behavior.

### 2.8 Manual explain output and checked scope

Standalone manual explain:

- returns `Explanation`;
- sets `semantics_source="manual_standalone"`;
- sets `evaluate_semantics_digest=None`;
- sets `explain_semantics_digest` to the supplied semantics digest or `None`;
- sets `semantics_match=None`;
- uses D20 status/evidence matrix.

If the closed head is false / no matching row is found, return `Explanation(status="failed", failure_class="closed_head_false" or "no_matching_row", evidence=None, ...)` rather than raising, after the closed-head precondition has passed.

If graph construction fails, return `unsupported` with `GRAPH_VALIDATION_FAILED`, consistent with T5.3.

### 2.9 Error boundaries

Use existing error buckets:

- `DetachedRowError` for detached `row.close()`;
- `RuleExprError` for open heads, unsupported closure patterns, missing schema, missing binding, or must-be-closed failures;
- `RuleValidationError` for invalid Rule DTO construction;
- `SDKStoreError` for public SDK call-shape errors;
- `ProtocolShapeError` for DTO construction bugs.

Do not add new public error subclasses.

### 2.10 Implementation ordering

Recommended local order:

1. Add private closed-head construction helpers and tests for value ports.
2. Add entity-ref identity construction helpers and tests.
3. Add projection placeholder stripping tests.
4. Add `EvaluateRow.close()`.
5. Add closed-head validation adapter using D15 strict inspect substrate.
6. Add SDK `eval.explain(...)` standalone manual entrypoint and focused tests.
7. Run focused tests, G7 preservation, and ruff.

## 3. Code Changes

Likely production files:

- `src/factgraph/application/protocol/evaluate_result.py`
  - add `EvaluateRow.close()`;
  - add private live row close helper or delegate hook.
- `src/factgraph/sdk/store.py`
  - add `_SDKEvalManager.explain(...)`;
  - add SDK-side manual explain dispatcher;
  - add closed-head construction helpers if schema context is SDK-owned;
  - add closed-head validation gate.
- `src/factgraph/application/protocol/rule_expr_inspect.py`
  - preferably no public changes; private helpers may be reused by import if acceptable.

Possible alternative:

- a new private protocol module for closed-head construction if implementation gets large, with no public export.

Files explicitly out of target scope unless amended:

- service route / OpenAPI / agent files;
- adapter production files;
- old Check/Diagnose/WhyNot shells;
- SDK final `Rule` namespace files;
- broad docs migration files.

## 4. Tests

Minimum focused tests:

1. Detached `row.close()` raises `DetachedRowError`.
2. Live value-port row closes to application `Rule`.
3. Value closure emits `CmpAtom("eq", port_var, Const(value))`.
4. Missing value binding raises `RuleExprError`.
5. Entity-ref single primary identity emits D15 `PredAtom(identity_predicate_id, [entity_ref_var, Const(value)])`.
6. Entity-ref compound identity emits one atom per primary identity field in schema order.
7. Missing entity schema metadata raises `RuleExprError`.
8. Projection `row.close()` strips placeholder atoms and produces non-projection closed Rule.
9. Produced closed Rule validates through D15 strict closed-head gate.
10. Manual `fg.eval.explain(expr, head=closed_head, ...)` rejects open heads with `RuleExprError`.
11. Manual standalone explain returns `Explanation` with `checked_scope["semantics_source"] == "manual_standalone"`.
12. Manual standalone explain with no matching row returns failed Explanation rather than open-head invalid_request.
13. Manual explain rejects unknown kwargs with `SDKStoreError`.
14. `row.explain()` remains no-arg and unchanged.
15. No public `.eval.why_not(...)` is introduced.
16. SDK `Rule` / `LegacyRule` / `ApplicationRule` namespace remains unchanged.
17. T5.2 evaluate return-shape tests remain green.
18. T5.3 row-explain tests remain green.

G7 preservation baseline before feat:

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

Expected inherited baseline: 166 tests OK from T5.3 archive.

## 5. Risks

| Risk | Mitigation |
|---|---|
| Manual explain grows into a second evaluate implementation. | Use existing T5.2 `evaluate(...) -> EvaluateResult` substrate where possible; do not fork runtime semantics. |
| Entity-ref close needs schema details not available on row/result. | Keep construction in SDK layer where schema index exists; raise `RuleExprError` if missing. |
| Projection placeholder atoms leak into replay. | Explicit projection tests assert placeholder pred ids are absent. |
| D15 strict closure broadens accidentally. | Tests cover rejection of non-D15 patterns; reuse T4.3 helper. |
| Manual explain blurs open-head precondition with D20 invalid_request. | Closed-head gate raises `RuleExprError` before constructing Explanation. |
| D25 row-anchored mismatch gets half-implemented. | T5.4 starts with standalone manual explain only unless row-anchored replay context is explicitly added. |
| Service/OpenAPI/docs migration leaks in. | Keep T5.4 SDK-only; T5.7 owns final migration. |
| SDK Rule flip sneaks in. | Tests keep `sdk.Rule is sdk.LegacyRule` until T5.6. |

## 6. Verification Gates

### Draft review gate

- Reviewer validates T5.4 scope does not absorb why-not, SDK Rule flip, service/docs migration, or adapter semantics.
- Reviewer validates `row.close()` / manual explain split is acceptable as one M-class slice.
- Reviewer validates standalone manual explain is sufficient for T5.4 unless row-anchored replay is explicitly required.

### Step 4.6 grep gate

Before scoped:

- search `row.close`, `EvaluateRow.close`, `fg.eval.explain`, `eval.explain`, `_inspect_closed_head`, `_is_projection_rule`, projection placeholder ids, identity predicates, `EntityRef`, `closed_head_digest`, service/docs/adapter guard words, and SDK Rule namespace;
- classify all hits;
- decide whether to keep as one M-class slice or split row-close and manual explain;
- record results in paired audit;
- amend blueprint if unexpected collisions appear.

### G7 baseline gate

After scoped:

- run inherited G7 preservation command;
- expected baseline is 166 tests OK;
- record pytest deferred and `tests.test_public_inference_factgraph_create` exclusion.

### Feature gate

Run:

- focused T5.4 row-close/manual explain tests;
- T5.3 row-explain focused tests;
- T5.2 evaluate return-shape focused tests;
- updated G7 preservation suite;
- touched-file ruff for production and tests.

Pytest remains deferred per existing SIGSEGV environment lock unless environment constraints change.

## 7. Rollback

Rollback must preserve T5.1-T5.3 substrates:

- If `row.close()` construction is wrong, revert `close()` and private closed-head helpers together.
- If manual explain is too broad, keep row-close work and split manual explain only after amendment.
- If entity-ref closure cannot be implemented without schema redesign, stop before feature commit and amend/split.
- Do not revert `Explanation`, `row.explain()`, or public evaluate return-shape commits.
- Do not revert unrelated dirty baseline files.

## 8. Documentation Handoff

T5.4 may add narrow inline docs only where needed for local coherence.

Deferred:

- final docs migration and examples rewrite remain T5.7;
- why-not docs remain T5.5/T5.7;
- final SDK `Rule` naming docs remain T5.6/T5.7;
- renderer product docs remain out of T5 Core.

## 9. Reviewer Focus

- Does the draft keep D15 strict closure unchanged?
- Is entity-ref closure sufficiently scoped to schema metadata already available?
- Should standalone manual explain and `row.close()` stay one M-class slice, or split before scoped?
- Does the manual explain plan avoid row-anchored semantics mismatch complexity unless explicitly added?
- Does projection placeholder stripping preserve T4.2/D14 behavior?
- Are service/docs/adapter/SDK Rule boundaries preserved?

## 10. Outcome

Pending implementation.
