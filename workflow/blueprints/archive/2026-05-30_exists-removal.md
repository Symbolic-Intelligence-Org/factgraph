# Slice 5 — Narrow `:exists` Co-Emission Removal

- Status: implemented
- Created: 2026-05-30
- Last Updated: 2026-05-30(implemented after Step 8 final gate + §10 Outcome)
- Slice: Step 2+ cleanup after Identity-as-Claim / API namespace / docs polish
- Class: S-M(runtime cleanup with tests/docs; Q-PR1 no-touch)
- Related Modules:
  - `src/factgraph/application/entity_write.py`
  - `src/factgraph/application/retract_guard.py`
  - `src/factgraph/application/schema_runtime.py`
  - `src/factgraph/sdk/store.py`
  - `src/factgraph/sdk/batch.py`
  - `src/factgraph/sdk/docs/`
  - `tests/`
- Related Docs:
  - Stage 1 audit: `workflow/audit/active/2026-05-30_exists-removal-vs-shipped.md` @ `bd3ab5c3`
  - Adopted Q-decision: `workflow/design/decisions/active/2026-05-30_q-exists-removal-decision.md` @ `870e1f1f`
  - ADR-IC baseline: `workflow/design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md`
  - Slice 2 archive: `workflow/blueprints/archive/2026-05-29_slice-2-identity-as-claim-emission.md`
  - Slice 3a archive: `workflow/blueprints/archive/2026-05-30_slice-3a-api-namespace.md`
  - Slice 4 archive: `workflow/blueprints/archive/2026-05-30_slice-4-docs-polish.md`
- Audit Log:
  - [2026-05-30_exists-removal.audit.md](./2026-05-30_exists-removal.audit.md)
- Branch: `v0.2.0-blueprint-exists-removal-2026-05-30`
- Fork point: `870e1f1f` (Q-EXISTS adopted decision head)

## 1. Problem

Slice 2 shipped Identity-as-Claim emission with a transitional `<EntityType>:exists` Claim:

- `fg.entities.create(...)` and legacy lazy materialization emit N Identity Claims plus one `:exists` Claim.
- `fg.entities.exists(...)` reads active `:exists` Claims.
- `fg.entities.delete(...)` revokes Identity, `:exists`, and Field Claims.
- `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` protects direct `:exists` retract.

ADR-IC §4.4.4 intentionally marked `:exists` co-emission as transitional. Stage 1 audit `bd3ab5c3` showed that a repo-wide `:exists` deletion is too broad because `:exists` also appears in rule DSL, schema indexing, Q-PR1 derivation accept, and legacy data.

The adopted Q-EXISTS decision `870e1f1f` narrows the next slice: remove **user-facing co-emission** and replace **user-facing existence checks** with Identity Claim bundle visibility, while preserving legacy/Q-PR1/rule surfaces.

## 2. Goals

- G1 Stop user-facing materialization paths from emitting new `<EntityType>:exists` Claims.
- G2 Rewrite `fg.entities.exists(EntityCls, **identity)` to use complete active Identity Claim bundle semantics.
- G3 Make `fg.entities.delete(...)` tolerate entities with no active `:exists` Claim and update return-count expectations.
- G4 Preserve direct-retract protection for legacy `:exists` Claims using the existing `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` code.
- G5 Keep `exists_pred_ids` populated for legacy guard classification and schema compatibility.
- G6 Keep rule DSL `Entity:exists` virtual syntax and Q-PR1 derivation accept out of scope.
- G7 Migrate tests from user-path "N Identity + 1 `:exists`" expectations to "N Identity" expectations.
- G8 Update current docs/ADR text at close to describe retired user-path co-emission and legacy/virtual carry-forward.
- G9 Preserve Q-PR1 sacred paths, sacred branches, and dirty baseline.

## 3. Non-goals

