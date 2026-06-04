# Task Blueprint Audit: `fg.fields.get` multi-cardinality canonical order alignment

- Blueprint: [2026-06-04_fields-get-canonical-order.md](./2026-06-04_fields-get-canonical-order.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-04 | draft | Blueprint created (Step 4.1) | Claude draft. Scope = A2 multi-only: align `fg.fields.get` multi order to projector canonical sort via shared key; single-cardinality untouched. |
| 2026-06-04 | draft | Step 4.2 review + tightening | Codex source-grounded review found one required scope tightening: `project_view_facts_with_witness(...)` has a second inline canonical sort key, so helper extraction must update both projector paths. Acceptance/pre-impl grep updated accordingly. |
| 2026-06-04 | draft | Step 4.3 preflight (streamlined) | Claude. Read-only verification of both projector callsites, import-cycle, reuse, docs scope. **Verdict PASS — no blockers.** Streamlined (recorded here, no separate branch/doc) per small scope. 1 regression note (PF-5: assert on scalar multi field). |

## Decision Notes

### 2026-06-04 — Preflight findings (Claude, read-only, pre-draft)

- Confirmed divergence: `fields.get` multi → storage/insertion order; snapshot → canonical sorted (`project_view_facts`, `projector.py:85`). Both deterministic, both dedup.
- Canonical key located: `projector.py:85` `tuple(str(part) for part in fact)`, fact from `build_args_for_claim` `(e_ref, *val_atoms)`.
- Test-impact triage (grep `fields.get` across `tests/`):
  - `tests/test_sdk_fields_namespace.py:124` — asserts `("red","blue")` (insertion order) → must update to `("blue","red")`.
  - `tests/test_sdk_fields_namespace.py:125` — already wraps snapshot in `set()` (order-agnostic) → unaffected.
  - Other `fields.get` uses (`:78`, `:82`, `:104`, `:114`, `:131`, `:132`, `:148`, `:189`) are single-value or empty → order-insensitive.

### 2026-06-04 — Scope decision: A2 multi-only (Claude recommendation)

Three options weighed:
- **A1** (sort in SDK with replicated key): minimal but duplicates the projector key (drift risk) + keeps SDK direct-read.
- **A2 multi-only** (chosen): reuse the projector's *shared* canonical key for the multi branch only; single-cardinality `values[-1]` untouched. Consistency-by-construction, no drift, scoped to the reported issue.
- **A2 full** (route `fields.get` entirely through projection): also changes single-cardinality selection (`values[-1]` → `compute_chosen_for_predicate`). Empirically agrees today (probe: 3× set → both "Mike") but broader blast radius beyond the reported multi-ordering issue → **deferred** (separate concern).

Single-cardinality alignment (A2-full) recorded as deferred follow-up, not in this slice.

### Process

- Cross-flip per [[feedback_audit_to_archive_cadence]]: Claude blueprint/preflight/review; Codex Step 4.7 implementation.
- Implementation requires the shared-key refactor (Step 1) to be a pure no-op for projector output — verify projector tests unchanged.

### 2026-06-04 — Step 4.2 review tightening (Codex)

Rule 1 source reread:
- `src/factgraph/core/view/projector.py:85` sorts plain projected facts with `tuple(str(part) for part in fact)`.
- `src/factgraph/core/view/projector.py:156` sorts witness projected facts with the same inline key over `row.fact_tuple`.
- `src/factgraph/sdk/store.py:854-862` decodes active claims in storage order and only branches on `cardinality == "multi"` after decode.
- `tests/test_sdk_fields_namespace.py:124-125` is the only direct multi-order assertion pair: line 124 is order-sensitive storage-order expectation; line 125 is currently order-insensitive via `set(...)`.

Tightening applied:
- **P1 Required** — The named helper extraction must update **both** projector paths (`project_view_facts` and `project_view_facts_with_witness`), not only the plain projection path. Otherwise `projector.py` would still carry a duplicate canonical key and the "single source of truth" goal would be false.
- **P2 Recommended** — The consistency regression should be order-sensitive. Tightening existing line 125 from `set(snapshot.tags)` to direct tuple equality is the smallest regression because it asserts `fields.get(...) == entities.get(...).tags` at the same cell.
- **P3 Recommended** — Step 4.6.5 should grep for remaining inline `tuple(str(part) for part in ...)` projector sort keys in addition to other `fields.get` order assertions.

### 2026-06-04 — Step 4.3 preflight (Claude, streamlined, read-only)

Scope decision: streamlined preflight recorded in this audit log (no separate `workflow/audit/` doc, no independent branch) — proportionate to the small slice (2 source files, 1 test update; bug-fix-in-established-surface + pure refactor). Standalone-preflight criteria (subtractive / cross-module protocol / namespace migration / historical-compat / pre-release) do not apply.

Findings (all verified against shipped source):

- **PF-1 (confirm Codex P1)** — Both projector sort callsites use the identical inline key over a `build_args_for_claim(...)` fact tuple: `projector.py:85` `key=lambda fact: tuple(str(part) for part in fact)`; `projector.py:156` `key=lambda row: tuple(str(part) for part in row.fact_tuple)`. A single `canonical_fact_sort_key(fact_tuple)` serves both (plain passes `fact`, witness passes `row.fact_tuple`; both are `build_args_for_claim` outputs).
- **PF-2 (no circular import)** — `core/view/projector.py` imports only `core.policy.*` + `core.store._support` + `core.store.ledger`; it does **not** import `sdk`. So adding `from factgraph.core.view.projector import build_args_for_claim, canonical_fact_sort_key` to `sdk/store.py` is a safe one-directional sdk→core import.
- **PF-3 (reuse OK)** — `build_args_for_claim(ledger, claim)` is module-level/exportable; `_SDKFieldsManager` already has `self._sdk.ledger`. Multi branch can sort active claims by `canonical_fact_sort_key(build_args_for_claim(self._sdk.ledger, claim))` then decode.
- **PF-4 (refactor is pure no-op)** — Helper body == the existing lambda expression, so both projection outputs are byte-identical after extraction. Codex must confirm projector tests unchanged (no golden-order churn).
- **PF-5 (regression must use a SCALAR multi field)** — Full-tuple equality `fg.fields.get(f, ref) == fg.entities.get(...).f` holds for scalar multi fields (e.g. `tags: list[str]`). For **entity_ref** multi fields, `fields.get` (`_decode_claim_value`) and snapshot (`_hydrate_value` → `EntityRef`) may differ in value **representation** even when ORDER matches — so the consistency regression must assert on a scalar multi field. Existing `test_sdk_fields_namespace.py:124-125` uses scalar `tags` → already satisfied.
- **PF-6 (docs scope confirmed minimal)** — `three_layer_api.md:208` is type-accurate but order-silent; `schema_definition.md` §1.3 carries the dedup/tuple note. Each needs a one-line addition: "`fields.get` multi order == snapshot canonical order." No other doc references the multi read order.

Verdict: **PASS, no blockers.** Plan in §5/§8 is accurate and implementable as written (with Codex's 4.2 tightenings). Ready for Step 4.5/4.6 self-check + scope freeze → 4.6.5 grep → 4.7 impl (Codex).
