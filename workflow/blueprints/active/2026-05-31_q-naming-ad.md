# Q-NAMING-AD Blueprint: Assertions naming polish + Persistence rename

- Status: scoped
- Created: 2026-05-31
- Last Updated: 2026-05-31
- Related Modules:
  - `src/factgraph/sdk/` (SDK facade — primary blast radius)
  - `src/factgraph/core/store/` (FrozenAssertionView core class — dual rename per §4.2)
  - `src/factgraph/application/` (audit query consumers — semantic boundary preserved)
- Related Docs:
  - [`workflow/design/decisions/active/2026-05-31_q1-naming-api-polish-decision.md`](../../design/decisions/active/2026-05-31_q1-naming-api-polish-decision.md) — Q-NAMING decision §4.2 + §4.5 + §4.8 (adopted at `f1a017ec`)
  - [`workflow/audit/active/2026-05-31_naming-polish-feasibility.md`](../../audit/active/2026-05-31_naming-polish-feasibility.md) — feasibility audit §2 (Batch A) + §5 (Batch D) at `10de33b9`
  - [`workflow/foundations/architecture_principles.md`](../../foundations/architecture_principles.md) §2.1 layer authority
- Audit Log:
  - [2026-05-31_q-naming-ad.audit.md](./2026-05-31_q-naming-ad.audit.md)

## 1. Problem

PDF "Change Requests for FactGraph" identified user-experience polish opportunities on the public Assertions and Persistence surfaces. Q-NAMING decision §4.2 (Batch A, 800 hits / 146 files, Yellow risk) and §4.5 (Batch D, 299 hits / 43 files, Yellow risk) lock five Assertions renames and two Persistence renames as adopted. This blueprint implements both batches as the first Q-NAMING sub-slice — the lowest-risk phase per Q-NAMING §4.9 — to validate the cross-slice cadence before the higher-risk B/C/E/F sub-slices.

Combining Batch A + Batch D into one slice is supported by audit §9 recommendation (Q-NAMING-A/D = "smallest useful slice") and Q-NAMING §4.9 Phase 1.

## 2. Goals

- G1: Rename `fg.views` → `fg.assertion_views` (SDK namespace manager) per §4.2 hard-cut.
- G2: Rename `FrozenAssertionView` → `FrozenAssertionSet` on **both** the SDK-facing class at [`src/factgraph/sdk/store.py:135`](../../../src/factgraph/sdk/store.py) and the core database-facing class at [`src/factgraph/core/store/database.py:75`](../../../src/factgraph/core/store/database.py) per §4.2 (wider scope explicitly accepted).
- G3: Add `strict=True` flag to `by_ids` on **every** public by-ids surface (top-level [`sdk/store.py:456`](../../../src/factgraph/sdk/store.py) + assertion view [`sdk/facade.py:263`](../../../src/factgraph/sdk/facade.py)) with explicit missing-ID and duplicate-ID raise behavior. Default `strict=False` preserves current permissive behavior.
- G4: Change `fg.audit.explain_fact(pred_id, e_ref)` public signature → `fg.audit.explain(asrt_id | record)`. **Semantic preservation**: `fg.audit` continues to explain chosen-policy among multiple active claims (NOT derivation reasoning). Core query helper at [`src/factgraph/core/store/_queries.py:13`](../../../src/factgraph/core/store/_queries.py) may remain private under existing name (`explain_fact`).
- G5: Change `fg.audit.conflicts(pred_id, e_ref)` public signature → `fg.audit.conflicts(record | entity, field)`. Same semantic preservation — returns active-claim set + policy-chosen winner.
- G6: Rename `fg.save(...)` → `fg.save_workspace(...)` per §4.5 hard-cut. Covers `SDKStore.save` at [`sdk/store.py:2847`](../../../src/factgraph/sdk/store.py). **EXCLUDES** `sdk/batch.py:1189` per Step 4.2 review finding P2-1: that `save(obj, *, include_deps, meta)` is a batch commit alias forwarding to `self.commit(...)`, returning `BatchCommitResult` — it is **NOT** workspace persistence and is therefore out of Batch D scope.
- G7: Rename `FactGraph.load(...)` classmethod → `FactGraph.load_workspace(...)` at [`sdk/store.py:1728`](../../../src/factgraph/sdk/store.py).
- G8: All renames are hard-cut per §4.8.1 — no aliases, no dual-emit, old names removed in same commit as new names introduced.
- G9: Workspace file format binary structure unchanged per §4.5 (only method names change).
- G10: Update affected module docs (`src/factgraph/*/docs/`) + current SDK quickstart / examples (`docs/`) in same slice per CADENCE Stage 4.8.

