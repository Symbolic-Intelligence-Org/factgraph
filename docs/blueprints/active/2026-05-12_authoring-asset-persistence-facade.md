# Task Blueprint: Authoring Asset Persistence Facade

- Status: draft
- Created: 2026-05-12
- Last Updated: 2026-05-12
- Related Modules:
  - `src/kernel/sdk/store.py`
  - `src/kernel/sdk/registry.py`
  - `src/kernel/sdk/dsl/rule.py`
  - `src/kernel/sdk/__init__.py`
  - `src/kernel/authoring/registry_fs.py`
  - `src/kernel/authoring/apply_execute.py`
  - `src/kernel/application/`
- Related Docs:
  - [docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md](../../references/working/design-points/factgraph-lifecycle-and-assets.zh.md)
  - [docs/blueprints/archive/2026-05-12_public-inference-factgraph-create.md](../archive/2026-05-12_public-inference-factgraph-create.md)
  - [docs/blueprints/archive/2026-05-12_inference-wire-registry-vocabulary.md](../archive/2026-05-12_inference-wire-registry-vocabulary.md)
- Audit Log:
  - [2026-05-12_authoring-asset-persistence-facade.audit.md](./2026-05-12_authoring-asset-persistence-facade.audit.md)

## 1. Problem

The lifecycle/assets sequence has completed two prerequisite slices:

1. Public SDK candidate-producing objects are now `Inference`, and
   `FactGraph.create(...)` exists.
2. Public service and registry vocabulary now uses inference routes, keys,
   methods, manifest entries, paths, and per-spec JSON.

The remaining public asset persistence surface is still `SDKRegistry`, a
separate facade:

```python
registry = SDKRegistry(root_dir="...")
registry.register_rule(rule)
registry.register_inference(inf)
registry.read_inference_spec("inf.id", "1.0.0")
```

That is no longer the desired product shape. Users think in terms of one
`FactGraph` and its domain namespaces:

```python
fg = FactGraph.create(schema_classes=[...], ...)
fg.rules.save(rule)
fg.rules.load("rule_id")
fg.inferences.save(inf)
fg.inferences.load("inference_id")
```

Blueprint 2 scopes that persistence facade. This is architecture-facing work:
it must decide where the registry is attached, what the public ref/return
types are, whether `SDKRegistry` remains public, and whether a new
`kernel.application.authoring_runtime` layer owns the shared save/load/list/get
logic.

## 2. Goals

- Add first-class `fg.rules.*` persistence methods.
- Add first-class `fg.inferences.*` persistence methods.
- Decide whether `RuleRef` is reused as a saved-rule return type or whether a
  new persisted ref DTO is needed.
- Decide whether to introduce `InferenceRef`.
- Decide how `FactGraph` obtains an authoring registry root or registry object.
- Decide whether `SDKRegistry` remains exported from `kernel.sdk`.
- Keep direct value-object runtime usage valid: saving rules/inferences must
  not become mandatory for `fg.eval.run(rule)` or `fg.eval.evaluate(inf)`.
- Preserve service/registry vocabulary from the preceding slice.

## 3. Non-goals

- Do not implement `FactGraph.save(...)` / `FactGraph.load(...)` workspace
  lifecycle. That is Blueprint 3.
- Do not implement schema mutation.
- Do not implement query persistence.
- Do not implement explain/evidence/audit namespace migration.
- Do not rename candidate/proof/application/core substrate vocabulary from
  derivation to inference.
- Do not change runtime `RuleRef(...)` where-clause semantics unless G0
  explicitly chooses to combine persisted refs with runtime refs.
- Do not alter `release/0.1.x`, `v0.1.0-rc.1`, `origin/v0.1-oss-prep`, or
  existing milestone refs.

## 4. Source Audit

### 4.1 `SDKRegistry` Current Surface

`SDKRegistry` is currently public:

- `src/kernel/sdk/__init__.py` imports and exports `SDKRegistry`.
- SDK invariant tests expect it in `kernel.sdk.__all__`.
- It is a thin wrapper over `FileAuthoringRegistry`, constructed with either
  `root_dir` or an existing registry object.

