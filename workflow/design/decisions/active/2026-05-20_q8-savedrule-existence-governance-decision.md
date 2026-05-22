# Q8 Decision: SavedRule Persistence Governance

- Status: closed
- Created: 2026-05-20
- Branch: `v0.1-q8-savedrule-governance-decision-2026-05-20`
- Inputs:
  - `docs/decisions/2026-05-20_q1-database-class-boundary-decision.md`
  - `docs/decisions/2026-05-20_q3-tx-identity-primitives-decision.md`
  - `docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md`
  - `docs/references/working/design-points/database-view-fg-layered-architecture.zh.md`
  - `feedback_audit_execution_discipline.md`
- Scope: decide whether shipped `FileAuthoringRegistry` / `SavedRule` persistence layer should exist at all in v1; if not, on what migration mechanics path.
- Non-scope: Q1 (Database boundary, closed), Q3 (transaction identity primitives, closed), Q2 (attach lifecycle), Q4 (FrozenAssertionView shape), Q5 (view ↔ is_active composition), Q7 (AssertionRecord shape reconciliation). Q6 (registry-in-workspace migration mechanics) is contingent on Q8 — handled in §6 below.

## 1. Decision

Q8 chooses **gradual deprecation** — option (c) from audit §8 Q8.

The shipped SavedRule / `FileAuthoringRegistry` rule+inference persistence layer is removed from the v1 design surface, but not in a single breaking release. Two phases:

- **Phase 1 (this release window)**: emit `DeprecationWarning` from **all public + semipublic SavedRule / SavedInference entry points listed in §3.2** — including (i) public SDK facade `fg.rules.*` / `fg.inferences.*` (§3.2.1), (ii) `SDKRegistry` rule/inference register + read + list methods (§3.2.2), and (iii) `SDKRegistry.apply_authoring_bundle(rule_request=..., derivation_request=...)` when the rule/inference branches are non-None (§3.2.3). The schema-only invocations (`SDKRegistry.apply_schema_classes` / `apply_authoring_bundle(authoring_schema=...)`) do NOT warn (per §4). Existing callers continue to function. Release notes flag the upcoming removal.
- **Phase 2 (after grace period)**: remove the SavedRule layer entirely per the surface enumeration in §3.2 and the end-state list in §9. Rules and inferences live in user Python modules / user-imported source, constructed via `Rule(...)` / `Inference(...)` and reaching evaluators via `_register_rule_dependencies` + `RuleRegistry` (in-memory, runtime-only).

This is the **strict-but-migration-aware** outcome:

- **Strict** because the end state matches design A20 literal ("rules 留在用户 Python 代码") exactly — no `SavedRule`, no `FileAuthoringRegistry` rule/inference persistence, no `fg.rules.save / ...` SDK surface.
- **Migration-aware** because shipped callers receive `DeprecationWarning` before removal, mirroring Q1's "compatibility-during-migration" precedent (Q1 §4.4 + Q1 §5).

Grace-period length is NOT decided by Q8. That is a release-engineering decision (number of releases / calendar window). Q8 commits to: deprecation now, removal at end of grace period.

## 2. Rejected Alternatives

### 2.1 Option (a) — Hard remove immediately

Rejected.

Reason: shipped `fg.rules.save / ...` + `fg.inferences.save / ...` + `SavedRuleRef` / `SavedInferenceRef` are part of the shipped public SDK contract (`src/factgraph/sdk/store.py:2092-2160`, `src/factgraph/application/authoring_runtime.py:20-79`). Immediate breaking removal in a single release breaks every existing caller without any migration path.

Q1 already established a "compatibility-during-migration" precedent for shipped write paths (Q1 §4.4 migration-surface table + Q1 §5 "This does not require immediate deletion of shipped retract/update APIs."). Hard removal of the SavedRule layer in one step is inconsistent with that precedent.

### 2.2 Option (b) — Mark deferred + keep shipped API as-is

Rejected.

Reason: option (b) preserves the shipped API and only documents the misalignment in release notes. This is the canonical "soften design strictness to match shipped reality" pattern explicitly prohibited by `feedback_audit_execution_discipline.md` Rule 2.