## 3. Non-goals

- N1: Cascade renames in §4.3 (atom → condition, branch → case, class renames). Reserved for Q-NAMING-B1 / B2.
- N2: Flat shell deletion in §4.4. Reserved for Q-NAMING-C.
- N3: Rule/Inference DSL renames in §4.6 (Branch → Case, .where → .when, target+head_vars → emits). Reserved for Q-NAMING-E.
- N4: Engine config renames in §4.7 (ProbLog/PyReason Semantics → Config, SemanticsProfile → EngineProfile, semantics= → config=, etc.). Reserved for Q-NAMING-F.
- N5: PDF Module 1 Schema renames per §4.1 REJECT (Entity.__default_eref_pattern__, Factory IDs, create_with_id, schema strict identity).
- N6: PDF Module 4 Rules/Inferences proposals beyond 4.1 + 4.2 per §4.6.5 REJECT.
- N7: Lower-level core query function rename (`_queries.explain_fact` / `_queries.conflicts`). Public boundary changes only; core helpers may remain private under existing names per §4.2 explicit permission.
- N8: Workspace file format binary structure changes per §4.5.
- N9: Historical workflow / archive material per §4.8.5 carve-out. Only current SDK docs, quickstarts, current examples, and active tests migrate.
- N10: Q-PR1 sacred 5 paths per §4.8.6 — must remain 0-diff vs `4c472b50`.
- N11: Persistence schema digest renames. Reserved for Q-NAMING-F per §4.7.7.

## 4. Current Context

- **当前 SDK 入口**:
  - `fg.views` namespace manager: `_SDKViewsManager` reached via `SDKStore.views` property at [`sdk/store.py:1866`](../../../src/factgraph/sdk/store.py)
  - `FrozenAssertionView`: dual definition at [`core/store/database.py:75`](../../../src/factgraph/core/store/database.py) (core) and [`sdk/store.py:135`](../../../src/factgraph/sdk/store.py) (SDK)
  - `by_ids`: top-level [`sdk/store.py:456`](../../../src/factgraph/sdk/store.py) returns `Any` over assertion ids; facade [`sdk/facade.py:263`](../../../src/factgraph/sdk/facade.py) returns `AssertionRecordSet`
  - `_SDKAuditManager`: defined at [`sdk/store.py:1402`](../../../src/factgraph/sdk/store.py); `explain_fact` and `conflicts` delegate to flat `SDKStore` methods at lines 1417 and 1421
  - Flat `SDKStore.explain_fact` and `SDKStore.conflicts` at lines 3470 / 3473 — these flat shells stay **fully untouched** during Q-NAMING-AD per Step 4.2 review finding P2-2. Q-NAMING-AD changes ONLY the `fg.audit.*` namespace manager surface; flat `SDKStore.explain_fact` / `.conflicts` are C-owned deletion debt (Q-NAMING-C will delete them per §4.4.1). Touching them here would either rename additional flat public shells (out of AD scope) or pre-implement Q-NAMING-C's delete (also out of AD scope).
  - Core query helpers: `_queries.explain_fact` at [`core/store/_queries.py:13`](../../../src/factgraph/core/store/_queries.py) returns `{pred_id, e_ref, active_claims, chosen_asrt_id}`; `_queries.conflicts` at line 51 returns `{pred_id, e_ref, active_asrt_ids, chosen_asrt_id}`
  - `FactGraph.load`: classmethod at [`sdk/store.py:1728`](../../../src/factgraph/sdk/store.py)
  - `SDKStore.save`: instance method at [`sdk/store.py:2847`](../../../src/factgraph/sdk/store.py)
  - Batch save delegation: [`sdk/batch.py:1189`](../../../src/factgraph/sdk/batch.py)