- N1 Remove `Entity:exists` rule DSL syntax.
- N2 Remove generated `:exists` predicate declarations from schema IR.
- N3 Empty/delete `exists_pred_ids`.
- N4 Rename `EXISTENCE_CLAIM_TRANSITIONAL_GUARD`.
- N5 Rewrite Q-PR1 sacred `src/factgraph/core/derivation/accept.py`.
- N6 Remove shadow store or `_identity_values_by_e_ref`.
- N7 Migrate, revoke, or rewrite legacy persisted `:exists` Claims.
- N8 Change SQLite ledger schema or run destructive data migrations.
- N9 Push, PR creation, or master merge.
- N10 Memory consolidation.
- N11 Remove `PlannedOpDTO(op="record_exists")`, `WireRecordExistsOp`, or wire parsing capability; those may remain as legacy/protocol compatibility surfaces unless a later decision supersedes this scope.

## 4. Current Context

### 4.1 Adopted Decision Constraints

This blueprint treats Q-EXISTS §4.1-§4.10 as binding:

| Q-EXISTS section | Binding constraint for this blueprint |
|---|---|
| §4.1 | Next slice is user-facing co-emission + legacy guard-compat cleanup, not full repo-wide `:exists` deletion. |
| §4.2 | Rule DSL `Entity:exists` remains virtual syntax. |
| §4.3 | `fg.entities.exists(...)` uses complete active Identity Claim bundle visibility. |
| §4.4 | Delete/count semantics update from "N Identity + 1 `:exists` + Field" to "N Identity + Field" for user-facing paths. |
| §4.5 | Legacy `:exists` Claims are read-only legacy data and remain protected. |
| §4.6 | `exists_pred_ids` option (1) is locked: keep for legacy guard classification and schema compatibility. |
| §4.7 | Shadow store removal is not combined with this slice. |
| §4.8 | Q-PR1 derivation accept stays out of scope; user-vs-derived split is explicit carry-forward. |
| §4.9 | ADR-IC/current docs update happens at implementation close. |
| §4.10 | Three taxonomy sources must be kept distinct: legacy user-path Claims, derivation-path Claims, rule DSL virtual references. |

### 4.2 Shipped Code Surface

| Surface | Current state | Evidence |
|---|---|---|
| User create emission | `_apply_op(record_exists)` writes `info.exists_predicate_id`. | `src/factgraph/application/entity_write.py:698-708` |
| Entity visibility | `_entity_visible(...)` checks `:exists` first, then field facts. | `src/factgraph/application/entity_write.py:860-875` |
| `fg.entities.exists` | SDK scans active `info.exists_predicate_id` claims. | `src/factgraph/sdk/store.py:1234-1253` |
| Entity delete | SDK documents whole-entity revoke as Identity + `:exists` + Field. | `src/factgraph/sdk/store.py:1117-1232` |
| Guard | `check_retract_allowed(...)` classifies `exists_pred_ids` and raises `EXISTENCE_CLAIM_TRANSITIONAL_GUARD`. | `src/factgraph/application/retract_guard.py:75-140` |
| Schema index | `SchemaIndex.exists_pred_ids` is populated independently from `identity_pred_ids`. | `src/factgraph/application/schema_runtime.py:40-74`, `:206-250` |
| SDK batch user-facing emission | Batch staging appends `RecordExistsOp`; wire apply directly writes `:exists` via `set_field`. | `src/factgraph/sdk/batch.py:1413-1424`; `:1458-1462`; `:1560-1604`; `:453-470` |
| Rule DSL | SDK DSL emits `Entity:exists`; protocol/rule planner special-cases it. | `src/factgraph/sdk/dsl/expr.py:397-400`, `:521-548`; `src/factgraph/application/protocol/rule.py:519-535`; `src/factgraph/core/rules/where_eval.py:1024-1030` |
| Q-PR1 | Derivation accept writes `exists_pred_id` and is sacred out of scope. | `src/factgraph/core/derivation/accept.py:667-725`, `:1006-1015` |