Public methods include:

- `apply_schema_classes(...)`
- `apply_authoring_bundle(...)`
- `read_manifest(...)`
- `upsert_schema_ir(...)`
- `register_rule_spec(...)`
- `register_rule(...)`
- `register_inference_spec(...)`
- `register_inference(...)`
- `get_schema_entry(...)`
- `list_rule_ids(...)`
- `list_inference_ids(...)`
- `list_rule_versions(...)`
- `list_inference_versions(...)`
- `list_apply_run_ids(...)`
- `list_apply_runs(...)`
- `show_apply_run(...)`
- `get_latest_rule_spec(...)`
- `get_latest_inference_spec(...)`
- `read_rule_spec(...)`
- `read_inference_spec(...)`

Return shapes are raw dicts/lists. Save/register methods return manifest-like
dicts with `kind/status/id/version/path/digest` fields. Reads return raw spec
dicts or `None`. This is useful substrate, but it is not a polished public
facade shape.

### 4.2 `FileAuthoringRegistry` Capabilities

`FileAuthoringRegistry` already has enough low-level methods to support
rule/inference save/load/list/get:

- schema IR upsert / manifest read / schema entry read;
- rule spec register/preview/read/list/latest;
- inference spec register/preview/read/list/latest;
- apply-event append/find/list.

It stores:

- `registry_manifest.json`
- `schema/schema_ir.json`
- `rules/{safe_id(rule_id)}/{safe_id(version)}.json`
- `inferences/{safe_id(inference_id)}/{safe_id(version)}.json`
- `authoring_apply_events.jsonl`

Important constraint: `read_inference_spec(...)` returns compiler-facing
payloads with `derivation_id`, translating back from persisted `inference_id`.
That W13a translation seam is deliberate and must not leak accidentally into
public `fg.inferences.load(...)` unless G0 chooses raw compiler payloads.

There is no single `FileAuthoringRegistry.read_schema_ir()` helper; SDK and
service currently duplicate schema-file loading around `get_schema_entry()`.

### 4.3 Current `RuleRef` Meaning

`RuleRef` is not currently a persisted asset handle. It is an SDK DSL carrier:

- frozen dataclass with `rule_id` and `version`;
- custom init can store hidden `_rule_obj` when constructed from a `Rule`;
- calling `RuleRef(...)(terms...)` yields a `RuleRefAtom`;
- lowering emits where IR `("ruleref", rule_id, version, terms)`;
- object-backed `RuleRef(existing_rule)` enables auto-registration of
  dependency rules during direct runtime execution.

It is accepted inside `Rule`, `Inference`, and `Query` where clauses. It is not
accepted as a direct `fg.eval.run(RuleRef(...))` object, despite one stale API
surface doc line implying that.

This creates a G0 decision: should `fg.rules.save(rule)` return the current
`RuleRef`, or is that overloading a where-clause DSL carrier with a persisted
asset handle?

### 4.4 Missing `InferenceRef`

There is no `DerivationRef` or `InferenceRef` today. Tests explicitly guard that
absence. Adding `fg.inferences.*` persistence probably requires choosing
between:

- raw ids / dicts;
- a new public `InferenceRef`;
- an `AssetRef`/`SavedInference`-style DTO.

If introduced, `InferenceRef` should be minted directly. A new public
`DerivationRef` should not be created.

### 4.5 SDK Namespace Shape

`fg.rules` exists today as `_SDKRulesManager` and only exposes:

```python
fg.rules.inspect(rule_or_inference)
```

The manager is private, returned through a read-only property, and blocks
attribute mutation. Adding methods to it is mechanically straightforward.

There is no `fg.inferences` namespace today. Blueprint 1 tests intentionally
guard its absence. Blueprint 2 will need to remove or invert that guard if it
adds real methods.

### 4.6 `FactGraph` / `SDKStore` Binding

