# D21 Decision: T5 `row.close()` and Closed-Head Gate

- Status: adopted
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: adopted design constraint; locks `EvaluateRow.close()`, closed-head Rule construction, and mandatory closed-head validation for manual explain.
- Implementation Anchors: T5.4 row.close + manual explain feat `c820f102`, archive `7464c3e3`.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md` Q7, F7, section 6 C66 and C72 triage.
  - D16 `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md` sections 4.1, 4.5, 4.7, and 4.8.
  - D17 `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md` sections 4.3, 4.8, and 4.9.
  - D19 `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md` sections 4.3, 4.5, and 4.6.
  - D20 `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope.md` sections 4.3, 4.4, and 4.6.
  - T4 D15 `workflow/design/decisions/active/2026-05-25_t4-d15-closed-head-inspect.md` sections 4.1-4.10.
  - Parent design `workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md:1020-1081`.
  - Sibling future-design note `workflow/design/design-points/archive/evidence-tree-rainbird-style-v1.zh.md:1285-1321` as non-authoritative manual replay pipeline context.
  - Shipped `src/factgraph/application/protocol/rule.py:55-113` and `src/factgraph/application/protocol/rule_expr_inspect.py:89-230`.
- Outputs / Downstream:
  - D22 why-not disposition.
  - D23 legacy SDK hard-cut plan.
  - D24 T1.3 final SDK `Rule` flip.
  - D25 evaluate/explain semantics consistency.
  - D26 semantics commitments scope and adapter implementation policy.
  - Stage 3 T5 synthesis and row-close / manual-explain implementation blueprint(s).
- Related:
  - `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope.md`
  - `workflow/design/decisions/active/2026-05-25_t4-d15-closed-head-inspect.md`
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Depends on: D16, D17, D18, D19, and D20 reviewed clean.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

Parent section 5.8.2 introduces two live-row methods:

- `row.explain()` for the primary evidence path;
- `row.close()` for advanced introspection and manual replay.

D20 already locked `row.explain()` and advanced `fg.eval.explain(expr, head=closed_head, ...)`. D21 owns the missing bridge: how a live `EvaluateRow` produces the closed application head Rule consumed by manual explain, and how manual explain rejects open heads before entering the D20 explanation pipeline.

T4.3 shipped the closed-head inspect substrate:

- `RuleExprInspect.is_closed` and `unbound_ports` live on inspect output, not on `Rule` or `RuleExpr`;
- `_inspect_closed_head(...)` recognizes strict D15 value and entity-ref closure forms;
- projection heads are closed by construction for inspect;
- read-only inspect reports open heads without raising;
- future must-be-closed gates use `RuleExprError`.

D21 consumes that substrate without reopening T4.3. It does not expand closure inference beyond D15 strict v1, and it does not move closed-head fields onto `Rule`.

Evidence-tree v1 is cited only for local pipeline context: manual replay starts from a caller-provided closed head and prepares closed bindings for the evidence producer. D21 does not adopt evidence-tree v1 internal node schema, renderer contract, or audit channel.

## 2. Scope

This decision locks:

- public `EvaluateRow.close()` behavior;
- live versus detached row behavior for `close()`;
- closed application head Rule construction from `EvaluateResult.head` and `EvaluateRow.bindings`;
- closure atom construction for value and entity-ref ports;
- projection-head special handling so D14 placeholder atoms do not escape into manual replay;
- validation gate used by manual `fg.eval.explain(..., head=closed_head, ...)`;
- error buckets for non-closed, malformed, missing-schema, and detached cases;
- relationship between closed-head construction and D19 `closed_head_digest`.

## 3. Non-Scope

This decision does not lock:

- `EvaluateResult`, `EvaluateRow`, `Claim`, `EvidenceRef`, or `DetachedRowError` fields; D17 owns them;
- digest formulas or canonical serialization details; D19 owns them;
- `Explanation` field surface, graph validation, and evidence metadata; D20 owns them;
- why-not public surface disposition; D22 owns it;
- old API hard-cut mechanics and service-route updates; D23 owns them;
- final SDK public `Rule` naming; D24 owns it;
- evaluate/explain semantics mismatch policy; D25 owns it;
- C73-C78 semantics implementation details; D26 owns them;
- evidence-tree internal node/edge schema or rendering product contract;
- relaxing `Rule.where` / `Rule.ports` non-empty invariants;
- adding public closed-head DTOs or public closed-head inspect helpers.

## 4. Decision

### 4.1 `EvaluateRow.close()` returns a closed application head Rule

D21 adopts `EvaluateRow.close()` as an advanced introspection method:

```python
closed_head = row.close()
```

It returns an application protocol `Rule` value, described generically as a closed application head Rule until D24 decides final SDK naming. It does not return a dict, `ClosedHeadStatus`, `RuleExprInspect`, `Explanation`, or evidence graph.

`row.close()` is not the primary evidence API. Users should normally call `row.explain()`. `row.close()` exists for reproducibility, debugging, and manual replay through:

```python
fg.eval.explain(expr, head=closed_head, ...)
```

The returned Rule must satisfy shipped `Rule` invariants: non-empty `id`, non-empty `where`, non-empty `ports`, and every port `Var` must appear in `where`.

### 4.2 `row.close()` is live-row only; detached rows raise `DetachedRowError`

D21 follows D17's live/detached boundary.

If `_result_resolver` is absent, `row.close()` raises `DetachedRowError`. It must not:

- return a partially closed Rule;
- return `None`;
- return `Explanation(status="invalid_request")`;
- synthesize a closed head from row data without the owning result context.

Detached rows keep their data fields readable. Manual replay for detached data requires the user to supply a closed head to `fg.eval.explain(...)` directly.

### 4.3 Closed-head construction starts from the evaluation head and appends deterministic closure atoms

For non-projection heads, `row.close()` constructs a closed Rule from:

- the open application head Rule stored on `EvaluateResult.head`;
- the row's public `bindings`;
- the result's schema context when entity-ref ports are present.

The closed head preserves:

- the original head `ports` mapping;
- the original head `version` and `desc`;
- the original user-authored `head.where` atoms.

Then it appends closure atoms for each output port in `head.ports` iteration order. This keeps construction stable while preserving output-column order. D21 does not use D13 runtime head-port link atoms as closure proof or as construction input.

The closed Rule id is:

```text
f"{result.head.id}_closed_{row.row_id}"
```

This follows the parent design. Shipped `Rule.id` only requires a non-empty string; D21 does not introduce a new public id validator. If an implementation later needs a storage-safe derivative of this id, that derivative must remain internal and must not replace the public closed-head Rule id without a new decision.

### 4.4 Value ports close with direct equality atoms

For `PortType(kind="value")`, `row.close()` appends:

```python
CmpAtom("eq", port_var, Const(row.bindings[port_name]))
```

The emitted shape is the canonical D21 construction shape. D15 inspect also accepts `Const == Var`, but D21 construction uses `Var == Const` for deterministic output.

If a head value port has no corresponding binding in `EvaluateRow.bindings`, row-close construction fails with `RuleExprError`. A row produced by a valid `EvaluateResult` should not hit this path; if it does, the result/row invariant is broken and returning a misleading closed head would be worse than failing.

D21 does not infer closure through:

- `Var == Var`;
- transitive equality;
- `InAtom`, `BuiltinAtom`, `NotAtom`, or aggregate atoms;
- field predicates unrelated to D15 entity identity predicates.

### 4.5 Entity-ref ports close with primary identity predicate atoms

For `PortType(kind="entity_ref", entity_type=...)`, `row.close()` does not close the port with `CmpAtom("eq", port_var, Const(entity_ref_value))`.

It uses the D15 entity-ref closure form. For every primary-key identity field on the entity type, construction appends:

```python
PredAtom(identity_predicate_id, [entity_ref_var, Const(identity_value)])
```

where:

- `identity_predicate_id` comes from `SchemaIndex.entities[entity_type].identity_predicates[field_name].pred_id`;
- primary-key fields come from the schema identity metadata;
- atom term order is exactly `[entity_ref_var, Const(identity_value)]`;
- compound identity emits one predicate atom per primary-key field, in schema primary-field order.

If schema metadata is missing or incomplete, `row.close()` raises `RuleExprError`. D15 read-only inspect may conservatively report an entity-ref port as unbound without raising, but D21 is a must-produce-closed-head gate and cannot silently emit an unverifiable closed Rule.

If the row binding cannot be normalized into all primary identity values for the entity type, `row.close()` raises `RuleExprError`.

### 4.6 Projection heads drop placeholder atoms and build a real closed head from row bindings

If `EvaluateResult.head` is a D14 projection Rule, `row.close()` must not preserve D14 placeholder atoms.

Projection placeholder atoms are validation-only. They were not materialized as filters during T4.2 evaluation, and D21 must not let them escape into manual replay through a closed Rule.

For projection heads, construction uses:

- a closed Rule id derived by the same rule in section 4.3;
- the projection head `ports` mapping;
- deterministic closure atoms built from row bindings per sections 4.4 and 4.5;
- no original projection placeholder atoms.

The result is no longer a projection Rule; it is an ordinary closed application head Rule that satisfies D15 strict closure.

Projection inspect remains closed by construction, but `row.close()` still emits literal closure atoms so D20 manual replay has a durable closed-head form and D19 can compute `closed_head_digest` from `closed_head.id` and `closed_head.content_digest`.

### 4.7 Manual explain has a must-be-closed gate before the D20 pipeline

`fg.eval.explain(expr, head=closed_head, ...)` validates `head` before entering the D20 explanation pipeline.

The gate reuses the T4.3 closed-head helper or an equivalent private adapter of that helper. It must verify:

- `head` is an application protocol Rule;
- `head` is closed under D15 strict forms;
- entity-ref closure has complete schema metadata;
- malformed Rule construction has already been rejected by `RuleValidationError`.

If the head is not closed, uses unsupported closure patterns, or lacks required entity identity metadata, the gate raises `RuleExprError` per D15 section 4.10. It must not return `Explanation(status="invalid_request")` for a non-closed head, because the manual explain contract requires a closed head before replay can begin.

D20 `invalid_request` remains reserved for malformed manual explanation context after the closed-head precondition succeeds, such as missing replay metadata that D20 requires for EvidenceGraph construction.

### 4.8 `closed_head_digest` is computed from the closed Rule produced or validated by D21

D19 locks:

```text
sha256_token(canonical("closed_head_v1", closed_head.id, closed_head.content_digest))
```

D21 owns the `closed_head` value that feeds this formula:

- `row.close()` produces it from the live result and row;
- manual explain consumes caller-provided closed heads and validates them before D20 replay;
- D21 does not duplicate or redefine the digest formula.

`closed_head_digest` must not include live resolver state, `EvidenceGraph`, adapter-native evidence, `evaluated_at`, or D13 runtime head-link materialization metadata.

### 4.9 Error buckets remain inherited; D21 adds no public error subclass

D21 uses existing error buckets:

- `DetachedRowError` for calling `row.close()` on a detached row;
- `RuleExprError` for non-closed head, unsupported closure pattern, missing schema primary identity metadata, missing row binding for a head port, or invalid row/head mismatch during closed-head construction;
- `RuleValidationError` for construction-time `Rule` DTO failures;
- `SDKStoreError` for public SDK call-shape errors outside RuleExpr semantics.

D21 does not add `ClosedHeadError`, `RowCloseError`, or any new public error subclass.

## 5. Rejected Alternatives

### Option A: Make detached rows close themselves from serialized data

- **Rejected because**: D17 classifies resolver-dependent row methods as live-only. Detached row data does not carry enough authoritative result and schema context to construct an entity-ref closed head safely.

### Option B: Return `RuleExprInspect` or `ClosedHeadStatus` from `row.close()`

- **Rejected because**: parent section 5.8.2 defines `row.close() -> Rule`, and D20 manual explain consumes a closed head Rule, not an inspect report.

### Option C: Use D13 runtime head-link atoms as closure proof

- **Rejected because**: D15 explicitly says closure checks operate on user-authored head atoms, not runtime head-port links that only equate variables.

### Option D: Close entity-ref ports with `Var == Const(entity_ref)`

- **Rejected because**: D15 entity-ref closure requires primary identity predicate literals in positional order `[entity_ref_var, Const(value)]`. Direct equality to an entity-ref object is not a D15 strict v1 closure form.

### Option E: Preserve projection placeholder atoms in closed heads

- **Rejected because**: D14 placeholder atoms are validation-only and T4.2 deliberately does not materialize them as filters. Keeping them in a manual replay closed head would make projection behavior diverge from evaluation.

### Option F: Return `Explanation(status="invalid_request")` when manual explain receives an open head

- **Rejected because**: D15 already assigns must-be-closed validation failures to `RuleExprError`. D20 `invalid_request` is for malformed replay context after closed-head validation succeeds.

### Option G: Add a public `fg.eval.explain_closed(...)` helper in D21

- **Rejected because**: D20 already locks manual `fg.eval.explain(expr, head=closed_head, ...)`. D21 should not add a second public explanation entrypoint.

### Option H: Expand closed-head inference to transitive equality or general field literals

- **Rejected because**: D15 strict v1 intentionally rejects transitive, cross-port, aggregate-derived, negated, `InAtom`, and builtin closure. D21 consumes that substrate rather than broadening it.

## 6. Supporting Evidence

| Evidence | Source | D21 use |
|---|---|---|
| Parent defines `row.close() -> Rule` and live/detached row behavior | parent `rule-expression-and-proof-attempt.zh.md:1020-1081` | Adopts row-close method and detached error boundary |
| D15 strict closure recognizes value equality and entity primary identity literals only | D15 sections 4.1-4.5 | Defines construction forms and rejects broader inference |
| D15 future gates use `RuleExprError` | D15 sections 4.8-4.10 | Sets manual explain and row-close validation errors |
| Shipped `Rule` requires non-empty id/where/ports and port Vars in where | `rule.py:55-113` | Ensures closed-head construction remains a valid Rule |
| T4.3 private helper exists and reports closed/unbound ports | `rule_expr_inspect.py:163-230` | Provides reusable closed-head validation substrate |
| D19 locks `closed_head_digest` as id + content digest | D19 section 4.3 | D21 produces the closed Rule consumed by that formula |
| D20 manual explain consumes closed heads and uses D19 replay anchors | D20 sections 4.4 and 4.6 | Places closed-head validation before replay |
| Evidence-tree v1 producer pipeline starts from live row or manual closed head | evidence-tree v1 `:1285-1321` | Local context only; no internal schema adoption |

## 7. Consequences

### 7.1 User-visible consequences

Users get two supported explanation paths:

- `row.explain()` for the common live-row path;
- `fg.eval.explain(expr, head=row.close(), ...)` for explicit manual replay.

Detached rows remain data-only. Their `.bindings`, `.claim`, and `.evidence_ref` stay readable, but `.close()` and `.explain()` raise `DetachedRowError`.

Projection rows can be closed for manual replay without exposing projection placeholder atoms.

### 7.2 Implementation consequences

The implementation needs a private closed-head constructor that has access to:

- the owning `EvaluateResult`;
- the row;
- the result head Rule;
- schema identity metadata;
- the T4.3 closed-head validation helper.

The constructor should append closure atoms deterministically and then validate the produced Rule through the same D15 strict closed-head logic used by manual explain.

D21 increases the importance of stable row bindings normalization: row binding values must be sufficient to construct D15 closure atoms for every head port.

### 7.3 Downstream consequences

D22 may build why-not behavior on top of D20 failure classes, but it must not redefine `row.close()`.

D23 hard-cut work must update docs and old shells so they do not present old `accept` / `diagnose` paths as substitutes for `row.close()` / manual explain.

D25 must compare evaluate and explain semantics using D19 digests; it must not use `closed_head_digest` as a substitute for semantics consistency.

D26 may add adapter-specific evidence support, but it must not change D21's public closed-head construction contract without superseding this decision.

## 8. Acceptance Criteria

- [ ] `row.close()` is live-row only and raises `DetachedRowError` for detached rows.
- [ ] `row.close()` returns an application protocol Rule, described generically until D24 final naming.
- [ ] Closed-head construction preserves non-projection head body atoms and appends deterministic D15 closure atoms.
- [ ] Projection closed-head construction drops D14 placeholder atoms and emits real literal closure atoms.
- [ ] Value ports close with `CmpAtom("eq", port_var, Const(value))`.
- [ ] Entity-ref ports close with primary identity `PredAtom(identity_predicate_id, [entity_ref_var, Const(value)])` atoms.
- [ ] Missing schema metadata for entity-ref closure raises `RuleExprError` in row-close / manual-explain gates.
- [ ] Manual `fg.eval.explain(..., head=closed_head)` validates closed-head status before D20 replay.
- [ ] D21 does not add new public error subclasses, public closed-head DTOs, or new explain entrypoints.
- [ ] D21 does not reopen D15 strict closure forms, D20 Explanation fields, D24 naming, or D26 semantics policy.

## 9. Decision Record

| Date | Stage | Decision | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Adopt live-row `row.close() -> Rule`, D15 strict closed-head construction, projection placeholder stripping, and manual explain closed-head gate. | Drafted after D20 reviewed clean v1; D22 why-not disposition unblocked after review. |
| 2026-05-25 | proposed-amend | Normalize D21 acceptance criteria checkboxes to unchecked draft-state convention. | Addresses Step 4.2 v1 WC1; aligns D21 with D16-D20 and T4 D-doc implementation-time acceptance semantics. |
