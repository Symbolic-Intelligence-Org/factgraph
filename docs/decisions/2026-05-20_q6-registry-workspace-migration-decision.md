# Q6 Decision: Registry-In-Workspace Migration

- Status: proposed for user review
- Created: 2026-05-20
- Branch: `v0.1-q6-registry-workspace-migration-decision-2026-05-20`
- Inputs:
  - `docs/decisions/2026-05-20_q8-savedrule-existence-governance-decision.md`
  - `docs/decisions/2026-05-20_q1-database-class-boundary-decision.md`
  - `docs/decisions/2026-05-20_q3-tx-identity-primitives-decision.md`
  - `docs/decisions/2026-05-20_q4-frozenassertionview-shape-decision.md`
  - `docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md`
  - `docs/references/working/design-points/database-view-fg-layered-architecture.zh.md`
  - `feedback_audit_execution_discipline.md`
- Scope: resolve audit Q6 after Q8=(c): how to migrate shipped `registry/` out of workspace across the SavedRule deprecation window, schema-only transition window, and final A20(E) layout.
- Non-scope: whether SavedRule exists (closed by Q8), compiled-schema object bytes protocol (A16(B) / A20(E) blueprint), full workspace Git-style layout (A17 / I13 blueprint), manifest field-by-field implementation details beyond `components.registry` lifecycle, pushing or deleting existing user data.

## 1. Decision

Q6 chooses **phased registry exit**:

1. **Phase 1 (Q8 deprecation window)**: shipped workspace `registry/` remains a compatibility component. `factgraph_workspace.json` may still carry `components.registry`. SavedRule / SavedInference entry points warn per Q8, but existing workspaces and existing registry-backed callers continue to function.
2. **Phase 2 (post-Q8 rule/inference removal, pre-A20(E))**: rule/inference persistence is gone. Workspace `registry/` may exist only as a **schema-only transition component** containing schema-related entries and schema apply-log events. No rule/inference writes are allowed.
3. **Final state (post-A20(E))**: schema persistence migrates to `db/objects/schema/<schema_digest>.json`; `registry/` is no longer a workspace component; `components.registry` exits the workspace manifest; schema apply-log writers exit or move to whatever schema-migration audit surface replaces them.

Q6 deliberately does NOT choose "hard cutover immediately" because Q8 selected gradual deprecation. Q6 also rejects "registry stays indefinitely" because A20 explicitly removes the registry layout and migrates schema into Database objects.

## 2. Phase Semantics

### 2.1 Phase 1 — compatibility registry

During Q8 Phase 1:

- `registry/` remains a workspace compatibility component.
- `components.registry` may remain in `factgraph_workspace.json`.
- `sync_registry_to_workspace(...)` may continue to copy registry contents into a saved workspace.
- `SDKStore.save(...)` may continue rebinding `_authoring_registry` to the workspace registry after save.
- Rule/inference save/load/list/get surfaces emit the Q8-mandated deprecation warnings.

This is an explicitly transitional state. It is NOT final design compliance. It exists only because Q8 chose gradual deprecation to preserve shipped callers during a grace period.

### 2.2 Phase 2 — schema-only transition registry

After Q8 Phase 2:

- rule/inference registry writers are removed or rejected;
- rule/inference registry readers exist only if Q8's read-only compatibility surface explicitly keeps them for frozen historical inspection;
- `registry/rules/` and `registry/inferences/` are no longer live write locations;
- `registry_manifest.json` may retain a schema entry only;
- `authoring_apply_events.jsonl` may continue only for schema event kinds while schema persistence remains registry-backed;
- `components.registry` may remain only if the schema-only registry physically remains.

The schema-only registry is a temporary bridge to A20(E). It is not a new durable architecture.

### 2.3 Final post-A20(E) state

Once A20(E) lands:

- compiled schema snapshot persists under `db/objects/schema/<schema_digest>.json`;
- the registry schema entry (`registry/schema/schema_ir.json`) is gone;
- schema apply-log writers tied to `FileAuthoringRegistry` are gone or replaced by a non-registry schema migration audit surface;
- `registry/` is absent from the workspace layout;
- `factgraph_workspace.json` does not include `components.registry`;
- `FileAuthoringRegistry` may survive only as a legacy adapter outside workspace loading/saving, not as a workspace component.

This final state aligns with A19 and A20.

## 3. Rejected Alternatives

### 3.1 Hard cutover in the next release