- **当前已知约束**:
  - Q-PR1 sacred 5 paths at 0-diff vs `4c472b50` — must hold through every commit
  - Sacred `master` at `562c74195df43e933bed92a3ff25de94dd8ce666` — never modified
  - Dirty baseline (4 M + 2 D + 2 untracked) preserved at session start (Q-NAMING §4.8.8 lists exact entries)
  - Hard-cut per §4.8.1: no aliases, no dual-emit
  - Workspace file format binary unchanged per §4.5 + G9
  - Audit semantic preservation: `fg.audit` explains chosen-policy, not derivation (G4 / G5)
  - Layer authority per [`workflow/foundations/architecture_principles.md`](../../foundations/architecture_principles.md) §2.1: SDK can call application, application does not import SDK. Core query helpers stay in core.

- **当前相关历史蓝图**:
  - Slice 6 form-i debt cleanup archived at `4c472b50` ([`workflow/blueprints/archive/2026-05-30_form-i-debt-cleanup.md`](../archive/2026-05-30_form-i-debt-cleanup.md)) — predecessor branch base.
  - No prior naming-polish blueprint exists for this surface.

## 5. Proposed Shape

### §5.1 Batch A rename layout

| Surface | Old | New | File:line scope |
|---|---|---|---|
| SDK namespace property | `SDKStore.views` (returns `_SDKViewsManager`) | `SDKStore.assertion_views` (returns `_SDKAssertionViewsManager`) | [`sdk/store.py:1866`](../../../src/factgraph/sdk/store.py) + namespace class definition |
| Core class | `FrozenAssertionView` | `FrozenAssertionSet` | [`core/store/database.py:75`](../../../src/factgraph/core/store/database.py) |
| SDK class | `FrozenAssertionView` | `FrozenAssertionSet` | [`sdk/store.py:135`](../../../src/factgraph/sdk/store.py) |
| Core exports | `__all__` entry `FrozenAssertionView` | `FrozenAssertionSet` | [`core/store/__init__.py:14`](../../../src/factgraph/core/store/__init__.py) (`__all__` tuple) + [`core/store/__init__.py:40`](../../../src/factgraph/core/store/__init__.py) (re-export tuple) — both rows. Confirmed in Step 4.2 review P3-1. |
| SDK exports | `__all__` entry `FrozenAssertionView` (if present) | `FrozenAssertionSet` | `sdk/__init__.py` — Step 4.3 preflight PF-v2 confirmed: full-file grep returns 0 hits, so no `__all__` update required in `sdk/__init__.py`. |
| SDK internal alias (Step 4.3 PF-r2 + Step 4.6.5 N-1) | Import alias `FrozenAssertionView as DatabaseFrozenAssertionView` at [`sdk/store.py:88`](../../../src/factgraph/sdk/store.py) + all internal references | `FrozenAssertionSet as DatabaseFrozenAssertionSet` + all internal references | Step 4.6.5 pre-impl grep exact set: import alias at line 88; internal alias references at lines 175, 313, and 1779. SDK `FrozenAssertionView` class references at lines 135, 384, 408, 430, 437, 3777, 3782, and 3786 are covered by the SDK class rename row above. |
| by_ids top-level | `def by_ids(self, asrt_ids)` | `def by_ids(self, asrt_ids, *, strict: bool = False)` | [`sdk/store.py:456`](../../../src/factgraph/sdk/store.py) |
| by_ids facade | `def by_ids(self, asrt_ids)` | `def by_ids(self, asrt_ids, *, strict: bool = False)` | [`sdk/facade.py:263`](../../../src/factgraph/sdk/facade.py) |
| Audit explain | `fg.audit.explain_fact(pred_id, e_ref, *val_atoms)` | `fg.audit.explain(target)` where `target: str \| AssertionRecord` | [`sdk/store.py:1417`](../../../src/factgraph/sdk/store.py) (`_SDKAuditManager.explain_fact` → `explain`) **only**; manager body calls core `_queries.explain_fact` directly or via a private helper |
| Audit conflicts | `fg.audit.conflicts(pred_id, e_ref)` | `fg.audit.conflicts(target)` where `target: AssertionRecord \| tuple[Entity, str]` | [`sdk/store.py:1421`](../../../src/factgraph/sdk/store.py) (`_SDKAuditManager.conflicts`) **only**; same private-helper / core-direct pattern |