### 4.3 Dirty Baseline

Known dirty baseline must remain untouched:

- `docs/references/working/design-points/readme.md`
- `examples/01_sdk_check_diagnose.ipynb`
- `examples/02_overlay_why_not_frontier.ipynb`
- `examples/archive/01_sdk_basics.ipynb`
- deleted `workflow/working/.gitkeep`
- untracked `docs/references/working/change-requests-2026-05-27/`
- untracked `rainbird-ai sdk code/`

## 5. Proposed Shape

### 5.1 User-Path Emission

Remove new user-facing `record_exists` emission from materialization paths that do not require Q-PR1 scope expansion.

The implementation should not delete schema `:exists` predicate declarations and should not delete `record_exists` handling until the codebase proves no legacy or non-user path still needs that DTO shape. If `record_exists` remains for compatibility, the user-facing planners should stop producing it.

### 5.1.1 SDK Batch User-Path Migration

`fg.batch().commit()` is a user-facing emission path. Stop new `RecordExistsOp` emission from batch user planners, mirroring the §5.1 user-path stop.

Wire/protocol compatibility (`WireRecordExistsOp`, `_validate_wire_record_exists_binding`, `PlannedOpDTO(op="record_exists")`) may remain as legacy parsing surface so existing wire clients are not broken by this slice.

### 5.2 Identity-Bundle Visibility

`fg.entities.exists(EntityCls, **identity)` should:

1. Validate the Entity class and complete Form I identity bundle using existing `_ref` / schema helpers.
2. Compute deterministic e_ref.
3. Resolve all Identity predicates for the entity type.
4. For each Identity field, find an active Identity Claim where `(e_ref, pred_id, value)` matches `(computed e_ref, identity_pred_id_for_field, user-supplied identity value from identity kwargs)`.
5. Return true only when the complete bundle is active.

Composite identity entities require all Identity Claims. "Any identity claim active" is explicitly rejected.

### 5.3 Delete Semantics

`fg.entities.delete(...)` should:

- remain the only legal whole-entity lifecycle deletion path for Identity Claims;
- retract active Identity and Field Claims for the entity;
- tolerate no active `:exists` Claim;
- preserve legacy direct-retract guard behavior for any legacy `:exists` Claim that remains active;
- update return counts and tests accordingly.

### 5.4 Legacy Guard Compatibility

Keep the guard code name `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` unchanged. The slice may narrow when it is reachable, but must not rename it.

`exists_pred_ids` remains populated and continues to classify:

- legacy user-path `:exists` Claims from old ledgers;
- derivation-path `:exists` Claims from Q-PR1 sacred accept.

### 5.5 Rule / Q-PR1 Carry-Forward

This slice records but does not resolve:

- rule DSL virtual `Entity:exists` syntax;
- rule protocol port inference based on `:exists`;
- rule planner ordering of `:exists`;
- Q-PR1 derivation accept `exists_pred_id` writes.

Any implementation step that needs those surfaces must stop and trigger blueprint amendment / user authorization.

## 6. Boundaries And Invariants

### 6.1 Scope Freeze

| SF | Lock | Source |
|---|---|---|
| SF1 | Q-EXISTS §4.1-§4.10 are binding constraints for this blueprint. | Q-decision `870e1f1f` |
| SF2 | Q-PR1 sacred paths remain 0 diff; `core/derivation/accept.py` is not edited. | Q-EXISTS §4.8 |
| SF3 | Shadow store is not removed and `_identity_values_by_e_ref` behavior is preserved unless only read/compat checks are needed. | Q-EXISTS §4.7 |
| SF4 | Rule DSL / protocol / where-planner `Entity:exists` virtual syntax remains in scope only for read/verification, not deletion. | Q-EXISTS §4.2 |
| SF5 | Legacy `:exists` Claims are preserved and protected; no ledger migration, bulk revoke, or rewrite. | Q-EXISTS §4.5 |
| SF6 | `fg.entities.exists(...)` uses complete Identity Claim bundle semantics, not any-identity semantics. | Q-EXISTS §4.3 |
| SF7 | `exists_pred_ids` remains populated for legacy guard classification and schema compatibility. | Q-EXISTS §4.6 option (1), per §4.10 taxonomy reasoning |
| SF8 | `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` name remains unchanged. | Q-EXISTS §4.5 |
| SF9 | No destructive ledger migration or SQLite schema migration. | Q-EXISTS §3 / §4.5 |
| SF10 | Dirty baseline, sacred branches, and Q-PR1 carve-out remain preserved throughout. | Slice 1/2/3a/4 inheritance |

### 6.2 Per-Commit Ritual

Each implementation commit must verify:

- current branch is the implementation branch for this blueprint;
- sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`;
- Q-PR1 sacred paths are 0 diff;
- dirty baseline is unchanged;
- `git diff --check` is clean;
- no push unless the user explicitly authorizes it.

## 7. Acceptance

### 7.1 Runtime Behavior

- [x] User-facing create/materialization paths no longer emit new `:exists` Claims.
- [x] `fg.entities.exists(...)` returns true for complete active Identity Claim bundle.
- [x] `fg.entities.exists(...)` returns false for incomplete/no active Identity Claim bundle.
- [x] Composite Identity entities require all Identity Claims to be active.
- [x] `fg.entities.delete(...)` succeeds and returns correct counts when no active `:exists` Claim exists.
- [x] Legacy `:exists` direct retract still raises `EXISTENCE_CLAIM_TRANSITIONAL_GUARD`.
- [x] `exists_pred_ids` remains populated.
- [x] Rule DSL / Q-PR1 surfaces remain behaviorally unchanged.

### 7.2 Tests

- [x] Complete test inventory identifies all user-path count expectations before implementation.
- [x] `tests/test_emission_contract.py` is migrated away from user-path `+1 :exists` expectations.
- [x] `tests/test_sdk_entities_create.py` is migrated to no user-path `:exists` emission.
- [x] `tests/test_sdk_entities_delete.py` is migrated to no active `:exists` requirement/count for user path.
- [x] `tests/test_sdk_entities_exists.py` covers complete-bundle semantics and composite identities.
- [x] SDK batch tests verify batch user paths no longer emit new `:exists` Claims; wire legacy compatibility tests pass.
- [x] Retract-guard tests preserve legacy `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` coverage through explicit legacy fixtures.
- [x] Schema cache tests preserve `exists_pred_ids` where required.

### 7.3 Docs / Decisions

- [x] ADR-IC §4.4 or equivalent active decision text is updated at close to reflect retired user-path co-emission.
- [x] Current SDK docs no longer describe user-path `:exists` co-emission as current truth.
- [x] Docs distinguish legacy Claims, derivation-path Claims, and rule DSL virtual references.
- [x] Shadow store and Q-PR1 carry-forward remain documented.

### 7.4 Final Checks

- [x] `python -m compileall -q src` clean.
- [x] Target runtime tests green.
- [x] Q-PR1 sacred paths 0 diff.
- [x] Dirty baseline preserved.
- [x] Sacred branches preserved.
- [x] `git diff --check` clean.

## 8. Implementation Plan

### Step 0 — Pre-Implementation Inventory

- Re-run Stage 1 grep inventory against implementation branch head.
- Build complete affected-test inventory for `:exists`, `EXISTENCE_CLAIM_TRANSITIONAL_GUARD`, `exists_pred_ids`, `record_exists`, and `fg.entities.exists`.
- Inventory entity visibility helpers (`entity_write._entity_visible`, `entity_view._entity_visible/_enumerate_entity_refs`, SDK facade visibility helpers, and `sdk/batch.py:_handle_requires_record_exists_op`).
- Confirm no new surfaces require Q-PR1 edits, rule DSL deletion, shadow-store removal, or ledger migration.
- If a blocker appears, pause for blueprint amendment.

**Output**: append affected-test inventory rows to the paired audit log Decision Notes (for example, "Step 0 inventory found N affected test files: ..."), or fold inventory results into the Step 1 implementation commit's audit row if the inventory is trivial. Step 0 modifies no runtime or test files.

### Step 1 — Identity-Bundle Existence Helper

- Add a shared helper for complete active Identity Claim bundle visibility.
- Cover single and composite identity cases.
- Keep it application/SDK-layer friendly without touching ledger schema or Q-PR1 paths.

### Step 2 — Rewrite `fg.entities.exists(...)`

- Replace direct active `:exists` scan with the helper from Step 1.
- Preserve Entity class / identity-bundle validation behavior.
- Add tests for true/false, incomplete identity, composite identity, and post-delete behavior.

### Step 3 — Stop User-Path `:exists` Co-Emission

- Stop user-facing create/lazy materialization planners from producing `record_exists` where permitted by scope.
- Stop `src/factgraph/sdk/batch.py` user-path staging from emitting `RecordExistsOp`; preserve `WireRecordExistsOp` parsing and wire compatibility per PF-REC2.
- Preserve schema `:exists` predicate declaration and `exists_pred_ids`.
- Do not edit Q-PR1 derivation accept.
- Update create/emission tests.

### Step 4 — Delete Semantics And Counts

- Ensure `fg.entities.delete(...)` handles entities with no active `:exists` Claim.
- Update count assertions from N Identity + 1 `:exists` + Field to N Identity + Field.
- Preserve direct legacy `:exists` guard coverage.

### Step 5 — Legacy Guard Fixtures

- Create explicit legacy `:exists` fixtures in tests without relying on new user-path emission.
- Verify direct retract still raises `EXISTENCE_CLAIM_TRANSITIONAL_GUARD`.
- Verify `exists_pred_ids` remains populated and independent from `identity_pred_ids`.

### Step 6 — Runtime Regression Sweep

- Run migrated emission/create/delete/exists/retract-guard/schema-cache tests.
- Run any rule/query tests that mention `Entity:exists` to confirm virtual syntax remains unchanged.
- Run Slice 2/3a target suites as needed.

### Step 7 — Current Docs / ADR Close Updates

- Update current SDK docs and ADR-IC/current decision text to reflect:
  - user-path co-emission retired;
  - legacy `:exists` Claims protected;
  - rule DSL virtual syntax retained;
  - Q-PR1 derivation accept and shadow store carry-forward.
- Do not rewrite historical/archive docs except explicit current-status rows.

### Step 8 — Final Gate + Outcome

- Run final tests and checks.
- Fill §10 Outcome / Deviations.
- Flip blueprint status to `implemented`.
- Prepare archive cadence after reviewer pass.

## 9. Docs To Update

Candidate close-time docs:

- `workflow/design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md`
- `workflow/design/decisions/active/2026-05-30_q-exists-removal-decision.md` if a Decision Record implementation row is needed
- `src/factgraph/sdk/docs/02_readwrite_and_ingest.en.md`
- `src/factgraph/sdk/docs/04_api_surface.en.md`
- `docs/official/kernel/quickstart/read-write.md`
- `docs/official/kernel/quickstart/schema.md`
- `workflow/audit/active/2026-05-30_exists-removal-vs-shipped.md` (optional close-time event/disposition row if useful)
- Any current docs surfaced by Step 0 grep

## 10. Outcome / Deviations

### 10.1 Final Landing Result

Slice 5 landed as a narrow runtime cleanup from scoped anchor `3d158dac` through implementation head `dab38a97`, then this implemented close commit.

| Step | Commit | Result |
|---|---|---|
| Step 0 | `2e8c5cd7` | Pre-implementation inventory recorded runtime/test surfaces and batch `RecordExistsOp` double-duty caveat. |
| Step 1 | `bc161151` | Added application-layer complete Identity-bundle visibility helper and helper tests. |
| Step 2 | `7fdb5b09` | Rewired `fg.entities.exists(...)` from `:exists` scan to complete Identity Claim bundle visibility. |
| Step 3 | `6061f908` | Stopped user-facing `:exists` co-emission in application materialization and SDK batch user paths while preserving wire/protocol compatibility. |
| Step 4 | `c6ad146a` | Aligned delete semantics/counts to Identity + Field, with legacy `:exists` path-bound delete coverage. |
| Step 5 | `41600d3c` | Formalized explicit legacy `:exists` retract-guard fixtures across SDK / entity_write / ingest surfaces. |
| Step 6 | `656eb011` | Ran regression sweep and fixed one remaining assertion-namespace legacy-fixture assumption. |
| Step 7 | `dab38a97` | Updated current SDK docs, ADR-IC, Q-EXISTS decision record, and audit log. |
| Step 8 | this close commit | Final gate passed; status flips to `implemented`; §10 Outcome filled. |

Implementation delta from scoped anchor before this close commit: 22 files, +610 / -312. Acceptance status: §7.1 runtime 8/8, §7.2 tests 8/8, §7.3 docs/decisions 4/4, §7.4 final checks 6/6.

### 10.2 Deviations And Amendments

- Step 4.3 preflight found `src/factgraph/sdk/batch.py` as a missing user-facing emission surface. The blueprint was amended before scope freeze; implementation preserved `WireRecordExistsOp`, `_validate_wire_record_exists_binding`, and `PlannedOpDTO(op="record_exists")` compatibility per N11.
- Step 3 discovered and handled `RecordExistsOp` double-duty in batch: user-path `:exists` emission stopped, while batch new-entity Identity-bundle creation continued through a non-wire `create_if_missing` signal.
- Step 3 also performed a small in-scope internal namespace cleanup in `sdk/batch.py` (`sdk.set/add/retract` to `sdk.fields.*` / `sdk.assertions.retract`) while editing the same in-scope file.
- Step 6 regression sweep found one remaining user-path emission assumption in `tests/test_sdk_assertions_namespace.py`; it was converted to an explicit legacy `:exists` fixture.
- Step 6 also detected unrelated Form I legacy debt in `tests/test_application_rule_disable_runtime_native.py` (`Identity(primary_key=True)`). It was intentionally left out of scope per SF1/Q-EXISTS narrow-slice lock.

### 10.3 Scope Freeze Verification

| SF | Close verification |
|---|---|
| SF1 | Q-EXISTS §4.1-§4.10 represented in implementation and docs close. |
| SF2 | Q-PR1 sacred paths remain 0 diff; `core/derivation/accept.py` untouched. |
| SF3 | Shadow store remains present; `_identity_values_by_e_ref` compatibility preserved. |
| SF4 | Rule DSL / protocol / where-planner `Entity:exists` syntax not deleted; 26 rule/query unittest cases passed. |
| SF5 | Legacy `:exists` Claims are preserved/protected; no migration, bulk revoke, or rewrite. |
| SF6 | `fg.entities.exists(...)` uses complete Identity Claim bundle semantics. |
| SF7 | `exists_pred_ids` remains populated for legacy guard/schema compatibility. |
| SF8 | `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` name unchanged. |
| SF9 | No ledger schema or SQLite migration performed. |
| SF10 | Dirty baseline, sacred branches, and Q-PR1 carve-out preserved. |

### 10.4 Runtime Behavior Verification

Final target regression sweep passed 167 direct test invocations across the Step 0 inventory target files plus the Step 1 helper tests. Rule/query `Entity:exists` virtual-syntax smoke passed 26 unittest cases.

Runtime behavior verified:

- user-facing `fg.entities.create`, lazy field materialization, and SDK batch user paths no longer emit new `:exists` Claims;
- `fg.entities.exists(...)` returns from complete active Identity Claim bundle visibility and ignores `:exists`-only legacy rows for user-facing truth;
- composite Identity entities require every Identity Claim to be active;
- `fg.entities.delete(...)` succeeds without active `:exists` and still path-bound revokes legacy `:exists` when present;
- direct legacy `:exists` retract remains guarded by `EXISTENCE_CLAIM_TRANSITIONAL_GUARD`;
- `exists_pred_ids` remains populated and independent from `identity_pred_ids`;
- rule virtual syntax and Q-PR1 surfaces remain behaviorally out of scope.

### 10.5 Test Migration Result

Migrated/verified target tests:

- `tests/test_application_entity_visibility.py`
- `tests/test_application_entity_write.py`
- `tests/test_emission_contract.py`
- `tests/test_sdk_entities_create.py`
- `tests/test_sdk_entities_delete.py`
- `tests/test_sdk_entities_exists.py`
- `tests/test_sdk_batch_application_delegate.py`
- `tests/test_sdk_batch_primary_identity.py`
- `tests/test_application_retract_guard.py`
- `tests/test_application_entity_write_retract_guard.py`
- `tests/test_application_ingest_retract_guard.py`
- `tests/test_sdk_retract_guard_integration.py`
- `tests/test_application_schema_runtime_cache.py`
- `tests/test_sdk_schema_three_split.py`
- `tests/test_sdk_assertions_namespace.py`

`pytest` remains unsuitable in this local environment due the known capture/readline segfault path, so Step 6/8 used direct Python and `unittest` smoke runners.

### 10.6 Docs Landed

Step 7 updated current docs/decisions:

- `src/factgraph/sdk/docs/02_readwrite_and_ingest.en.md`
- `src/factgraph/sdk/docs/04_api_surface.en.md`
- `workflow/design/decisions/active/2026-05-29_q-ic-identity-as-claim-decision.md`
- `workflow/design/decisions/active/2026-05-30_q-exists-removal-decision.md`
- `workflow/blueprints/active/2026-05-30_exists-removal.audit.md`

`docs/official/kernel/quickstart/read-write.md` had no `:exists` hits after Slice 4. `docs/official/kernel/quickstart/schema.md` only references generated `<EntityType>:exists` in schema-mutation rejection context, so it did not need Slice 5 edits.

### 10.7 Q-PR1 / Sacred / Dirty Preservation

Verified at close:

- Q-PR1 sacred paths diff from `4cc577dc..HEAD`: 0 lines.
- Local `master`: `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline preserved: 4 modified files, 1 deleted file, 2 untracked paths; no dirty baseline files staged or committed by Slice 5.
- No push, PR creation, or master merge performed.

### 10.8 Carry-Forward Dependencies

- Q-PR1 derivation accept `:exists` emission remains untouched and needs explicit future authorization if changed.
- Rule DSL `Entity:exists` remains virtual/internal syntax; lowering it through Identity Claims or active field evidence is a future rule/query slice.
- Shadow-store removal remains a separate cleanup; Slice 5 intentionally preserves `_identity_values_by_e_ref`.
- Legacy `:exists` data migration policy remains future work; this slice preserves/protects existing rows.
- Form I legacy debt in `tests/test_application_rule_disable_runtime_native.py` remains an unrelated cleanup candidate.
- Wire/protocol `record_exists` compatibility remains until a later decision supersedes N11.

### 10.9 Archive Cadence

After reviewer implemented-anchor pass:

1. Move `workflow/blueprints/active/2026-05-30_exists-removal.md` to `workflow/blueprints/archive/`.
2. Move `workflow/blueprints/active/2026-05-30_exists-removal.audit.md` to `workflow/blueprints/archive/`.
3. Update `workflow/blueprints/archive/INVENTORY.md` with Slice 5 summary.
4. Add an `archived` event row in the audit log.
5. Commit archive cadence separately and keep push gated on explicit user authorization.
