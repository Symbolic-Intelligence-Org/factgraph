# Task Blueprint: `fg.fields.get` multi-cardinality canonical order alignment

- Status: implemented
- Created: 2026-06-04
- Last Updated: 2026-06-04 (Step 4.8 closure)
- Related Modules:
  - `src/factgraph/sdk/store.py` (`_SDKFieldsManager.get` / `_active_claims_for_field`)
  - `src/factgraph/core/view/projector.py` (canonical fact sort key)
- Related Docs:
  - [`docs/quickstart/schema_definition.md`](../../../docs/quickstart/schema_definition.md) §1.3
  - [`docs/quickstart/three_layer_api.md`](../../../docs/quickstart/three_layer_api.md) §3
- Audit Log:
  - [2026-06-04_fields-get-canonical-order.audit.md](./2026-06-04_fields-get-canonical-order.audit.md)
- Cross-flip: Claude drafts blueprint / preflight / review; Codex implements (Step 4.7).

## 1. Problem

`fg.fields.get(field, ref)` returns **multi-cardinality** values in ledger **storage order** (insertion / rowid), while the entity snapshot (`fg.entities.get(...).field`) and views return values in **canonical sorted order** (via `project_view_facts`). Two read surfaces over the same cell return different orders — an undocumented, surprising inconsistency.

Verified (preflight, 2026-06-04):
- `fg.fields.get(items)` → `('cherry','apple','banana')` (insertion order)
- snapshot `.items` → `('apple','banana','cherry')` (canonical sorted)
- Both deterministic across reload; both deduplicate.

Root cause:
- `fg.fields.get` → `_active_claims_for_field` (`store.py:757`) → `ledger.find_claims` (storage order) → decode → `tuple`. **No sort.**
- snapshot → `project_view_facts` (`core/view/projector.py:117`) → per-predicate `sorted(facts, key=lambda fact: tuple(str(part) for part in fact))` (`projector.py:85`).

Surfaced during quickstart demo work + the entity-repr design discussion.

## 2. Goals

- `fg.fields.get` multi-cardinality returns values in the **same canonical order** as snapshot / views.
- **Consistency-by-construction**: reuse the projector's canonical sort key (single source of truth), not a duplicated/parallel sort — so the two surfaces cannot drift.

## 3. Non-goals

- **Do NOT change single-cardinality `fields.get`**: it currently returns `values[-1]` (last active claim). Routing single through the projector's `compute_chosen_for_predicate` policy is a *separate* behavior change (the "A2-full" option) — explicitly **out of scope** here. Single-cardinality path stays byte-for-byte unchanged.
- Do NOT change snapshot / view behavior (already canonical + correct).
- Do NOT change dedup or tuple-return semantics (inherent to content-addressing; see `schema_definition.md` §1.3).
- Do NOT change `fg.assertions` history-view ordering (`(ingested_at, asrt_id)` — its own purpose).

## 4. Current Context

- `fg.fields.get` entry: `src/factgraph/sdk/store.py:854` (`_SDKFieldsManager.get`); claims fetched via `_active_claims_for_field` (`store.py:757`), decoded via `_decode_claim_value` (`store.py:767`). Multi branch: `return tuple(values)` (`store.py:860`).
- Canonical sort key (the target order): `core/view/projector.py:85` — `sorted(facts, key=lambda fact: tuple(str(part) for part in fact))`, where `fact = build_args_for_claim(ledger, claim)` (`projector.py:90-114`, returns `(e_ref, *val_atoms)`).
- Both `fields.get` and the projector ultimately read the same active claims; only the projector sorts.
- Constraint: data substrate is binary (`pred(subject, single value)`, user-confirmed) — each multi claim has one value atom.

## 5. Proposed Shape (A2 — shared canonical key, multi-only)