**Out of Q-NAMING-AD scope (Step 4.2 P2-2)**:
- Flat `SDKStore.explain_fact` at [`sdk/store.py:3470`](../../../src/factgraph/sdk/store.py) and flat `SDKStore.conflicts` at [`sdk/store.py:3473`](../../../src/factgraph/sdk/store.py): preserve untouched. These are C-owned deletion debt (Q-NAMING-C §4.4.1). Q-NAMING-AD must NOT rename them to mirror new audit-namespace names (would create new public flat shells `fg.explain` / `fg.conflicts`) AND must NOT delete them (pre-implements Q-NAMING-C).
- Implementation pattern: `_SDKAuditManager.explain` body reaches the core query helper through the existing private path (e.g., direct `_queries.explain_fact` call or an intermediate private helper extracted under `_internal/`). Manager body **does not** call `self._sdk.explain_fact(...)` or any flat shell.

### §5.2 Batch D rename layout

| Surface | Old | New | File:line scope |
|---|---|---|---|
| FactGraph classmethod | `FactGraph.load(path)` | `FactGraph.load_workspace(path)` | [`sdk/store.py:1728`](../../../src/factgraph/sdk/store.py) |
| SDKStore instance method | `SDKStore.save(path)` | `SDKStore.save_workspace(path)` | [`sdk/store.py:2847`](../../../src/factgraph/sdk/store.py) |

**Out of Batch D scope (Step 4.2 P2-1)**:
- [`sdk/batch.py:1189`](../../../src/factgraph/sdk/batch.py) `BatchHandle.save(obj, *, include_deps, meta) → BatchCommitResult` is a batch commit alias forwarding to `self.commit(...)`. Despite name-grep hit it is NOT workspace persistence. Preserve as-is in Q-NAMING-AD. If a future decision wants to rename batch commit aliases, that is a separate Q-decision scope.

Workspace file format binary unchanged (G9).

### §5.3 `strict=True` semantics

Define explicit error model for `by_ids(strict=True)`:

- Missing ID: raise `SDKStoreError("by_ids strict mode: assertion id '{id}' not found")`
- Duplicate ID in input: raise `SDKStoreError("by_ids strict mode: duplicate assertion id '{id}' in input")`
- Default `strict=False` preserves current permissive behavior (caller-visible: same return, missing IDs silently dropped per current behavior)

Implementation must apply to all by-ids public surfaces (G3 enumerates two; preflight Step 4.3 PF-v3 verified no third surface exists).

**§5.3.1 Duplicate-detection placement (Step 4.3 PF-r1)**

Current shipped behavior auto-deduplicates input BEFORE any strict check:
- [`sdk/store.py:470`](../../../src/factgraph/sdk/store.py): `for asrt_id in sorted(set(normalized)):`
- [`sdk/facade.py:268`](../../../src/factgraph/sdk/facade.py): `wanted = set(normalized)`

**Decision (locked at Step 4.4)**: duplicate detection under `strict=True` MUST occur **before** the `set(...)` deduplication step. Reference implementation pattern:

```python
if strict:
    seen: set[str] = set()
    for asrt_id in normalized:
        if asrt_id in seen:
            raise SDKStoreError(
                f"by_ids strict mode: duplicate assertion id {asrt_id!r} in input"
            )
        seen.add(asrt_id)
# existing dedup proceeds afterwards for downstream lookup
```