Rejected.

This would remove the workspace registry immediately, forcing existing users of `fg.rules.save/load/list/get`, `fg.inferences.save/load/list/get`, `SDKRegistry` rule/inference surfaces, and registry-backed workspaces to migrate in one step. Q8 explicitly rejected immediate hard removal and chose gradual deprecation.

Q6 must not undermine Q8 by choosing a registry migration that effectively hard-removes the backing storage in Phase 1.

### 3.2 Keep registry forever as an external authoring component

Rejected.

Keeping `registry/` forever, even outside workspace, would preserve the SavedRule governance model that Q8 removed from the v1 design. Q8's final state is rules/inferences as user Python code plus in-memory `RuleRegistry`, not SDK-owned file persistence.

An explicit `registry_root=` may remain as a Phase 1 compatibility escape hatch and as an implementation detail for migration tools, but it is not the final v1 architecture for rules/inferences.

### 3.3 Treat schema persistence as Q8 removal scope

Rejected.

Q8 explicitly scoped `FileAuthoringRegistry.upsert_schema_ir(...)` out. Schema persistence is migrated, not removed. Q6 therefore cannot delete `registry/schema/schema_ir.json` unless A20(E)'s replacement path is ready.

## 4. Supporting Evidence

### 4.1 Design references

- §18 A15 line 734: rules are code artifacts;v1 rules do not enter workspace or Database transaction.
- §18 A16 line 735: compiled schema snapshot belongs under Database as `db/objects/schema/<schema_digest>.json`.
- §18 A19 line 738: final manifest shrinks to `{workspace_version, components.{db, views}, created_at, last_saved_at}` and does not carry duplicate top-level `db_id / schema_digest / data_digest`.
- §18 A20 line 739: current `registry/rules/`, `registry/inferences/`, `registry/registry_manifest.json`, and `registry/authoring_apply_events.jsonl` are removed;`registry/schema/schema_ir.json` migrates to `db/objects/schema/<schema_digest>.json`;rules stay in user Python code.

### 4.2 Q8 references

Q8 selected gradual deprecation:

- Phase 1: rule/inference persistence surfaces warn but continue.
- Phase 2: rule/inference persistence exits.
- Schema persistence is out of Q8 scope and migrates later via A20(E).
- `registry_manifest.json` is partial: rules/inferences sections exit at Phase 2, schema entry may persist until A20(E).
- `authoring_apply_events.jsonl` is event-kind scoped: rule/inference events stop after Phase 2;schema events may continue until A20(E).
- Q6 remains relevant during Phase 1 and the post-Phase-2 schema-only window.

### 4.3 Shipped workspace / registry coupling

Shipped workspace runtime currently treats `registry/` as a workspace component:

- `WORKSPACE_REGISTRY = "registry/"` at `src/factgraph/application/workspace_runtime.py:19`.
- `WorkspacePaths` includes `registry` at `workspace_runtime.py:26-32`.
- `workspace_manifest_payload(...)` writes `components.registry` at `workspace_runtime.py:59-62`.
- `validate_workspace_manifest(...)` requires `components.registry == "registry/"` at `workspace_runtime.py:102-108`.
- `save_workspace(...)` calls `sync_registry_to_workspace(...)` and writes a `FileAuthoringRegistry(paths.registry)` at `workspace_runtime.py:160-177`.
- `load_workspace(...)` requires the registry path to exist at `workspace_runtime.py:180-187`.

### 4.4 Shipped FileAuthoringRegistry schema/apply-log surface

`FileAuthoringRegistry` currently combines schema, rule, inference, manifest, and apply-log responsibilities:

- `upsert_schema_ir(...)` writes fixed path `schema/schema_ir.json` and manifest schema entry at `src/factgraph/authoring/registry_fs.py:47-67`.
- `registry_manifest.json` path is `registry_fs.py:40-41`.
- `authoring_apply_events.jsonl` path is `registry_fs.py:43-45`.
- apply-log writer is `append_apply_event(...)` at `registry_fs.py:210-216`.
- apply-log readers are `find_apply_execute_run(...)` and `list_apply_execute_runs(...)` at `registry_fs.py:218-267`.
- `_load_manifest(...)` defaults to `schema: None`, `rules: []`, `inferences: []` at `registry_fs.py:410-428`.

### 4.5 Shipped SDK coupling

Shipped SDK constructor/save logic ties workspace path to registry path:

- `_resolve_workspace_constructor_paths(...)` derives `expected_registry = workspace_paths.registry` and uses it when `path=` is supplied without `registry_root=` at `src/factgraph/sdk/store.py:667-695`.
- `SDKStore.save(...)` persists the workspace and then rebinds `_authoring_registry = FileAuthoringRegistry(paths.registry)` at `sdk/store.py:2063-2090`.
- schema digest preflight / update consults `_authoring_registry` at `sdk/store.py:2588-2624`.

These are exactly the couplings Q6 must unwind over time.

## 5. Consequences

### 5.1 A15 / I12(E)

Q6 resolves the migration mechanics for the design strictness established by A15: rules do not belong in workspace.

Phase 1 is a deliberate compatibility exception inherited from Q8. Phase 2 removes rule/inference workspace writes. Final state removes the registry component entirely after schema migration.

### 5.2 A19 manifest

`components.registry` cannot disappear while live workspace schema persistence still depends on `registry/schema/schema_ir.json`.

Q6 therefore gates A19 in two steps:

1. during Phase 1 and schema-only transition, manifests may still carry `components.registry`;
2. after A20(E), `components.registry` exits and A19's `{components.{db, views}}` shape becomes reachable.

### 5.3 A20 split

Q6 reinforces the A20 split:

- A20(A-D,F): rules / inferences / registry manifest rule+inference entries / rule+inference apply-log event kinds / "rules stay in Python" follow Q8 + Q6 Phase 1/2.
- A20(E): schema path migration follows A16(B) + A17 + I13 and remains necessary even after Q8 Phase 2.

### 5.4 Q1 / Q2 / Q3 / Q4 / Q5 / Q7 unaffected

Q6 governs workspace registry migration. It does not reopen Database boundary (Q1), attach lifecycle (Q2), identity primitives (Q3), view shape (Q4), view visibility (Q5), or assertion record shape (Q7).

### 5.5 Q8 upstream contingency closed

Q8 is the upstream contingency that must close before Q6. Q6 implements Q8's migration mechanics without reopening Q8's SavedRule governance decision.

### 5.6 Implementation ordering

Q6 creates an ordering constraint, not an implementation plan:

1. Q8 Phase 1 warnings may land while registry remains a workspace component.
2. Q8 Phase 2 rule/inference removal is a prerequisite for entering the schema-only transition window.
3. A20(E) schema migration must land before registry can fully exit workspace and before `components.registry` can disappear.

## 6. Acceptance Criteria For This Decision

Future Q6-dependent blueprints must obey:

1. Do keep Q8 Phase 1 compatible: do not remove workspace registry storage before Q8's deprecation window closes.
2. Do emit/retain Q8 deprecation warnings for every rule/inference persistence entry point during Phase 1.
3. Do forbid new rule/inference registry writes after Q8 Phase 2.
4. Do allow a schema-only registry transition after Q8 Phase 2 only until A20(E) migrates schema to `db/objects/schema/<schema_digest>.json`.
5. Do NOT remove `registry/schema/schema_ir.json` until the `db/objects/schema/<schema_digest>.json` replacement exists.
6. Do NOT keep `components.registry` in the final A19 manifest after A20(E).
7. Do NOT treat `registry_root=` as the final v1 architecture for rule/inference persistence. It is a compatibility / migration tool only.
8. Do keep `FileAuthoringRegistry` class survival scoped to schema transition / legacy tooling;do not use it to reintroduce SavedRule persistence after Q8 Phase 2.
9. Do event-kind-scope `authoring_apply_events.jsonl`: rule/inference events stop after Q8 Phase 2;schema events may continue only until A20(E) or a replacement audit surface lands.
10. Do preserve existing user data during migration;removal of live write surfaces is not permission to silently delete historical registry files without an explicit migration / archive path.

## 7. Decision Record

Q6 resolution: **phased registry exit**.

During Q8 Phase 1, `registry/` remains a workspace compatibility component and `components.registry` may remain in the manifest. After Q8 Phase 2, the live registry may contain only schema-transition material and schema apply-log events. After A20(E), schema moves to `db/objects/schema/<schema_digest>.json`, registry exits the workspace layout, and `components.registry` disappears from the manifest.

Q6 does not reopen Q8. SavedRule persistence is already set to gradual deprecation and final removal. Q6 defines the workspace migration mechanics needed to make that governance outcome coherent with A16/A19/A20.