1. **`src/factgraph/core/view/projector.py`**: extract the inline sort key (line 85's lambda) into a **named exported helper**, e.g. `canonical_fact_sort_key(fact: tuple) -> tuple[str, ...]`; refactor both `project_view_facts(...)` and `project_view_facts_with_witness(...)` to call it. This makes the canonical order a single named source of truth across both plain and witness projection surfaces.
2. **`src/factgraph/sdk/store.py`** `_SDKFieldsManager.get` (or a private helper it calls): for the **multi-cardinality branch only**, sort the active claims by `canonical_fact_sort_key(build_args_for_claim(self._sdk.ledger, claim))` before decoding — mirroring `projector.py:84-85` exactly, reusing `build_args_for_claim` + `canonical_fact_sort_key`. Single-cardinality branch unchanged.

This guarantees `fields.get` multi order == snapshot order by construction (same fact-building + same key), without projecting the whole view per `get` and without touching single-cardinality selection.

## 6. Boundaries And Invariants

- Single-cardinality `fields.get` semantics unchanged (`values[-1]`).
- Dedup + `tuple` return preserved.
- No change to ledger storage, claim model, digests, or view projection.
- Sort key must be the **same function** the projector uses (no duplicated key logic).
- `projector.py` must not retain a second inline `tuple(str(part) for part in ...)` fact-sort key after the helper extraction; both projection paths use the named helper.
- Sacred 5-path 0-diff + master untouched (this fix does not touch those paths).

## 7. Acceptance

- [ ] `fg.fields.get(multi_field, ref)` returns the same order as `fg.entities.get(...).field` for the same cell (asserted by a new regression test).
- [ ] Single-cardinality `fields.get` behavior unchanged (existing tests pass without edits to single-cardinality assertions).
- [ ] Canonical sort key is shared (one named function used by both projector and `fields.get`).
- [ ] `project_view_facts(...)` and `project_view_facts_with_witness(...)` both use the named helper; no duplicate inline canonical fact-sort key remains in `projector.py`.
- [ ] `tests/test_sdk_fields_namespace.py:124` updated to the new canonical order `("blue","red")`.
- [ ] `tests/test_sdk_fields_namespace.py:125` becomes an order-sensitive equality assertion (not only `set(...)`) or an equivalent new regression asserts `fields.get(...) == entities.get(...).tags`.
- [ ] Full targeted suite green; no other multi-order assertions broken.
- [ ] Affected docs synced (`schema_definition.md` §1.3 / `three_layer_api.md` §3 — note that `fields.get` and snapshot now share canonical order).

## 8. Implementation Plan

1. `[src/factgraph/core/view/projector.py]` Extract `canonical_fact_sort_key(fact)` named helper; refactor both current inline key callsites (`project_view_facts` and `project_view_facts_with_witness`) to use it; export it. (Pure refactor, no behavior change — projector output identical.)
2. `[sdk/store.py]` In `_SDKFieldsManager.get` multi branch, sort active claims by `canonical_fact_sort_key(build_args_for_claim(ledger, claim))` before decode. Single branch untouched.
3. `[tests]` Update `test_sdk_fields_namespace.py:124` → `("blue","red")`. Add a consistency regression: for a multi field with several added values, assert `fields.get(...) == entities.get(...).field`; the existing line 125 `set(...)` assertion is the natural place to tighten into order-sensitive equality.
4. `[Step 4.6.5 pre-impl grep]` Codex greps for any other multi-cardinality `fields.get` order assertions before editing, and greps `projector.py` for remaining inline `tuple(str(part) for part in ...)` sort keys after the helper extraction.
5. `[docs]` Small sync: `schema_definition.md` §1.3 + `three_layer_api.md` §3 note that `fields.get` multi order == snapshot canonical order.

## 9. Docs To Update

- `docs/quickstart/schema_definition.md` §1.3 (canonical-order note)
- `docs/quickstart/three_layer_api.md` §3 (fields.get read order)
- No new durable docs entry → `docs/README.md` unchanged.

## 10. Outcome / Deviations

**Outcome (Step 4.8 closure, 2026-06-04):** implemented as scoped, no deviations.

- `core/view/projector.py`: extracted `canonical_fact_sort_key(fact)` (the prior inline `tuple(str(part) for part in ...)`); both `project_view_facts` (line 85) and `project_view_facts_with_witness` (line 160) now call it. Pure no-op for projector output (verified — 59 view/projector/witness/walker consumer tests unchanged green).
- `sdk/store.py` `_SDKFieldsManager.get`: multi branch sorts active claims by `canonical_fact_sort_key(build_args_for_claim(self._sdk.ledger, claim))` before decode → matches snapshot canonical order by construction. **Single-cardinality branch unchanged** (`values[-1]`), per §3 non-goal.
- `tests/test_sdk_fields_namespace.py`: line 124 `("red","blue")` → `("blue","red")`; line 125 tightened from `set(...)` to order-sensitive `fields.get(...) == entities.get(...).tags` (scalar `tags`, per PF-5).
- Docs: `three_layer_api.md` §3 + `schema_definition.md` §1.3 each note that `fields.get` multi order == snapshot canonical order.

**Deviations:** none. All §7 acceptance items met. Codex's two 4.2 tightenings (both projector paths; order-sensitive regression) honored.

**Independent verification (Claude, Step 4.8):** `tests/test_sdk_fields_namespace.py` + `tests/sdk` + `tests/application/protocol` → 268 passed; view/projector/witness consumers (entity_view / walker_views / souffle witness / frozen_view / namespace_removal) → 59 passed. Projector refactor confirmed no-op. (Note: Codex's env returned no pytest output; Claude re-ran under a working pytest as the real gate.)

**Sacred:** the 3 impl commits (`3ba06fa2` / `65def873` / `0898f902`) touch only `projector.py` / `store.py` / tests / docs / blueprint — none in the Q-PR1 5-path. Master unchanged.

**Deferred follow-up:** single-cardinality `fields.get` alignment to `compute_chosen_for_predicate` (the "A2-full" option) remains out of scope — recorded in audit Decision Notes.

**Archive note:** ready for Step 4.9 archive (git-mv blueprint pair to `workflow/blueprints/archive/` + INVENTORY entry) once user authorizes.