Design A20 ("rules 留在用户 Python 代码"), A11 ("Rule persistence 全部 deferred"), §17 D9 ("Rule persistence / SavedRule → 需要 rule registry / deployment governance" — i.e., absent in v1), and §3 cross-cut table line 73 ("Rules 先保持 code artifact;Database 只持事实和 schema anchor") jointly establish a strict prohibition that does not permit the SavedRule layer to remain in v1.

Option (b) does not align with the design — it merely documents that shipped exceeds the design. Q8 must align, not document.

## 3. Supporting Evidence

### 3.1 Design strict prohibition (verified literal references)

- `database-view-fg-layered-architecture.zh.md:73` (§3 cross-cut table): "Rule persistence / SavedRule registry | Rules 先保持 code artifact;Database 只持事实和 schema anchor"
- `database-view-fg-layered-architecture.zh.md:713` (§17 D9): "Rule persistence / SavedRule | 需要 rule registry / deployment governance" (deferred-trigger condition; absent in v1)
- `database-view-fg-layered-architecture.zh.md:730` (§18 A11): "branch / writable sub-fg / remote / multi-db / Rule persistence 全部 deferred"
- `database-view-fg-layered-architecture.zh.md:739` (§18 A20): "...rules 留在用户 Python 代码"

Joint literal reading: v1 design has no SavedRule persistence layer.

### 3.2 Shipped SavedRule layer (verified surface, expanded per Q8 review B1)

Full surface in Q8 governance scope. Phase 1 deprecation warnings must cover all public + semipublic CREATE/READ surfaces;Phase 2 removes all rule+inference responsibilities while keeping the `FileAuthoringRegistry` class alive for the schema portion (per §4).

#### 3.2.1 Public SDK facade — `fg.rules.*` / `fg.inferences.*`

| Surface | File:Line |
|---|---|
| `fg.rules.save(rule)` | `src/factgraph/sdk/store.py:2092-2103` |
| `fg.rules.load(rule, *, version=None)` | `src/factgraph/sdk/store.py:2105-2111` |
| `fg.rules.list()` | `src/factgraph/sdk/store.py:2113-2118` |
| `fg.rules.get(rule_id)` | `src/factgraph/sdk/store.py:2120-2125` |
| `fg.inferences.save(inference)` | `src/factgraph/sdk/store.py:2127-2138` |
| `fg.inferences.load(...)` | `src/factgraph/sdk/store.py:2140-2146` |
| `fg.inferences.list()` | `src/factgraph/sdk/store.py:2148-2153` |
| `fg.inferences.get(inference_id)` | `src/factgraph/sdk/store.py:2155-2160` |

#### 3.2.2 SDKRegistry rule/inference surface — `src/factgraph/sdk/registry.py`

Public/semipublic registry facade separate from `fg.rules.*` / `fg.inferences.*`. Must also receive Phase 1 deprecation warnings (per B1) — otherwise users have an undeprecated escape hatch into the same SavedRule layer.

| Surface | File:Line |
|---|---|
| `SDKRegistry.register_rule_spec(payload)` | `sdk/registry.py:93-97` |
| `SDKRegistry.register_rule(rule, *, schema_ir=...)` | `sdk/registry.py:99-107` (compiles SDK `Rule` → spec then calls `register_rule_spec`) |
| `SDKRegistry.register_inference_spec(payload)` | `sdk/registry.py:109-113` |
| `SDKRegistry.register_inference(inference, *, schema_ir=...)` | `sdk/registry.py:115-134` (compiles SDK `Inference` → spec then calls `register_inference_spec`) |
| `SDKRegistry.list_rule_ids()` | `sdk/registry.py:163-167` |
| `SDKRegistry.list_inference_ids()` | `sdk/registry.py:169-173` |
| `SDKRegistry.list_rule_versions(rule_id)` | `sdk/registry.py:175-179` |
| `SDKRegistry.list_inference_versions(inference_id)` | `sdk/registry.py:181-185` |
| `SDKRegistry.get_latest_rule_spec(rule_id)` | `sdk/registry.py:205-209` |
| `SDKRegistry.get_latest_inference_spec(inference_id)` | `sdk/registry.py:211-215` |
| `SDKRegistry.read_rule_spec(rule_id, version)` | `sdk/registry.py:217-221` |
| `SDKRegistry.read_inference_spec(inference_id, version)` | `sdk/registry.py:223-227` |

#### 3.2.3 Authoring publish + apply pipeline

| Surface | File:Line | Q8 effect |
|---|---|---|
| `SDKRegistry.apply_authoring_bundle(rule_request=..., derivation_request=...)` | `sdk/registry.py:56-79` | Phase 1: warns when `rule_request` or `derivation_request` is non-None. Phase 2: rule_request / derivation_request branches rejected;`authoring_schema=` branch survives. |
| `SDKRegistry.apply_schema_classes(...)` | `sdk/registry.py:42-54` | OUT of Q8 scope (schema-only path; see §4) |
| Action name mapping `rule_preflight → register_rule_spec` | `authoring/publish.py:245-250` | Phase 2: `rule_preflight` action removed |
| Action name mapping `derivation_preview → register_inference_spec` | `authoring/publish.py:245-250` | Phase 2: `derivation_preview` action removed |
| Action name mapping `schema_preflight → upsert_schema_ir` | `authoring/publish.py:245-250` | OUT of Q8 scope |
| Dispatch `register_rule_spec / register_inference_spec` | `authoring/apply_execute.py:469-512` | Phase 2: rule/inference dispatch branches removed (lines 483-488 + 506-511);schema dispatch branches (481-482 + 504-505) survive |

#### 3.2.4 Application + FS layer

| Surface | File:Line |
|---|---|
| `save_rule(registry, payload, schema_ir=...)` | `src/factgraph/application/authoring_runtime.py:54-65` |
| `save_inference(registry, payload, schema_ir=...)` | `src/factgraph/application/authoring_runtime.py:68-79` |
| `SavedRuleRef(rule_id, version)` | `src/factgraph/application/authoring_runtime.py:20-34` |
| `SavedInferenceRef(inference_id, version)` | `src/factgraph/application/authoring_runtime.py:37-51` |
| `FileAuthoringRegistry.register_rule_spec(...)` | `src/factgraph/authoring/registry_fs.py:83-118` |
| `FileAuthoringRegistry.register_inference_spec(...)` | `src/factgraph/authoring/registry_fs.py:145-182` |
| `FileAuthoringRegistry.preview_register_rule_spec(...)` | `src/factgraph/authoring/registry_fs.py:120-143` |
| `FileAuthoringRegistry.preview_register_inference_spec(...)` | `src/factgraph/authoring/registry_fs.py:184-208` |
| `FileAuthoringRegistry.list_rule_ids()` | `src/factgraph/authoring/registry_fs.py:292-301` |
| `FileAuthoringRegistry.list_inference_ids()` | `src/factgraph/authoring/registry_fs.py:303-312` |
| `FileAuthoringRegistry.list_rule_versions(rule_id)` | `src/factgraph/authoring/registry_fs.py:314-324` |
| `FileAuthoringRegistry.list_inference_versions(inference_id)` | `src/factgraph/authoring/registry_fs.py:326-336` |
| `FileAuthoringRegistry.get_latest_rule_spec(rule_id)` | `src/factgraph/authoring/registry_fs.py:338-352` |
| `FileAuthoringRegistry.read_rule_spec(rule_id, version)` | `src/factgraph/authoring/registry_fs.py:354-372` |
| `FileAuthoringRegistry.get_latest_inference_spec(inference_id)` | `src/factgraph/authoring/registry_fs.py:374-388` |
| `FileAuthoringRegistry.read_inference_spec(inference_id, version)` | `src/factgraph/authoring/registry_fs.py:390-408` |
| `registry_manifest.json` rule entries written at | `src/factgraph/authoring/registry_fs.py:100-110` |
| `registry_manifest.json` inference entries written at | `src/factgraph/authoring/registry_fs.py:163-174` |
| `registry/rules/<rule_id>/<version>.json` file path | `register_rule_spec` write target (`:88-90`) |
| `registry/inferences/<inference_id>/<version>.json` file path | `register_inference_spec` write target (`:151-153`) |