`FactGraph` is a literal alias for `SDKStore`.

`SDKStore.__init__` currently accepts:

- `classes`
- optional `store`
- optional `schema_ir`
- optional `artifact_store_root`
- optional `default_row_format`

`FactGraph.create(...)` / `from_schema_classes(...)` accept:

- `schema_classes`
- optional `ledger`
- optional `ledger_path`
- optional `artifact_store_root`
- optional `default_row_format`

There is no authoring registry root, workspace root, or `FileAuthoringRegistry`
binding on `SDKStore`. Runtime `registry=` kwargs refer to core
`RuleRegistry`, not `FileAuthoringRegistry`.

This is the load-bearing Blueprint 2 decision. `fg.rules.save(...)` cannot be a
clean instance method unless `FactGraph` knows where to persist authoring
assets, or the method takes an explicit registry/root argument every time.

### 4.7 Application Layer Pattern

Existing `kernel.application` modules use frozen DTOs and pure runtime functions
around core/substrate types. Examples include `schema_runtime`,
`derivation_runtime`, check/diagnose/fact-overlay/why-not runtimes, and
capability helpers.

There is no `kernel.application.authoring_runtime` today. Existing authoring
workflow code directly imports `FileAuthoringRegistry` in `kernel.authoring`.

Blueprint 2 should decide whether to introduce an application-layer
authoring runtime before adding SDK namespace methods. This would keep
`SDKStore` from directly owning registry write semantics and would give future
service/workspace flows a shared substrate.

### 4.8 Stale Doc Finding

`src/kernel/sdk/docs/04_api_surface.en.md` currently says `run(rule_or_query)`
evaluates a `Rule`, `RuleRef`, or `Query`. Code does not accept direct
`RuleRef`. This should be fixed in the docs sync or as a G1 inventory polish,
because it confuses `RuleRef` as DSL atom vs persisted asset handle.

### 4.9 Current Test/Docs Impact

Direct `from kernel.sdk import SDKRegistry` appears in a small number of tests,
but `FileAuthoringRegistry` is used much more broadly in kernel/service/domain
tests and runtime paths.

SDK docs still teach `SDKRegistry` as a normal public object. The user guide has
stale registry examples from before the inference vocabulary rename. Authoring
docs already describe the W13a storage translation.

## 5. G0 Questions

### Q1 — Registry Attachment

- **A1a** `FactGraph.create(..., registry_root=...)` / `SDKStore(..., registry_root=...)`
  binds a `FileAuthoringRegistry` to the graph.
- **A1b** `fg.rules.save(rule, registry=...)` and `fg.inferences.save(inf, registry=...)`
  require explicit registry/root on each call.
- **A1c** Defer instance methods; keep only standalone `SDKRegistry` for now.

Recommendation: **A1a**. If the facade lives under `FactGraph`, persistence
should be graph-bound. Per-call registry arguments make the namespace feel like
a thin helper over the old facade.

### Q2 — Registry Constructor Shape

- **A2a** Accept `registry_root: str | Path | None`.
- **A2b** Accept `registry: FileAuthoringRegistry | None`.
- **A2c** Accept both, with the same conflict check pattern as `SDKRegistry`.

Recommendation: **A2c**. It preserves testability and lets advanced callers
inject a registry object, while normal users pass a root path.

### Q3 — Application Runtime Layer

- **A3a** Add `kernel.application.authoring_runtime` with pure save/load/list/get
  functions and DTOs.
- **A3b** Let `SDKStore` call `FileAuthoringRegistry` directly.
- **A3c** Keep logic in `SDKRegistry` and delegate from new namespaces.

Recommendation: **A3a**. This matches the application-first runtime authority
pattern and avoids making the SDK shell own authoring persistence semantics.

### Q4 — Public `SDKRegistry` Fate

- **A4a** Hard-cut `SDKRegistry` from `kernel.sdk.__all__` and docs in this
  slice; keep the module/importable class internally for tests/advanced use if
  needed.
