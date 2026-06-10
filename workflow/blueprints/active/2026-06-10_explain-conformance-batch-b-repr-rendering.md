# Task Blueprint: Explain Conformance Batch B — unified repr value rendering

- Status: draft
- Created: 2026-06-10
- Last Updated: 2026-06-10
- Type: conformance rework batch
- Parent: [2026-06-10_explain-conformance-rework.md](./2026-06-10_explain-conformance-rework.md)
- Related Modules:
  - `src/factgraph/application/explain/prober.py` (`repr_text` baking; primary edit target)
  - `src/factgraph/application/schema_runtime.py` (`render_entity_repr(...)`; display-only identity text)
  - `src/factgraph/core/protocol/tup_v1.py` (canonical float64 decode helper, if needed)
  - `tests/application/explain/test_prober.py` (prober repr regressions)
  - `tests/test_application_schema_runtime.py` (entity repr rendering regressions)
  - `tests/sdk/test_explain_conformance_native.py` (native conformance battery)
- Audit Log:
  - [2026-06-10_explain-conformance-batch-b-repr-rendering.audit.md](./2026-06-10_explain-conformance-batch-b-repr-rendering.audit.md)

---

## 1. Problem

Native explanation `repr_text` still renders values through scattered
case-specific string conversion.

`%ENT` was repaired in the earlier Bug 2 fix, but the remaining render paths
still call `_term_display(...)` without schema or view context:

- `%FLD` inside `_repr_fact(...)`;
- fact fallback text;
- compare atoms;
- builtin atoms;
- true-unbound `NotReached` terms after Batch D.

As a result, encoded values leak into human-readable explanation prose:

- encoded `idref_v1:...` values appear instead of entity labels;
- canonical `float64` hex appears instead of numeric text;
- true-unbound internal `$...` variable names appear in failed paths;
- `render_entity_repr(...)` can corrupt labels through sequential
  `str.replace(...)` when placeholders share prefixes or field values contain
  placeholder-looking text.

This is a presentation correctness batch. It must not change evaluation,
identity, digest, seed, verdict, or adapter behavior.

## 2. Goals

1. Route all prober value rendering through one renderer path.
2. Make `%ENT`, `%FLD`, compare, builtin, and fact fallback rendering share
   entity-ref and scalar display behavior.
3. Decode canonical `float64` hex only for display.
4. Make `render_entity_repr(...)` single-pass so placeholder replacement is not
   order-dependent and values are not reinterpreted as templates.
5. Replace true-unbound internal `$...` names with a friendly placeholder in
   display text.
6. Preserve Batch A row anchoring, Batch D verdict semantics, and existing
   digest/identity semantics.

## 3. Non-goals

- Do not change `_normalize_identity_value(...)`, `materialize_identity(...)`,
  `resolve_selector(...)`, `encode_entity_ref(...)`, or any identity/digest
  semantics.
- Do not change row seed construction. Batch A owns that.
- Do not change verdict cascade behavior. Batch D owns that.
- Do not change NotAtom structural rendering. Batch C owns Bug 6.
- Do not change DTOs, adapter dispatch, or support-capture.
- Do not turn epoch-nanos `time` values into formatted timestamps in this
  batch. No time display policy is locked; current integer display remains the
  conservative behavior.

## 4. Source Preflight

Confirmed source facts:

- `prober.py:_bake_repr_text(...)` already receives `schema_index` and
  `view_facts`.
- `_repr_fact(...)` receives `view_facts`, but only `%ENT` uses it through
  `_entity_repr_for_fact(...)`.
- `%FLD`, fact fallback, `_repr_compare(...)`, and `_repr_builtin(...)` call
  `_term_display(...)`.
- `_term_display(...)` currently accepts no `schema_index` / `view_facts`
  context and falls back to `str(value)` for anything except `EntityRef`.
- `_entity_repr_for_fact(...)` has the proven idref recovery shape using
  `_recover_identity_from_predicates(...)` plus `render_entity_repr(...)`.
- `schema_runtime.render_entity_repr(...)` currently uses ordered
  `str.replace(...)` for `%CLS` and identity placeholders.
- `_identity_value_text(...)` is display-only and feeds `render_entity_repr`.
- `materialize_identity(...)` is public runtime normalization used by
  `resolve_selector(...)` and `entity_view._recover_identity_from_predicates`.
  It must remain semantic, not display-oriented.
- `tup_v1.FLOAT64_HEX_RE` and `_float64_bits(...)` already encode/validate
  canonical float64 hex; display decoding should reuse this module rather than
  duplicate bit logic.
- Epoch-nanos `time` values are represented as integers in the protocol. No
  audited defect requires changing their display.

## 5. Proposed Shape

### 5.1 Unified prober renderer

Replace the narrow `_term_display(term)` function with a context-aware renderer,
for example:

```python
def _render_term_value(
    term: BoundVar | Const | None,
    *,
    schema_index: object | None,
    view_facts: dict[str, list[tuple[Any, ...]]],
) -> str:
    ...
```

All native prober text paths should call it:

- `%ENT` through `_entity_repr_for_fact(...)`;
- `%FLD`;
- fact fallback;
- compare atoms;
- builtin atoms.

Rendering behavior:

- `EntityRef` instances: use `render_entity_repr(...)` when possible; otherwise
  keep the existing safe fallback.
- encoded `idref_v1:<EntityType>:...` strings: parse entity type from the token,
  recover identity from visible facts with `_recover_identity_from_predicates`,
  then call `render_entity_repr(...)`. Fallback gracefully to the encoded token
  if identity is not visible.
- canonical `float64` hex strings: display as the decoded finite float.
- `BoundVar(value=None)`: display a friendly placeholder such as
  `<unbound>` or `<unbound:name>` instead of raw internal `$...`. Exact wording
  is an implementation choice, but raw `$` variable names should not appear in
  human text for true-unbound `NotReached` atoms.
- other values: keep current string behavior.

`_entity_repr_for_fact(...)` may become a thin wrapper around the shared
renderer with an explicit entity-type hint, or it may stay separate as long as
all idref/entity/float display logic is centralized and reused.

### 5.2 Float64 display helper

Expose a small helper from `core/protocol/tup_v1.py`, for example:

```python
def display_float64_value(value: Any) -> str:
    ...
```

It should reuse the existing canonical float validation / bit normalization.
For canonical hex input, decode to a finite Python float and return display
text. For native float input, preserve finite float behavior. Avoid duplicating
`struct.unpack(...)` logic outside `tup_v1`.

The helper is display-only. It must not change `encode_value_bytes(...)`,
`_val_atom_for_claim_arg(...)`, `_normalize_identity_value(...)`, or any
canonical bytes/digest path.

### 5.3 Single-pass `render_entity_repr(...)`

Replace sequential `str.replace(...)` with one-pass placeholder substitution.
Implementation options are open:

- regex substitution over `%CLS|%<identity_field>` tokens; or
- a small scanner that emits literal/template tokens once.

Required semantics:

- `%CLS` renders the entity type.
- `%<identity field>` renders the corresponding identity value with
  `_identity_value_text(...)`.
- field values containing `%...` text are emitted literally and are not
  reprocessed as placeholders.
- shared prefixes such as `%org` and `%org_unit` cannot corrupt each other.
- unknown placeholders remain unchanged or follow the existing template
  validation assumptions; do not widen template syntax in this batch.

### 5.4 Display-only identity float decode

Add float64 decode at `_identity_value_text(...)`, because it is the display
edge for entity labels.

Do **not** decode inside `_normalize_identity_value(...)` or
`materialize_identity(...)`. Keeping canonical hex in materialized identity is
part of runtime/storage compatibility; only text rendering should become
human-readable.

## 6. Boundaries And Invariants

- **INV-display-only**: Batch B changes only text rendering. Identity values,
  entity refs, canonical bytes, claim digests, row digests, result digests, and
  schema digests do not change.
- **INV-one-renderer**: `%FLD`, compare, builtin, and fact fallback share the
  same term rendering behavior. `%ENT` may keep entity-subject-specific wrapper
  logic but must not have a separate idref/float display implementation.
- **INV-graceful-fallback**: if idref identity cannot be recovered from visible
  facts, display falls back to the original token and does not raise.
- **INV-Batch-A/D**: row anchoring and verdict cascade semantics remain green.
- **INV-Batch-C-boundary**: NotAtom structural rendering remains out of scope.

## 7. Acceptance

- [ ] `%FLD` entity-ref values render friendly entity labels, not raw
  `idref_v1:...`, including cross-type fields such as `Employee.dept: Dept`.
- [ ] Compare atoms with entity-ref operands render friendly entity labels.
- [ ] Fact fallback and builtin operands use the same renderer behavior.
- [ ] Canonical `float64` hex renders as numeric text in `%FLD` and compare /
  builtin text.
- [ ] Float64 identity values render as numeric text through
  `render_entity_repr(...)`, while `materialize_identity(...)` still returns the
  existing normalized identity representation.
- [ ] `render_entity_repr(...)` handles prefix-collision placeholders such as
  `%org` / `%org_unit` and value-injection cases where identity values contain
  `%...` text.
- [ ] True-unbound `NotReached` repr text no longer exposes raw internal `$...`
  variable names.
- [ ] Non-entity and non-float repr output remains stable.
- [ ] Batch A row-anchoring, Batch D cascade, aggregate Batch E, and adapter
  dispatch cohorts remain green.
- [ ] No implementation diff in seed builder, verdict semantics,
  support-capture, DTOs, or adapter converters.

## 8. Implementation Plan

1. Add focused tests for `render_entity_repr(...)` prefix-collision and
   value-injection cases.
2. Add display-only float64 tests for `_identity_value_text(...)` through
   `render_entity_repr(...)`, plus a guard that `materialize_identity(...)`
   remains unchanged.
3. Add native prober tests for entity-ref `%FLD`, compare operands, builtin
   operands, float64 `%FLD`, and true-unbound `NotReached` display.
4. Expose a float64 display helper in `tup_v1.py` if implementation needs it.
5. Convert `render_entity_repr(...)` to single-pass replacement.
6. Thread `schema_index` and `view_facts` through `_repr_compare(...)`,
   `_repr_builtin(...)`, `_fact_fallback_repr(...)`, and the unified term
   renderer.
7. Reuse `_recover_identity_from_predicates(...)` for encoded idref display.
8. Run focused prober/schema_runtime tests and the broader conformance cohort.
9. If rendering requires a new helper outside `prober.py`, document the
   placement and keep it display-only.

## 9. Docs To Update

No public docs expected in this batch unless tests or implementation reveal
existing docs that claim raw encoded values are expected. Final conformance
cleanup may summarize the native repr fidelity battery.

## 10. Outcome / Deviations

Pending.