All §3.2.4 entries are Phase 2 removal targets EXCEPT `upsert_schema_ir` + `preview_upsert_schema_ir` (in §4). **The `FileAuthoringRegistry` class itself survives Phase 2** with only its schema-related methods + apply-log methods retained (per T2; see §5 for apply-log scoping per B2).

### 3.3 Q1 precedent for compatibility-during-migration

Q1 (`docs/decisions/2026-05-20_q1-database-class-boundary-decision.md`):

- §4.4 migration-surface table classifies shipped write paths with explicit "later migration must decide" status for some surfaces.
- §5 "This does not require immediate deletion of shipped retract/update APIs."

Q8 follows the same pattern: shipped surface remains during deprecation window, removed after grace period.

### 3.4 Audit Rule 2 (design strictness must not be softened)

Per `feedback_audit_execution_discipline.md` Rule 2: when design says strict prohibition ("MUST NOT" / "全部不进" / "deferred" / "留在用户"), the Q-row must enumerate resolution options that actually align with design, not just document misalignment.

Option (b) is the "document misalignment" pattern explicitly rejected by Rule 2. Q8 selects from the design-aligning options (a) or (c) only.

## 4. Schema Persistence Boundary (OUT of Q8 scope)

`FileAuthoringRegistry.upsert_schema_ir` (`src/factgraph/authoring/registry_fs.py:47-67`) is **OUT of Q8 scope**.

Schema persistence has a different fate per audit A16(B) + A20(E):

- A16(B) commits compiled schema persistence to `db/objects/schema/<schema_digest>.json` content-addressed (under Database, not registry).
- A20(E) says shipped `registry/schema/schema_ir.json` migrates to that path.

Schema persistence is **migrated**, not **removed**. Q8 governs only the rule / inference / manifest-rule-inference-entries / apply-log portions of `FileAuthoringRegistry`.

After Q8 Phase 2 closes + A20(E) migration closes, the `registry/` directory may be entirely empty (or absent). That's a workspace-layout question for I13 / A17 / A19 / A20(E) cluster, not Q8.

## 5. Downstream Artifact Lifecycles (tightened per Q8 review B2)

### 5.1 `registry_manifest.json` — partial migration

`registry_manifest.json` (`src/factgraph/authoring/registry_fs.py:40-41`) carries 3 distinct sections:

- `schema` entry — OUT of Q8 scope (A16(B) / A20(E)).
- `rules` entries (`registry_fs.py:100-110`) — Q8 removal scope, exit at Phase 2.
- `inferences` entries (`registry_fs.py:163-174`) — Q8 removal scope, exit at Phase 2.

Under Q8 = (c):

- **Phase 1**: manifest continues to write all 3 sections.
- **Phase 2**: manifest's `rules` and `inferences` sections exit. The `schema` entry may persist until A20(E) migration moves schema to `db/objects/schema/<digest>.json`. The manifest file as a whole continues to exist as long as the schema section is present;its eventual disappearance is governed by A20(E), not Q8.

Sequencing between Q8 Phase 2 and A20(E) is release-engineering territory.

### 5.2 `authoring_apply_events.jsonl` — event-kind scoping (per B2)

`authoring_apply_events.jsonl` (path at `registry_fs.py:43-45`) is **not solely downstream of SavedRule**.

The log is written via `append_apply_event` (`registry_fs.py:210-216`) and read via `find_apply_execute_run` (`:218-242`) and `list_apply_execute_runs` (`:244-267`). It records `authoring_apply_execute_run` events (event kind discriminator at `:237` and `:261`) that can carry any of the action dispatchers:

- `rule_preflight` / `register_rule_spec` / `preview_register_rule_spec` — Q8 scope
- `derivation_preview` / `register_inference_spec` / `preview_register_inference_spec` — Q8 scope
- `schema_preflight` / `upsert_schema_ir` / `preview_upsert_schema_ir` — **OUT of Q8 scope** per §4

