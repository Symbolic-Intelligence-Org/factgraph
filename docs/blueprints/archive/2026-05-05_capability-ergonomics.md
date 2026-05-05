# Capability Ergonomics(Batch 2 of Round Story Completion Plan)

- Status: implemented
- Created: 2026-05-05
- Last Updated: 2026-05-05
- Parent: [2026-05-05_round-story-completion-plan.md](../active/2026-05-05_round-story-completion-plan.md) §5.2
- Scope: Batch 2 — application-layer helper / normalizer only
- Branch: `v0.1-capability-ergonomics-2026-05-05`(off `49dfc9a`)
- Related Modules:
  - `src/kernel/application/`
  - `src/kernel/application/docs/`
  - `src/kernel/tests/`
  - `examples/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/blueprints/archive/2026-05-05_canonical-round-story.md](../archive/2026-05-05_canonical-round-story.md)
- Audit Log:
  - [2026-05-05_capability-ergonomics.audit.md](./2026-05-05_capability-ergonomics.audit.md)

## 1. Problem

Batch 1 made the Q1-Q5 round story readable, but the example still has too much mechanical setup around three shipped surfaces:

- Q3 Fact Overlay manually constructs `FactValueOverride` from assertion ids, predicate ids, old tuples, and new tuples.
- Q4 Why-not manually sorts each candidate binding even though the plan head already declares the required variable order.
- Q5 Frontier manually projects a `Store` into `view_facts` before calling evaluator-layer `evaluate_native_where_frontier(...)`.

Those mechanics are stable application-layer chores, not new semantics. Leaving them in examples makes future Batch 3+ scenario work harder to read and invites users to copy low-level glue.

## 2. Goals

- Add focused application-layer helpers that reduce setup for Q3 / Q4 / Q5.
- Preserve existing protocol DTOs and runtime behavior exactly.
- Keep helpers in `kernel.application`, not `kernel.sdk`.
- Add focused tests plus 1-2 example updates that show the helpers without changing the round story semantics.

## 3. Non-goals

- No `kernel.sdk` shell or `SDKStore.{check, diagnose, fact_overlay, why_not}` method.
- No protocol DTO field changes, status enum changes, or request/result shape changes.
- No changes to `check_fact_overlay_binding`, `check_why_not_universe`, or `evaluate_native_where_frontier` algorithms.
- No Batch 3 `EvaluationOverlay` container, fact add/remove actions, rule ops, persistence, or proof-frame behavior.
- No cross-engine capability schema or new engine support.

## 4. Current Context

- Fact Overlay DTO: `FactValueOverride(asrt_id, pred_id, e_ref, old_fact_tuple, new_fact_tuple, note)`.
- Why-not DTO: `WhyNotUniverseRequest(plan, candidate_universe, engine)` validates complete head-variable bindings from `plan.heads[0].head_var_names`.
- Frontier entrypoint: `kernel.core.rules.frontier.evaluate_native_where_frontier(view_facts, where, ...)`.
- Schema helpers already exist in `kernel.application.schema_runtime`: `field_predicate`, `field_value_type`, `entity_type_from_ref`.
- Projection helpers already exist in `kernel.core.view.projector`: `project_view_facts`, `project_view_facts_with_witness`.

## 5. Proposed Shape

Add one application helper module, `src/kernel/application/capability_helpers.py`, exported from `kernel.application`:

1. `build_fact_value_override(store, index, *, e_ref, field, new_value, note=None) -> FactValueOverride`
   - `field` is existing `FieldPath`.
   - Finds the current projected active fact for `(field.pred_id, e_ref)`.
   - Builds `old_fact_tuple` from the current projected fact and `new_fact_tuple=(e_ref, normalized_new_value)`.
   - Supports current single-value scalar fields first. Entity-ref fields or non-single arity may raise a precise helper error instead of guessing.

2. `build_why_not_candidate_universe(plan, candidates) -> tuple[BindingItems, ...]`
   - Uses `plan.heads[0].head_var_names` as the canonical variable order.
   - Accepts candidate rows as mappings keyed by head var names or sequences aligned to head var order.
   - Returns normalized `BindingItems` rows accepted by `WhyNotUniverseRequest`.

3. `build_frontier_view_facts(store) -> dict[str, list[tuple[Any, ...]]]`
   - Projects `Store` into the `view_facts` shape expected by `evaluate_native_where_frontier(...)`.
   - Does not import or call `kernel.core.rules.frontier`, preserving the evaluator/application layer-separation drift gate.

Define a small `CapabilityHelperError(ValueError)` for misuse such as missing active field fact, mismatched entity type, unsupported field arity, or incomplete candidate row.

## 6. Boundaries And Invariants

- Helpers are deterministic adapters over existing DTOs/functions.
- Helpers do not write the ledger and do not mutate the store.
- Helpers do not import from `kernel.sdk`.
- Helpers do not call sibling runtime functions.
- Helpers do not import `kernel.core.rules.frontier`; the frontier helper is projection-only.
- Existing DTO validation remains authoritative; helper validation only catches ergonomic mistakes earlier with clearer messages.

## 7. Acceptance

- [ ] Q3 helper builds the same `FactValueOverride` as the manual demo path for Alice age override.
- [ ] Q3 helper rejects missing active facts and entity/field mismatches with `CapabilityHelperError`.
- [ ] Q4 helper builds a valid complete `candidate_universe` from mapping rows and sequence rows.
- [ ] Q4 helper rejects incomplete rows before `WhyNotUniverseRequest` construction.
- [ ] Q5 helper returns the same `view_facts` as manual `project_view_facts(...)`.
- [ ] Existing Q3/Q4/Q5 capability focused tests still pass.
- [ ] `examples/11_capabilities_e2e_demo.py` uses the helpers without changing assertions or output semantics.
- [ ] `src/kernel/application/docs/01_overview.md` and `_en.md` mention the helper module.
- [ ] No `kernel.sdk` files are modified.

## 8. Implementation Plan

1. Add `src/kernel/application/capability_helpers.py` with the three helpers and `CapabilityHelperError`.
2. Export helpers from `src/kernel/application/__init__.py`.
3. Add `src/kernel/tests/test_application_capability_helpers.py`.
4. Update `examples/11_capabilities_e2e_demo.py` to use helpers for phases 3, 4, and 5.
5. Update `src/kernel/application/docs/01_overview.md` and `_en.md`.
6. Run focused tests:
   - `python -m unittest src.kernel.tests.test_application_capability_helpers`
   - `python -m unittest src.kernel.tests.test_examples_capabilities_demo`
   - existing fact-overlay / why-not / frontier focused tests, including application-layer no-frontier-import drift gate
   - `python -m ruff check src/kernel examples/11_capabilities_e2e_demo.py`

## 9. Docs To Update

- `src/kernel/application/docs/01_overview.md`
- `src/kernel/application/docs/01_overview_en.md`

No `docs/README.md` update expected; this is module-level API documentation, not a new durable docs section.

## 10. Outcome / Deviations

- 最终落地结果:added `kernel.application.capability_helpers` with `build_fact_value_override(...)`, `build_why_not_candidate_universe(...)`, and `build_frontier_view_facts(...)`;exported them from `kernel.application`;updated the capabilities E2E demo to consume the helpers;added focused helper tests;updated application module docs.
- 与 blueprint 不同的地方:the original scoped shape briefly named `evaluate_store_native_where_frontier(...)`, but implementation narrowed Q5 to projection-only `build_frontier_view_facts(...)`.
- 为什么会有这些调整:the existing evaluator frontier drift gate correctly forbids application-layer imports of `kernel.core.rules.frontier`;projection-only ergonomics satisfies Batch 2 while preserving layer separation.
- 归档说明:no SDK files, protocol DTOs, status enums, or runtime algorithms changed;focused and full kernel verification passed.