- **A4b** Keep `SDKRegistry` public as advanced importable while adding
  `fg.rules.*` / `fg.inferences.*`.
- **A4c** Defer `SDKRegistry` fate.

Recommendation: **A4a** if Q1/Q3 land. The product surface should not have two
parallel persistence facades. The project is pre-release.

### Q5 — Rule Save Return Type

- **A5a** Return existing `RuleRef(rule_id, version)`.
- **A5b** Return a new persisted-asset DTO, e.g. `SavedRuleRef` or `RuleAssetRef`.
- **A5c** Return raw manifest dict.

Recommendation: **A5b**, unless G0 deliberately wants to overload `RuleRef`.
Current `RuleRef` has hidden object-backed behavior and where-clause semantics;
that is not the same as a saved asset handle.

### Q6 — Inference Save Return Type

- **A6a** Add `InferenceRef(inference_id, version)`.
- **A6b** Return raw manifest dict.
- **A6c** Return plain string id.

Recommendation: **A6a**. There is no existing public type to reuse, and raw
dicts would preserve the old registry facade shape.

### Q7 — Load Return Type

- **A7a** `load(...)` returns SDK value objects: `Rule` / `Inference`.
- **A7b** `load(...)` returns raw persisted spec dict.
- **A7c** Split names: `load(...)` returns object, `read_spec(...)` returns dict.

Recommendation: **A7a** for public namespace methods. If raw dict reads remain
needed, keep them behind internal registry/application APIs rather than
teaching them as the primary product surface.

### Q8 — List Return Type

- **A8a** `list()` returns typed refs.
- **A8b** `list()` returns ids only.
- **A8c** Provide both `list()` typed refs and `list_ids()` ids.

Recommendation: **A8a** for a compact first public surface. IDs-only makes
users immediately call `get/latest` for version context.

### Q9 — Method Names

- **A9a** Use `save/load/list/get`.
- **A9b** Use `create/read/list/get`.
- **A9c** Use `register/read/list/get`.

Recommendation: **A9a**, but G0 should acknowledge that this introduces a
new verb family relative to existing managers. `save/load` best matches durable
authoring asset intent.

### Q10 — `get` Semantics

- **A10a** `get(id)` returns latest version; `load(id, version=...)` or
  `load(ref)` reads a specific version.
- **A10b** `get(id, version)` requires explicit version.
- **A10c** Omit `get` in this slice.

Recommendation: **A10a**. It maps well to existing latest-version registry
helpers while keeping explicit-version load available.

### Q11 — Schema Persistence Coupling

- **A11a** `fg.rules.save` / `fg.inferences.save` requires schema IR already
  present in the registry and fails otherwise.
- **A11b** The first save automatically upserts the graph schema IR into the
  bound registry.
- **A11c** Add explicit `fg.schema.save()` first; asset save refuses until it is
  called.

Recommendation: **A11b** for ergonomics, but this is a real design choice.
`SDKRegistry.register_inference` currently reads registry schema IR to compile
objects, so the facade must avoid surprising "missing schema" failures.

### Q12 — Direct Runtime With Saved Refs

- **A12a** Saved refs are only load handles; users must `load(ref)` before
  `run/evaluate`.
- **A12b** `fg.eval.run(rule_ref)` and `fg.eval.evaluate(inference_ref)` are
  accepted by resolving through the bound registry.
- **A12c** Defer saved-ref runtime behavior.

Recommendation: **A12a** for this slice. It avoids colliding with current
`RuleRef` where-clause behavior and keeps the persistence facade focused.

### Q13 — `fg.inferences` Namespace

- **A13a** Add `_SDKInferencesManager` with persistence methods only.
- **A13b** Also move/alias evaluation under `fg.inferences`.
- **A13c** Defer `fg.inferences`; put inference persistence under `fg.rules`.

Recommendation: **A13a**. Inference persistence needs a real namespace now;
evaluation belongs under `fg.eval`.

### Q14 — Existing `fg.rules.inspect`

- **A14a** Keep `fg.rules.inspect(...)` unchanged and add persistence methods
  alongside it.