Both surfaces ([`sdk/store.py:456`](../../../src/factgraph/sdk/store.py) + [`sdk/facade.py:263`](../../../src/factgraph/sdk/facade.py)) must apply this pattern. Missing-id detection follows the existing per-id lookup loop and raises on first `None` return when `strict=True`. Default `strict=False` skips the pre-set check entirely, preserving permissive behavior.

### §5.4 Audit signature semantics (G4 / G5)

`fg.audit.explain(target)`:
- If `target` is `str`: treated as `asrt_id`. Returns `{asrt_id, args, meta, chosen: bool, ...}` (specific shape per §6 invariants).
- If `target` is `AssertionRecord`: extracts the assertion id and reduces to the str case.
- Semantic: explains which active claim wins under current chosen-policy for the (pred, eref) cell containing this assertion id.

`fg.audit.conflicts(target)`:
- If `target` is `AssertionRecord`: extracts (pred_id, e_ref) from the record.
- If `target` is `tuple[Entity, str]`: extracts (pred_id from entity-field, e_ref from entity id).
- Returns `{pred_id, e_ref, active_asrt_ids, chosen_asrt_id}` matching current `_queries.conflicts` shape.

Core query helpers (`_queries.explain_fact`, `_queries.conflicts`) retain existing signatures and names — only the SDK public boundary changes (per §4.2 explicit permission).

#### §5.4.1 asrt_id → (pred_id, e_ref, val_atoms) reverse-resolution (Step 4.3 PF-R1)

`_queries.explain_fact(store, pred_id, e_ref, *val_atoms)` requires `pred_id` and `e_ref` as positional arguments (verified at [`core/store/_queries.py:13`](../../../src/factgraph/core/store/_queries.py) by Step 4.3 preflight PF-R1 + §3.1 spot-check). The G4 surface accepts only `target: str | AssertionRecord` and must reverse-resolve to those positional arguments. Same constraint applies to G5 `conflicts` (but `conflicts` takes only `(pred_id, e_ref)`, no `val_atoms` tail).

**Decision (locked at Step 4.4)**: implementation MUST provide a reverse-resolution mechanism reachable from `_SDKAuditManager.explain` / `.conflicts` bodies. The implementation chooses one of:

- **Option (a) — private helper in `_SDKAuditManager` or `sdk/store.py`**: a helper `_resolve_asrt_to_explain_args(store, asrt_id) → (pred_id, e_ref, val_atoms_tuple)` reads the ledger via `store.ledger.find_claims(...)` or `store.ledger.get_claim(asrt_id)` to extract the claim's (pred_id, e_ref, args). Manager body: `helper(...) → unpack → _queries.explain_fact(self._sdk._store, *args)`.
- **Option (b) — new public function on `_queries`**: e.g., `_queries.explain_assertion(store, asrt_id) → dict[str, Any]` that performs the reverse-resolution + delegation internally. Manager body: `_queries.explain_assertion(self._sdk._store, asrt_id)`.

**Implementation choice (a) vs (b)** is a scoped-detail per CADENCE Step 4.3 (PF-R1 + PF-s1 family). Both satisfy P2-2 (do not call `self._sdk.explain_fact(...)`) and preserve `_queries.explain_fact` core signature (per §4.2 + N7 layer-authority invariant). Choice is recorded in Step 4.7 implementation commit + Step 4.8 closure §10.

`AssertionRecord` → `asrt_id` extraction uses the existing `AssertionRecord.asrt_id` attribute (preflight already verified shipped `AssertionRecord` shape via `sdk/facade.py:263+` re-read). For `conflicts`, the `tuple[Entity, str]` branch uses entity.id and field name to construct `(pred_id, e_ref)` directly without ledger lookup.

### §5.5 Docs sync targets

Per CADENCE Stage 4.8 + Q-NAMING-AD §10:

- `src/factgraph/sdk/docs/README.md` — SDK namespace + FrozenAssertionSet + audit signature changes + persistence renames
- `src/factgraph/core/store/docs/README.md` — core FrozenAssertionSet
- `src/factgraph/application/docs/README.md` — if audit query is documented as application capability (verify in preflight)
- `docs/quickstart` / current SDK examples — verify scope in Step 4.3 preflight
- `docs/README.md` — only if a new persistent docs entry is introduced (none expected)

Historical workflow / archive references preserved per Q-NAMING §4.8.5.

### §5.6 Step 4.6.5 pre-implementation grep inventory

Step 4.6.5 deletion-grep found no major blocker and no need to roll scope back to `draft`. The following current targets are folded into Q-NAMING-AD implementation scope under CADENCE Option 2:

- **Tests**:
  - `tests/test_sdk_frozen_assertion_view.py`
  - `tests/test_sdk_frozen_view_surface.py`
  - `tests/test_sdk_redesign_namespace_shape.py`
  - `tests/test_db_identity_substrate.py`
  - `tests/test_sdk_read_policy.py`
  - `tests/test_factgraph_workspace_lifecycle.py`
  - `tests/test_db_attach_lifecycle.py`
  - `tests/test_schema_mutation_lifecycle.py`
  - `tests/test_schema_field_add_lifecycle.py`
  - `tests/test_a20e_registry_final_removal.py`
- **Current docs and source docstrings**:
  - `src/factgraph/sdk/docs/00_user_guide.en.md`
  - `src/factgraph/sdk/docs/01_concepts.en.md`
  - `src/factgraph/sdk/docs/02_readwrite_and_ingest.en.md`
  - `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
  - `src/factgraph/sdk/docs/04_api_surface.en.md`
  - `src/factgraph/core/store/docs/README.md`
  - `src/factgraph/application/docs/01_overview_en.md`
  - `src/factgraph/authoring/docs/01_overview.md`
  - `src/service/docs/04_rules_registry.md`
  - `src/factgraph/cli.py`
  - `docs/official/kernel/quickstart/database.md`
  - `docs/official/kernel/quickstart/persistence.md`
  - `docs/official/kernel/quickstart/namespace-map.md`
- **Current example**:
  - `examples/05_sdk_assertion_views.ipynb`

Out-of-scope grep hits remain historical / archive / working material (for example `examples/archive/*` and `docs/references/working/*`) and are preserved per Q-NAMING §4.8.5.

## 6. Boundaries And Invariants

- **必须保持的边界**:
  - Q-PR1 sacred 5 paths: `src/factgraph/core/evidence/write_protocol.py`, `src/factgraph/core/store/ledger.py`, `src/factgraph/core/store/_builders.py`, `src/factgraph/adapters/pyreason/`, `src/factgraph/core/derivation/accept.py` — 0-diff vs `4c472b50` after every commit
  - Sacred master `562c74195df43e933bed92a3ff25de94dd8ce666` — never modified
  - Dirty baseline preserved — never `git add` baseline files
  - Layer authority (architecture_principles.md §2.1): SDK boundary changes; core query helpers may stay private
  - Audit semantic: chosen-policy explanation, NOT derivation reasoning (G4 / G5)
  - Workspace file format binary: unchanged
- **明确不做的内容**:
  - N1-N11 above
  - Core query helper `_queries.explain_fact` / `_queries.conflicts` rename
  - Any rename outside §4.2 Batch A + §4.5 Batch D surfaces enumerated in §5.1 / §5.2
  - Persistence schema digest rename (reserved for Q-NAMING-F per §4.7.7)
  - **Flat `SDKStore.explain_fact` and `SDKStore.conflicts` rename or deletion** (per Step 4.2 P2-2): these flat public shells are C-owned deletion debt; Q-NAMING-AD does NOT rename them (would create new `fg.explain` / `fg.conflicts` public surface) and does NOT delete them (pre-implements Q-NAMING-C). They remain untouched until Q-NAMING-C.
  - **`BatchHandle.save` rename** (per Step 4.2 P2-1): `sdk/batch.py:1189` is a batch commit alias forwarding to `self.commit(...)`, not workspace persistence; preserved as-is in AD.
- **兼容性约束**:
  - Hard-cut per §4.8.1 — no aliases, no dual-emit, no deprecation shims
  - Alpha release, no historical user protection burden
  - Old name removed in same commit as new name introduced

## 7. Acceptance

- [ ] G1: `fg.views` removed; `fg.assertion_views` present with same operational semantics
- [ ] G2: `FrozenAssertionView` removed from both core and SDK; `FrozenAssertionSet` present at both layers; `__all__` exports updated
- [ ] G3: `by_ids(strict=True)` on both surfaces ([`sdk/store.py:456`](../../../src/factgraph/sdk/store.py) and [`sdk/facade.py:263`](../../../src/factgraph/sdk/facade.py)) with explicit raise on missing/duplicate ID; default `strict=False` preserves permissive behavior
- [ ] G4: `fg.audit.explain_fact` removed; `fg.audit.explain(target)` accepts `str | AssertionRecord` with semantic preservation
- [ ] G5: `fg.audit.conflicts(pred_id, e_ref)` signature replaced with `fg.audit.conflicts(record | (entity, field))` with semantic preservation
- [ ] G6: `fg.save` removed; `fg.save_workspace` present at [`sdk/store.py:2847`](../../../src/factgraph/sdk/store.py). [`sdk/batch.py:1189`](../../../src/factgraph/sdk/batch.py) `BatchHandle.save` preserved as-is per P2-1 (out of scope: batch commit alias, not workspace persistence)
- [ ] G7: `FactGraph.load` classmethod removed; `FactGraph.load_workspace` present
- [ ] G8: No alias methods, no dual-emit, no deprecation properties anywhere in §5.1 / §5.2 surfaces
- [ ] G9: Workspace file format binary unchanged (verify: load old workspace file with new method succeeds)
- [ ] G10: Module docs updated; current SDK docs / quickstarts / current examples migrated
- [ ] Q-PR1 sacred 5 paths 0-diff vs `4c472b50` confirmed at impl commit HEAD
- [ ] Sacred master `562c74...` unchanged through slice
- [ ] Dirty baseline preserved (no baseline file in `git diff --cached`)
- [ ] All targeted tests pass; full-kernel test suite acknowledged unrelated baseline failures recorded in §10 if any
- [ ] No push without explicit user authorization

## 8. Implementation Plan

1. **Step 4.2 review (Codex)**: review draft, surface 2-4 tightenings per CADENCE Rule 1 + Rule 2 + scope discipline. Cross-check P2-1 / P2-2 corrections in Q-NAMING §4.3.2 are NOT touched (N1).
2. **Step 4.3 preflight (TBD drafter)**: independent branch `v0.2.0-q-naming-ad-preflight-2026-05-31`. Re-read all blueprint-referenced shipped files at preflight-row drafting time per Rule 1. Build 5-bucket severity findings table. **Mandatory preflight findings (corrected per Step 4.2 P3-2)**:
   - 2.a `branch_index → case_index` (field-level rename per Q-NAMING §4.3.4) persistence impact check: Q-NAMING §4.5 requires Codex pre-lock confirmation that the §4.3.4 cascade (deferred to Q-NAMING-B2) does not block Batch D workspace methods. Verify that current workspace persistence does NOT serialize `branch_index` strings into the workspace binary; if it does, B2 stop gate becomes a hard prerequisite to Q-NAMING-AD scope-freeze.
   - 2.b Confirm `sdk/batch.py:1189` `BatchHandle.save` is out-of-scope despite grep hit (per Step 4.2 P2-1).
   - 2.c Confirm `sdk/__init__.py` `FrozenAssertionView` re-export status (per Step 4.2 P3-1 — current grep returns no hit; preflight either locates indirect re-export or confirms SDK does not re-export the class at top level).
   - 2.d Confirm no third `by_ids` public surface beyond `sdk/store.py:456` and `sdk/facade.py:263` (audit §2 blocker 5).
   - 2.e Confirm flat `SDKStore.explain_fact` / `.conflicts` at lines 3470 / 3473 are reachable through `_queries` without going through `_SDKAuditManager` (verifies P2-2 rewire is feasible).
3. **Step 4.4 preflight amendment (on blueprint branch)**: apply Required + Recommended PFs. Update audit log Event Log + Decision Notes.
4. **Step 4.5 self-check (lightweight)**: PF coverage verification, no commit.
5. **Step 4.6 scoped anchor**: `Status: draft` → `Status: scoped` single small commit + audit log event row.
6. **Step 4.6.5 pre-impl grep amendment (completed at scoped)**: pre-impl grep `(fg\.views|FrozenAssertionView|fg\.audit\.(explain_fact|conflicts)|fg\.save|FactGraph\.load|DatabaseFrozenAssertionView)` against `src/`, `tests/`, current docs, and current examples. Minor N-1 targets were folded into §5.1 + §5.6 under CADENCE Option 2 with no status rollback and no implementation started.
7. **Step 4.7 implementation (Codex承接)** on branch `v0.2.0-impl-q-naming-ad-2026-05-31`:
   - 7.1 Rename `FrozenAssertionView` → `FrozenAssertionSet` (core + SDK, in same commit cluster).
   - 7.2 Rename `fg.views` → `fg.assertion_views` (namespace + manager class name).
   - 7.3 Add `strict=True` flag to both by-ids surfaces with explicit raise semantics.
   - 7.4 Change audit public signatures on the `_SDKAuditManager` namespace **only** (`explain_fact` → `explain`; same for `conflicts`). Rewire manager body to reach the core query helper through `_queries.explain_fact` / `_queries.conflicts` directly or via a private helper, NOT through `self._sdk.explain_fact(...)`. **Preserve flat `SDKStore.explain_fact` and `SDKStore.conflicts` at [`sdk/store.py:3470`](../../../src/factgraph/sdk/store.py) / [`:3473`](../../../src/factgraph/sdk/store.py) untouched** per P2-2 (C-owned deletion debt; AD must not rename them to mirror new names nor delete them).
   - 7.5 Rename persistence methods on `SDKStore` and `FactGraph` only (`SDKStore.save` → `save_workspace`, `FactGraph.load` → `load_workspace`). **Preserve `BatchHandle.save` at [`sdk/batch.py:1189`](../../../src/factgraph/sdk/batch.py) untouched** per P2-1 out-of-scope determination.
   - 7.6 Migrate tests (one-pass per file, code + test together).
   - 7.7 Update module docs (`src/factgraph/sdk/docs/`, `src/factgraph/core/store/docs/`, possibly `src/factgraph/application/docs/`).
   - 7.8 Update current SDK docs / quickstarts / current examples in `docs/`.
   - 7.9 Lint pass (`ruff check`).
   - 7.10 Single feat commit (or 3-commit pattern per CADENCE if Step 4.7 review surfaces P1 fix).
8. **Step 4.7 review (Claude)**: independent test re-run, scope grep, cross-check PF / N findings, cross-check prior-slice contract preservation (Q-PR1 sacred + sacred master + dirty baseline).
9. **Step 4.8 closure**: `Status: scoped` → `Status: implemented` + §10 Outcome / Deviations filled + audit log "implemented" event.
10. **Step 4.9 archive**: `git mv` blueprint + audit log pair from `active/` to `archive/` + `INVENTORY.md` entry.

## 9. Docs To Update

- `src/factgraph/sdk/docs/README.md` — fg.assertion_views, FrozenAssertionSet, audit.explain / audit.conflicts new signatures, save_workspace / load_workspace
- `src/factgraph/core/store/docs/README.md` — FrozenAssertionSet (replace FrozenAssertionView)
- `src/factgraph/application/docs/README.md` — if application docs reference audit query (verify in preflight)
- `docs/quickstart/` (or equivalent) — public-facing examples that use any renamed surface
- `docs/official/kernel/` — public quickstart docs (verify scope in preflight)
- `docs/README.md` — only if new persistent docs entry introduced (none expected)
- Historical material under `workflow/heritage/` / `workflow/blueprints/archive/` / `workflow/audit/archive/` — NOT touched per Q-NAMING §4.8.5

## 10. Outcome / Deviations

(To be filled at Step 4.8 closure.)