Per B2: Q8 governs event KINDS, not the log file as a whole.

Under Q8 = (c):

- **Phase 1**: log continues to write all event kinds.
- **Phase 2**: rule/inference event kinds stop being appended because their action dispatchers are removed (per §3.2.3). Schema event kinds continue to be written so long as schema persistence remains in `FileAuthoringRegistry`.
- **Post-A20(E)**: if schema also exits the registry-side apply pipeline (per A20(E) workspace-layout migration), `authoring_apply_events.jsonl` may exit entirely. That fate is governed by A16(B) / A20(E) / Q6, **NOT Q8**.

### 5.3 Apply-log readers — remain available post-Phase-2

`SDKRegistry.list_apply_run_ids` (`sdk/registry.py:187-191`), `SDKRegistry.list_apply_runs` (`:193-197`), `SDKRegistry.show_apply_run(apply_request_id)` (`:199-203`) read this log. Under Q8 = (c), these readers remain available post-Phase-2 to inspect existing rule/inference history (read-only of frozen log content), but no new rule/inference events get written.

Their long-term fate follows the broader apply-log fate (A20(E) / Q6), not Q8.

## 6. Q6 Interaction — Q6 is contingent on Q8 + schema registry overlap (tightened per B2)

Per audit §8 Q8 final paragraph, Q6 (registry-in-workspace migration) is contingent on Q8.

Under Q8 = (c):

- **During Phase 1 (deprecation)**: Q6 fully applies. The `registry/` directory exists and Q6's location mechanics (workspace-coupled vs external `registry_root=`) remain relevant for rules + inferences + schema portions.
- **After Phase 2 (rule/inference removal)**: Q6 becomes **partially vacuous**. Rule + inference portions exit, so Q6 location mechanics no longer apply to those. **Q6 still applies to the schema portion** of the registry until A20(E) migrates schema to `db/objects/schema/<digest>.json`, AND to the residual `authoring_apply_events.jsonl` (which continues writing schema event kinds per §5.2).
- **After A20(E) closes**: Q6 becomes fully vacuous (registry directory may be absent entirely; apply log may also exit per §5.2 if no remaining writers).

Q6 should still be drafted to govern (i) the Phase-1 deprecation window for all portions, and (ii) the post-Phase-2 schema-only window between Q8 Phase 2 and A20(E) closure.

## 7. Consequences

### 7.1 A11 SavedRule + A15 (A-persisted) + A20 (A)(B)(C)(D)(F) + D9

All five drift items resolve to the Q8 outcome:

- **A11 SavedRule**, **A15 A-persisted**, **A20 (A)(B)(C)(D)(F)**: currently `(c) shape conflict` per audit;Q8 = (c) makes migration explicit. Post-Phase-2 state = aligned with design.
- **D9** Rule persistence / SavedRule: shipped exceeds deferral today;post-Phase-2 = aligned with D9 deferred status.

### 7.2 A19 manifest reshape gated on Q8 Phase 2

A19 design 4-field manifest does NOT include `components.registry`. Under Q8 = (c):

- During Phase 1: shipped 6-field manifest still carries `components.registry`. A19 reshape cannot complete yet.
- After Phase 2: manifest may drop `components.registry`. A19 design shape becomes reachable.

A19 implementation timing is therefore gated on Q8 Phase 2.

### 7.3 Q1 / Q3 unaffected

Q1 (Database boundary) and Q3 (tx identity primitives) are independent of Q8. No interaction. Database does NOT gain rule persistence at Phase 2 — rules live in user Python only.

### 7.4 SDK runtime path unchanged

In-memory `Rule(...)` / `Inference(...)` construction + `_register_rule_dependencies` + `RuleRegistry` are NOT in Q8 scope. The runtime path continues to function (and becomes the only blessed path post-Phase-2). User code constructs Rule/Inference objects from imported Python modules and passes them to `evaluate(...)` / what-if shells / etc.

### 7.5 Q7 unaffected

Q7 (AssertionRecord shape) operates on assertion record shapes, not on rule persistence. Q7 and Q8 are mutually independent. Q8 closure does not change Q7's options.

## 8. Acceptance Criteria For This Decision

Future Q8-dependent blueprints must obey:

1. Do NOT extend the SavedRule layer with new persistence capabilities at ANY surface (no new `save_*` methods on `fg.rules.*` / `fg.inferences.*`, no new `SDKRegistry.register_*` methods, no new `Saved*Ref` shapes, no new `register_*_spec` methods on `FileAuthoringRegistry`, no new manifest sections under rules / inferences).
2. Do emit `DeprecationWarning` in Phase 1 from ALL public + semipublic SavedRule entry points (per B1):
   - `fg.rules.save / load / list / get` and `fg.inferences.save / load / list / get` (`sdk/store.py:2092-2160`)
   - `SDKRegistry.register_rule_spec / register_rule / register_inference_spec / register_inference` (`sdk/registry.py:93-134`)
   - `SDKRegistry` rule/inference read/list methods: `list_rule_ids / list_inference_ids / list_rule_versions / list_inference_versions / get_latest_rule_spec / get_latest_inference_spec / read_rule_spec / read_inference_spec` (`sdk/registry.py:163-227`)
   - `SDKRegistry.apply_authoring_bundle(rule_request=..., derivation_request=...)` — warn only when `rule_request` or `derivation_request` is non-None (`sdk/registry.py:56-79`). Schema-only invocations (`authoring_schema=` or via `apply_schema_classes`) do NOT warn.
3. Do NOT route SavedRule persistence through the new Database boundary (rules are not Database content per Q1 + A20).
4. Do retain runtime in-memory `Rule` / `Inference` / `RuleRegistry` / `_register_rule_dependencies` (out of Q8 removal scope).
5. Do retain `FileAuthoringRegistry.upsert_schema_ir` + `preview_upsert_schema_ir` + schema-related apply pipeline (schema persistence governed by A16(B) / A20(E), not Q8). **The `FileAuthoringRegistry` CLASS survives Phase 2** (per T2);only its rule/inference responsibilities exit. Class-level rename, deletion, or schema-decoupling is governed by A20(E), not Q8.
6. Do NOT use Q8 deprecation as cover for permanent retention — the design end-state is removal;deprecation is migration mechanics only.
7. Do treat Q6 outcomes as applying to (i) the Phase-1 deprecation window (all portions) AND (ii) the post-Phase-2 schema-only window (until A20(E) migrates schema out). Q6 only becomes fully vacuous after A20(E) closes.
8. Do NOT freeze A19 manifest reshape until Q8 Phase 2 closes. Manifest `rules` + `inferences` sections exit with Phase 2;the `schema` section follows A20(E);`components.registry` field in workspace manifest follows the broader manifest-section fate.
9. Do NOT remove the runtime in-memory `RuleRegistry` mechanism — it is the design-blessed path going forward.
10. Phase 2 removal scope covers ALL `FileAuthoringRegistry` rule/inference methods (per T1):
    - Write methods: `register_rule_spec` / `register_inference_spec` / `preview_register_rule_spec` / `preview_register_inference_spec` (`authoring/registry_fs.py:83-208`)
    - Read/list methods: `list_rule_ids` / `list_inference_ids` / `list_rule_versions` / `list_inference_versions` / `get_latest_rule_spec` / `get_latest_inference_spec` / `read_rule_spec` / `read_inference_spec` (`authoring/registry_fs.py:292-408`)
    These read/list methods are NOT escape hatches that survive Phase 2 — they exit alongside the write surface.
11. `authoring_apply_events.jsonl` rule/inference EVENT KINDS exit at Phase 2 (per B2);schema event kinds continue per §4 / §5.2. The log file's overall fate (whether it exits entirely) is governed by A20(E) / Q6, NOT Q8.
12. Apply-log readers (`SDKRegistry.list_apply_run_ids` / `list_apply_runs` / `show_apply_run` at `sdk/registry.py:187-203`) remain available post-Phase-2 to read existing rule/inference history. They do not gate new writes.
13. `SDKRegistry.apply_authoring_bundle` Phase-2 surface keeps the `authoring_schema=` branch (`sdk/registry.py:56-79`) and rejects `rule_request=` / `derivation_request=`. The dispatcher branches at `authoring/apply_execute.py:483-488` + `:506-511` are removed in Phase 2;schema dispatcher branches at `:481-482` + `:504-505` survive (governed by §4).

## 9. Decision Record

Q8 resolution: **gradual deprecation of the SavedRule persistence layer**.

### End-state at Phase 2

**Removed**:
- Public SDK facade: `fg.rules.save / load / list / get` + `fg.inferences.save / load / list / get`
- SDKRegistry surface: `register_rule_spec` / `register_rule` / `register_inference_spec` / `register_inference` + all SDKRegistry rule/inference read+list methods (`list_rule_ids` / `list_inference_ids` / `list_rule_versions` / `list_inference_versions` / `get_latest_rule_spec` / `get_latest_inference_spec` / `read_rule_spec` / `read_inference_spec`)
- `SDKRegistry.apply_authoring_bundle` `rule_request=` / `derivation_request=` branches (only `authoring_schema=` branch survives)
- Authoring pipeline: `rule_preflight` / `derivation_preview` action name mappings (`publish.py:245-250`) + `register_rule_spec` / `register_inference_spec` dispatcher branches (`apply_execute.py:483-488 + :506-511`) + corresponding prevalidate branches
- Application boundary: `save_rule` / `save_inference` (`authoring_runtime.py:54-79`)
- Handle types: `SavedRuleRef` / `SavedInferenceRef` (`authoring_runtime.py:20-51`)
- FS layer: `FileAuthoringRegistry.register_rule_spec / register_inference_spec / preview_register_rule_spec / preview_register_inference_spec / list_rule_ids / list_inference_ids / list_rule_versions / list_inference_versions / get_latest_rule_spec / get_latest_inference_spec / read_rule_spec / read_inference_spec` (per T1)
- Filesystem: `registry/rules/` + `registry/inferences/` directories
- Manifest: `registry_manifest.json` `rules` and `inferences` sections (schema section follows A20(E))
- Apply log: rule/inference event KINDS in `authoring_apply_events.jsonl` (log file itself follows A20(E)/Q6, per B2)

**Retained** (per T2 — `FileAuthoringRegistry` class survives, only rule/inference responsibilities exit):
- `FileAuthoringRegistry` class + `upsert_schema_ir` + `preview_upsert_schema_ir` + schema-related apply pipeline
- `SDKRegistry.apply_schema_classes` + `SDKRegistry.apply_authoring_bundle(authoring_schema=...)` schema-only branch
- `SDKRegistry.upsert_schema_ir` / `read_manifest` / `get_schema_entry` (`sdk/registry.py:81-91, 157-161`)
- `SDKRegistry` apply-log readers (`list_apply_run_ids` / `list_apply_runs` / `show_apply_run`) — read-only access to frozen rule/inference history + ongoing schema event history
- Runtime: `Rule(...)` / `Inference(...)` / `RuleRegistry` / `_register_rule_dependencies` (design-blessed path)
- Manifest `schema` entry + schema event kinds in apply log (until A20(E) migrates schema out)

### Scope boundaries

- Schema persistence (`upsert_schema_ir`) is OUT of Q8 scope — governed by A16(B) / A20(E) workspace-layout migration.
- `authoring_apply_events.jsonl` is NOT solely a SavedRule downstream artifact (per B2). Q8 governs rule/inference event KINDS only; the log file's overall fate is governed by A20(E) / Q6.
- The `FileAuthoringRegistry` Python class is NOT removed by Phase 2 (per T2) — only its rule/inference responsibilities exit. Class-level fate is governed by A20(E).
- Q1 / Q3 / Q7 are unaffected.
- Q6 governs (i) Phase-1 (all-portions) registry location mechanics, AND (ii) post-Phase-2 schema-only location mechanics until A20(E) closes.
- A19 manifest reshape gates rule/inference section removal on Q8 Phase 2;`components.registry` field follows the broader manifest fate (A16(B)/A20(E)).