- **A14b** Move inspect elsewhere before adding persistence.

Recommendation: **A14a**. The namespace can own rule/inference structure and
asset lifecycle together.

### Q15 — Query Persistence

- **A15a** Explicitly defer query persistence; no `fg.queries` namespace.
- **A15b** Add query persistence now for parity.

Recommendation: **A15a**. Query persistence has a different substrate and no
current registry surface.

### Q16 — Docs / Stale `run(RuleRef)` Claim

- **A16a** Fix the stale `run(RuleRef)` API-surface teaching in this slice.
- **A16b** Leave it for separate docs cleanup.

Recommendation: **A16a**. It directly affects G0 decisions about whether refs
are runtime selectors or persistence handles.

## 6. Boundaries And Invariants

- Direct value-object runtime remains valid:
  `fg.eval.run(rule)` and `fg.eval.evaluate(inf)` do not require prior save.
- `RuleRef(...)` where-clause semantics remain valid unless G0 explicitly
  chooses to overload it.
- Existing service/registry inference vocabulary remains intact.
- `FileAuthoringRegistry` remains the storage substrate.
- Public lifecycle methods must not leak manifest-entry dicts unless G0 chooses
  raw dict return types.
- `fg.inferences` must only be added if it has real persistence behavior.
- `SDKRegistry` export/docs fate must be explicit; do not accidentally leave two
  public persistence surfaces.
- `release/0.1.x`, `v0.1.0-rc.1`, `origin/v0.1-oss-prep`, and milestone refs
  remain untouched.

## 7. Acceptance

- [ ] G0 locks registry attachment shape.
- [ ] G0 locks whether `kernel.application.authoring_runtime` is introduced.
- [ ] G0 locks public ref/return types for rules and inferences.
- [ ] G0 locks `SDKRegistry` public fate.
- [ ] G0 locks load/list/get semantics.
- [ ] G0 locks schema persistence behavior.
- [ ] G1 adds red tests for `fg.rules.save/load/list/get`.
- [ ] G1 adds red tests for `fg.inferences.save/load/list/get`.
- [ ] G1 adds guard tests that direct runtime value-object use remains valid.
- [ ] G1 adds guard tests for service/registry inference vocabulary preservation.
- [ ] G1 adds negative/positive tests for `SDKRegistry` export fate.
- [ ] G2 implements only the locked facade/application-layer changes.
- [ ] G3 updates SDK, authoring, and lifecycle docs.
- [ ] G4 fills §10, marks implemented, and archives this blueprint pair.

## 8. Implementation Plan

Draft sequence, subject to G0:

1. G1 red baseline and boundary guards:
   - persistence namespace shape;
   - registry binding behavior;
   - ref/return shapes;
   - SDKRegistry public fate;
   - direct runtime preservation;
   - service/registry vocabulary preservation.
2. G2 application layer:
   - add `kernel.application.authoring_runtime` if selected;
   - define request/result DTOs or ref DTOs if selected;
   - centralize schema-registry handling.
3. G2 SDK binding and namespace managers:
   - add registry binding to `FactGraph` / `SDKStore` if selected;
   - add `_SDKInferencesManager`;
   - extend `_SDKRulesManager`;
   - wire methods to application runtime.
4. G2 public surface cleanup:
   - update `kernel.sdk.__all__`;
   - adjust `SDKRegistry` export/docs/tests according to G0;
   - update stale `run(RuleRef)` docs or tests if selected.
5. G3 docs sync:
   - SDK API surface;
   - user guide;
   - rules/inferences guide;
   - authoring docs;
   - lifecycle design-point.
6. G4 close-out and archive.

## 9. Docs To Update

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/03_rules_and_inferences.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/authoring/docs/01_overview.md`
- `docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md`
- `docs/README.md` if any durable docs entry is added.

## 10. Outcome / Deviations

Task completion will fill:

- Final landed behavior:
- Validation:
- Commit lineage:
- Deviations:
- Archive notes:
