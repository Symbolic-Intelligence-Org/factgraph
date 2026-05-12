# FactGraph Lifecycle And Authoring Assets

Status: working / non-authoritative
Authority: This note is design input for a future blueprint. It is not current implementation truth. If any conclusion here becomes durable, migrate it into the relevant `src/kernel/*/docs/` module docs or `docs/architecture_principles.md`.
Last Updated: 2026-05-12

## 1. 问题陈述

当前 public SDK 已经有一个清晰的 `FactGraph` mental model:

```python
fg = FactGraph.create(schema_classes=[User, Document])
fg.write.add(...)
fg.read.find(...)
fg.eval.run(...)
fg.what_if.check(...)
```

Blueprint 3 已让 `FactGraph` 的 workspace 生命周期成为一等公民:

- `FactGraph.create(...)` 现在是 public lifecycle constructor,并可绑定 `path=` workspace root 或 `registry_root=` / `registry=` 给 authoring asset persistence 使用; `FactGraph.from_schema_classes(...)` 仍可作为 class-first lower-level constructor substrate。
- `fg.save(path=None)` 写入 v1 workspace layout: `factgraph_workspace.json` + `ledger.db` + `registry/`。
- `FactGraph.load(path, schema_classes=[...])` 读取 workspace,要求 Python schema classes,并验证 manifest / ledger / registry / provided classes 的 schema digest。
- `SDKRegistry` 已从 `kernel.sdk` public export surface hard-cut; `kernel.sdk.registry.SDKRegistry` 仍作为 advanced/internal wrapper 存在。普通用户的 authoring asset lifecycle 入口已经转到 `fg.rules.*` / `fg.inferences.*`。
- `Rule` / `Inference` 现在仍作为独立 value object 参与 runtime call; durable authoring asset 的 save/load/list/get 入口已经自然地长在 graph-bound namespaces 上。
- schema 的 add/delete/update/migration 还没有明确 public story。
- evidence / audit capability 后续会变大,但不应在 lifecycle 设计里被误塞进 registry 或 query/rule namespace。
- `Query` 没有纳入当前 registry story,这不是原则性决定,只是当前实现还没有 query asset persistence。
- Blueprint 1 已将 public SDK candidate-producing value object hard-cut 为 `Inference`,同时把 proof/audit/application substrate 的 derivation vocabulary 留给后续 wire/registry/proof cleanup。

这个 note 的目标不是立刻改 API,而是把下一轮 blueprint 的设计边界先放清楚:

1. `FactGraph` 是否应该拥有 `create/load/save`? Blueprint 1 + Blueprint 3 已回答为 yes。
2. Registry 是否应该降级为实现机制甚至直接退出 public SDK,由 `fg.rules.*`、`fg.inferences.*` 和 future `fg.queries.*` 承担用户-facing asset lifecycle?
3. `fg.schema.add/delete/update` 应该怎么表达,以及哪些动作第一阶段不应该实现?
4. explain / evidence capability 和 query asset 应该放在哪里,避免之后命名重做?
5. 现有 assertion/read/write/view 语法是否保持不受影响?
6. public SDK 已 hard-cut 为 `Inference` 后,internal/wire `derivation_*` vocabulary 应该在哪个后续切片统一 rename?

Pre-release framing: 产品尚未正式发布,所以这里不以历史 public compatibility 为硬约束。`SDKRegistry` 已经在 Blueprint 2 从 public SDK hard-cut,`from_schema_classes(...)` 仍作为 lower-level constructor substrate 保留。后续 blueprint 仍应优先选择更干净的 public mental model。

## 2. Source-Grounded Current State

### 2.1 Post-L SDK namespace taxonomy

The post-L SDK ergonomics redesign locked a teaching taxonomy in `docs/blueprints/archive/2026-05-09_post-l-sdk-ergonomics-redesign.md`.

The important points for this note:

- `FactGraph = SDKStore` was shipped as the user-facing entrypoint name.
- The taxonomy is concept-first, not resource-first:
  - `schema`
  - `read`
  - `write`
  - `eval`
  - `what_if`
  - `audit`
  - `package`
  - `views`
- `from_schema_classes` and `batch` were intentionally kept top-level because they are entrypoint/context-construction APIs, not ordinary namespace methods.

That last point matters: keeping `from_schema_classes` top-level was right for that slice, but it also leaves room for a more explicit lifecycle entrypoint:

```python
fg = FactGraph.create(...)
fg = FactGraph.load(...)
fg.save(...)
```

`create/load/save` are also entrypoint / lifecycle APIs, so they belong top-level if they exist.

### 2.2 Current FactGraph construction

Current implementation lives in `src/kernel/sdk/store.py`.

Key facts:

- `FactGraph` is a literal alias of `SDKStore`.
- `SDKStore.__init__(classes, ...)` still expects Python `Entity` classes.
- `SDKStore.from_schema_classes(classes, *, ledger=None, ledger_path=None, artifact_store_root=None, registry_root=None, registry=None, default_row_format=None)`:
  - compiles schema from classes;
  - computes `schema_digest`;
  - optionally binds a `Ledger(path=ledger_path)`;
  - stores / checks `ledger` metadata `schema_digest`;
  - optionally binds a file artifact sidecar;
  - optionally binds a `FileAuthoringRegistry` via `registry_root=` or
    `registry=`;
  - constructs `SDKStore`.

So `from_schema_classes` is already doing more than "compile classes": it is the current graph construction point for schema + ledger + artifact sidecar. That makes it a natural implementation substrate for `FactGraph.create(...)`. Because the product is pre-release, a future blueprint may still decide to hard-cut it from the canonical public surface once `create/load` are clean.

### 2.3 Current Registry capability

Current implementation lives in `src/kernel/sdk/registry.py`.

`kernel.sdk.registry.SDKRegistry` wraps `FileAuthoringRegistry` and currently supports:

- path or prebuilt registry construction;
- `apply_schema_classes(...)`;
- `apply_authoring_bundle(...)`;
- `read_manifest()`;
- `upsert_schema_ir(...)`;
- `register_rule_spec(...)`;
- `register_rule(...)`;
- `register_inference_spec(...)`;
- `register_inference(...)`;
- schema/rule/derivation lookup and listing helpers;
- apply-run listing/showing.

Important asymmetry:

- Rules and derivations are supported as durable authoring assets.
- Query persistence is not currently present as a first-class registry capability.
- Runtime code already accepts registry objects in several paths, so `RuleRef(...)` and registered authoring assets are already a real mechanism.

This supports the claim that registry is a real implementation mechanism. It does **not** imply that `SDKRegistry` should remain a public SDK concept. Blueprint 2 removed `SDKRegistry` from `kernel.sdk.__all__`; the advanced wrapper remains available from `kernel.sdk.registry` while graph-bound `fg.rules.*` / `fg.inferences.*` serve as the normal product facade.

### 2.4 Current Rule / Inference object model

Rules and inferences are independent SDK value objects.

This is a good property and should not be lost. It enables:

```python
rule = Rule(...)
fg.eval.run(rule)

inf = Inference(...)
fg.eval.evaluate(inf, semantics=ProbLogSemantics(...))
```

Durable registration should be optional:

```python
fg.rules.save(rule)
fg.inferences.save(inf)
```

The design goal is not "everything must be registered before use." The goal is "ephemeral value-object use and durable saved-asset use should both be first-class, with clear names."

### 2.5 Current docs surface

Current SDK docs still teach `SDKRegistry` as an independent object in `src/kernel/sdk/docs/00_user_guide.en.md` and `src/kernel/sdk/docs/04_api_surface.en.md`.

That is accurate for today's API, but it is not necessarily the ideal future shape. If `FactGraph.load/save` and `fg.rules.save/load` land, docs do not need a long compatibility migration. They can make `SDKRegistry` internal/advanced immediately, or remove it from public teaching and exports entirely, because no released contract depends on it yet.

### 2.6 Additional code facts that constrain the design

Follow-up code review surfaced several facts that should be treated as design constraints before any blueprint starts.

1. **`_SDKBatchTx.save(...)` already exists.**
   `src/kernel/sdk/batch.py` defines `save(obj, *, include_deps=True, meta=None)` on the batch transaction handle. It means "stage/commit this object into the batch transaction", not "persist the entire FactGraph workspace." Any future `fg.save(...)` must explicitly disambiguate graph-level save from batch-handle save.

2. **No current SDK namespace manager uses `save/load` as a verb pair.**
   Existing managers use domain verbs:
   - `views.create/update/delete/get/list`
   - `schema.ingest/validate_provenance`
   - `read.get/find/ref`
   - `write.set/add/retract/edit`
   - `rules.inspect`
   - `eval.run/evaluate/evaluate_compiled/inspect_semantics/accept*`
   - `audit.explain_fact/conflicts/diff_proof_frames`
   - `package.export_package/run_package`

   Therefore `fg.rules.save/load/list` and `fg.inferences.save/load/list`
   introduce a new verb family. Blueprint 2 explicitly accepted this because
   saved authoring assets behave more like durable files than like in-memory
   `views.create/update/delete` entries.

3. **Ledger metadata is sparse.**
   Current ledger metadata is a key/value table, and the known construction path stores `schema_digest`. It does not store workspace root, registry root, artifact sidecar root, view definitions, or Python class import paths. This is the key constraint on `FactGraph.load(...)`.

4. **Package export already draws a boundary.**
   Current package export includes schema/policy/facts/rules/outputs/audit-like material depending on package kind/options, but it is not equivalent to a graph workspace save. Registry manifest and views are not currently treated as package state. The save-vs-package distinction is therefore not only future theory; the code already implies it.

5. **Round events live in a separate audit file layer.**
   Audit round events are file-backed separately from ledger rows. A future graph workspace save must decide whether audit/evidence files are in scope; it cannot assume "ledger save" includes audit evidence.

6. **`SDKRegistry.register_inference(...)` can recover schema IR from the registry.**
   If `schema_ir` is omitted, registry code can retry compilation using persisted registry schema IR. This is a real precedent for registry as a durable schema reference, but it is not enough for class-less `FactGraph.load(...)` because the typed SDK still needs Python `Entity` classes or a dynamic facade.

7. **`SDKStore.__init__` now has registry attachment parameters.**
   Blueprint 2 chose constructor attachment: `registry_root=` constructs a
   `FileAuthoringRegistry`, and `registry=` accepts a prebuilt one. Both can be
   supplied only when their roots match. Workspace-derived registry remains
   future Blueprint 3 scope.

8. **`views` is the closest manager precedent, but it is in-memory.**
   `_SDKViewsManager` already has `create/update/delete/get/list`, but those views are not currently a registry-backed persisted asset. This matters because `fg.save(...)` either needs to include views deliberately or preserve today's in-memory-only status.

9. **`Derivation` public rename has low symbol collision but high substrate reach.**
   Code audit found no existing `Inference` public class/export/file namespace collision. By contrast, `Derivation` appears across SDK DSL, tests, service routes, service payload keys, application protocol names, authoring compile functions, registry manifest keys, and filesystem paths such as `derivations/{id}/{version}.json`. Therefore public SDK rename is feasible, but full-stack substrate rename is a separate slice.

10. **Public persistence returns typed saved refs.**
   `SDKRegistry.register_rule(...)` and `SDKRegistry.register_inference(...)`
   still return dict-shaped manifest entries on the advanced/internal path.
   Public `fg.rules.save(...)` / `fg.inferences.save(...)` return
   `SavedRuleRef` / `SavedInferenceRef` instead, so registry manifest structure
   does not become the product return contract.

11. **Query identity is runtime-derived, not a persisted authoring identity.**
   `Query` is an SDK value object with runtime payload lowering, but no user-managed id/version persistence surface. The current runtime query id is a deterministic digest-like id (`__query__:<digest>`) derived from query shape and schema context, not a durable authoring asset id. That makes `fg.queries.save/load/list` a real design problem, not a cheap namespace parity add.

12. **File registry layout is concrete but still substrate vocabulary.**
   The current file registry uses `registry_manifest.json`, `schema/schema_ir.json`, `rules/{id}/{version}.json`, `derivations/{id}/{version}.json`, and apply-run logs. This is important implementation material for persistence, but not a reason to preserve `derivations` as public product vocabulary after an `Inference` rename.

## 3. Historical And Design Context

### 3.1 Rule / policy / function-tree note

`docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md` already proposed a more domain-oriented tree. It included:

- data/read/write/assertion/view surfaces;
- rules;
- policy/theory;
- explain/simulate/audit;
- registry as a durable catalog/publication concern.

This note should be read as a narrower successor for the lifecycle / asset part of that tree. It does not try to solve policy/theory, but it keeps the same principle: public namespace should describe the domain model, not implementation storage.

### 3.2 Read/write/assertion note

`docs/references/working/design-points/read-write-snapshot-assertion-selection.zh.md` established that FactGraph is not table CRUD. `read`, `write`, `assertions`, and `views` expose assertion-aware graph semantics.

This matters because lifecycle design must not accidentally reframe assertions as generic rows. `fg.schema.*` and `fg.rules.*` can evolve without changing:

- `fg.read.*`
- `fg.write.*`
- `fg.assertions.*`
- `fg.views.*`
- `AssertionRecordSet`
- `EntitySnapshot.field(...)`
- `snapshot.assertions.<field>`
- `ReadPolicy`

### 3.3 Post-Track-3 semantics API note

`docs/references/working/design-points/post-track3-semantics-public-api.zh.md` turned `fg.rules.inspect(rule)` into current behavior through Track 1.

This means `fg.rules.*` is no longer only aspirational. It already exists as a namespace for rule/derivation structure inspection. The next question is whether durable rule and derivation asset lifecycle belongs there too.

### 3.4 Rule / policy / function-tree naming risk

`docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md` explicitly flagged a naming risk: `Derivation` can be confused with proof derivation, and product-level aliases such as `Inference` or `Materialization` may be clearer.

Blueprint 1 adopts that concern for the public SDK. The candidate/materialization producer is now public `Inference`: `where + head -> CandidateSet[]`. It is not the proof trace itself. Internal proof/audit vocabulary can continue to use derivation where it means "how something was derived."

## 4. Design Thesis

This note proposes the following working thesis for a future blueprint:

1. **`FactGraph` owns lifecycle.**
   Normal users should think in terms of creating, loading, saving, and operating a graph workspace.

2. **Registry is a mechanism, not necessarily an advanced public API.**
   The registry substrate may remain internally, but `SDKRegistry` does not have to remain importable or documented as public. The canonical user path should be `FactGraph.load/save` and domain namespaces.

3. **Rule / Inference / Query are authoring assets, not mandatory registry records.**
   They remain value objects for direct runtime use. Saving them is optional.

4. **Domain namespaces should own durable asset operations.**
   Prefer:
   - `fg.rules.save/load/list/inspect`
   - `fg.inferences.save/load/list`
   - future `fg.queries.save/load/list` only after query persistence exists

   over:
   - `fg.registry.register_rule`
   - `fg.registry.register_inference`

5. **Schema mutation should be explicit and conservative.**
   `schema.add`, `schema.delete`, and `schema.update` sound simple, but schema evolution affects ledger compatibility, identity semantics, migrations, registry manifests, and provenance. First implementation should likely avoid destructive delete.

6. **Evidence carriers should stay internal, with `fg.explain.*` as the likely user surface.**
   Evidence capability is important, but it should not be folded into rules/registry by accident. The earlier function-tree note recommends keeping `SupportArtifact`, `ProvenanceEnvelope`, `EvidenceGraph`, candidate evidence trees, and rule trace artifacts internally distinct while routing user-facing proof explanation through `fg.explain.*`. This note adopts that direction as design input.

7. **Assertion/read/write surfaces are invariants.**
   The lifecycle/asset redesign must not change current assertion syntax or namespace behavior.

8. **Application-layer authority should mediate persistence.**
   If domain namespaces persist authoring assets, they should call a `kernel.application` authoring runtime layer or an equivalent DTO boundary. They should not duplicate filesystem registry logic or reach directly into `FileAuthoringRegistry`.

9. **Public SDK vocabulary can differ from internal substrate vocabulary.**
   Because the product is pre-release, Blueprint 1 hard-cuts public SDK `Derivation` to `Inference` without preserving a public alias. Internal application/authoring/service names may continue to use `derivation_*` until a dedicated wire/registry rename slice cuts them.

## 5. Proposed Conceptual Tree

Working target:

```text
FactGraph
├── create(...)                         # new public lifecycle entrypoint
├── load(...)                           # graph workspace load
├── save(...)                           # graph workspace save
├── from_schema_classes(...)            # existing class-first constructor; public fate TBD
├── batch(...)                          # unchanged
├── schema
│   ├── describe(...)                    # current / future schema inspection
│   ├── add(...)                         # additive schema extension candidate
│   ├── deprecate(...)                   # safer than hard delete
│   ├── update(...) / migrate(...)        # migration-plan based, future
│   ├── ingest(...)                      # existing taxonomy placement
│   └── validate_provenance(...)         # existing taxonomy placement
├── rules
│   ├── inspect(...)                     # current Track 1 behavior
│   ├── save(...) / create(...)           # durable rule asset candidate; verb TBD
│   ├── load(...) / get(...)              # retrieval verb TBD
│   ├── list(...)
│   └── refs / metadata shape TBD         # RuleRef / manifest return contract
├── inferences                           # public SDK replacement for Derivation
│   ├── inspect(...)                      # future if split from rules.inspect
│   ├── save(...) / create(...)           # durable inference asset candidate; verb TBD
│   ├── load(...) / get(...)
│   └── list(...)
├── derivations                          # internal/wire vocabulary only until renamed
│   └── not a preferred public SDK namespace
├── queries                              # future conceptual namespace only
│   └── save/load/list are NOT exposed until query persistence exists
├── read                                # unchanged
├── write                               # unchanged
├── assertions                          # unchanged
├── views                               # unchanged
├── eval                                # mostly unchanged
├── what_if                             # unchanged for now
├── explain                             # future unified live proof explanation surface
│   ├── evidence(candidate | support_digest)
│   ├── graph(candidate | support_digest)
│   └── narrative(candidate | support_digest)
├── audit
│   ├── explain_fact(...)                # current; may migrate/alias into explain
│   ├── conflicts(...)                   # current
│   └── diff_proof_frames(...)           # persisted/offline/cross-round review
└── package                             # unchanged export/run package story
```

As of Blueprint 2, the `rules.save/load/list/get` and
`inferences.save/load/list/get` portions of this tree are current behavior.
Workspace lifecycle, schema mutation, query persistence, and explain/evidence
remain future-scope.

## 6. Architectural Layer And Verb Reality

### 6.1 Avoid SDK shell over SDK shell

If this design ships durable asset facades, the implementation should avoid:

```text
_SDKRulesManager.save()
  -> SDKRegistry.register_rule()
      -> FileAuthoringRegistry.write(...)
```

That shape turns one SDK shell into a wrapper over another SDK shell. It also makes `SDKRegistry` the hidden authority while the docs say it is merely the backing mechanism.

Landed Blueprint 2 shape:

```text
_SDKRulesManager.save()
  -> kernel.application.authoring_runtime.save_rule(...)
      -> FileAuthoringRegistry / AuthoringRegistry protocol

SDKRegistry.register_rule()
  -> kernel.application.authoring_runtime.save_rule(...)
      -> FileAuthoringRegistry / AuthoringRegistry protocol
```

The application module is `kernel.application.authoring_runtime`. Domain managers call it directly. Any surviving advanced `SDKRegistry` use remains a separate wrapper over lower-level registry mechanics; it is no longer the public SDK authority.

If the future blueprint deletes `SDKRegistry` from the public SDK, this still holds internally during migration: the old registry wrapper should either disappear or become a thin internal client of the application-layer function, not remain as an alternate authority.

This mirrors the broader project pattern: SDK objects are ergonomic shells; application modules own runtime/protocol orchestration; core/authoring modules own substrate mechanics.

### 6.2 Verb family is a real design decision

The first draft used `save/load/list` for rules and derivations because it matches user intent. Code review adds a counterweight: existing SDK managers do not use that pair today.

Viable verb families:

| Family | Example | Pros | Cons |
|---|---|---|---|
| Save/load | `fg.rules.save(rule)`, `fg.rules.load("id")` | Natural for durable assets; aligns with `FactGraph.save/load` if that ships | New manager verb pattern; collides conceptually with `_SDKBatchTx.save(...)` |
| Create/get/list | `fg.rules.create(rule)`, `fg.rules.get("id")` | Matches `views.create/get/list` precedent | "create" feels less natural for saving an existing value object |
| Register/read/list | `fg.rules.register(rule)`, `fg.rules.read("id")` | Honest about registry mechanics | Reintroduces registry language into domain namespace |

This note still leans `save/load/list` for authoring assets, but future G0 must explicitly lock it and document how it differs from batch transaction `save`.

### 6.3 FactGraph-level save vs batch transaction save

If `fg.save(...)` ships, it must be clear that:

```python
fg.save("./workspace")
```

means graph/workspace persistence, while:

```python
with fg.batch() as tx:
    tx.save(obj)
```

means adding/staging an object inside a batch transaction.

This naming collision is acceptable only if docs and error messages make the receiver object obvious:

- `FactGraph.save(...)`: graph lifecycle.
- `BatchTx.save(...)`: batch commit/staging helper.

If that distinction feels too subtle, future G0 should consider alternative graph-level names such as `persist(...)`, `snapshot(...)`, or `write_workspace(...)`. This note does not recommend renaming yet; it records the collision as a load-bearing design constraint.

## 7. Lifecycle API Candidates

### 7.1 `FactGraph.create(...)`

Candidate shape:

```python
fg = FactGraph.create(
    schema_classes=[User, Document],
    path="./workspace",
)
```

Possible arguments:

- `schema_classes`: class-first creation, matching current implementation.
- `path`: optional graph workspace root.
- `ledger_path`: explicit ledger location, if workspace path is not enough.
- `artifact_store_root`: existing file artifact sidecar concept.
- `default_row_format`: current constructor option.

Existing constructor:

```python
FactGraph.from_schema_classes([...])
```

can remain as an explicit class-first constructor, but it is not protected by release compatibility. A later blueprint may choose either:

- additive path: keep it as an explicit lower-level constructor;
- hard-cut path: make `create(...)` the only public constructor and move `from_schema_classes(...)` internal.

The minimal implementation path is still:

```python
FactGraph.create(schema_classes=[...])
```

implemented as a clearer wrapper over the existing `from_schema_classes(...)` code path.

Open design point: whether `FactGraph.create([User, Document])` should allow positional classes, or require `schema_classes=` for readability.

### 7.2 `FactGraph.load(...)`

Current conservative shape:

```python
fg = FactGraph.load(
    "./workspace",
    schema_classes=[User, Document],
)
```

Why still require `schema_classes` in the first slice:

- Current `SDKStore` needs Python `Entity` classes to build typed SDK behavior.
- Ledger metadata currently records `schema_digest`, not enough to reconstruct Python classes.
- Registry schema IR can help compile saved rules/inferences, but it does not reconstruct typed Python entity classes by itself.
- Class-less load would require a dynamic entity facade or generated classes, which is a separate design.

Deferred richer shape:

```python
fg = FactGraph.load("./workspace")  # dynamic schema mode
```

This should be deferred until dynamic class-less FactGraph behavior is deliberately designed.

### 7.3 `fg.save(...)`

Candidate shape:

```python
fg.save()
fg.save("./workspace")
```

The core design question is save scope:

1. ledger only;
2. ledger + schema digest;
3. ledger + schema IR;
4. ledger + schema IR + registry manifest/rules/inferences;
5. full graph workspace: ledger + schema + registry + artifacts + views + package metadata.

This note recommends using "FactGraph workspace" for the larger concept, but not implementing the largest form until file layout is explicitly locked.

First save/load blueprint should probably choose between:

- **Level 3:** ledger + schema IR;
- **Level 4:** ledger + schema IR + registry manifest/rules/inferences.

Including artifacts, views, and audit/evidence round files is a larger workspace design and should not happen by accident.

### 7.4 `FactGraph.save(fg)` vs `fg.save(...)`

Python users will expect instance method first:

```python
fg.save("./workspace")
```

A class/static helper:

```python
FactGraph.save(fg, "./workspace")
```

is less idiomatic and probably unnecessary unless the project wants a pure functional persistence API. This note recommends instance method as the primary shape, while acknowledging the batch-transaction `save` collision described in §6.3.

## 8. Schema Evolution Candidates

The user-facing request includes:

```python
fg.schema.add(...)
fg.schema.delete(...)
fg.schema.update(...)
```

The names are intuitive, but their semantics are not equal.

### 8.1 `fg.schema.add(...)`

Safest candidate.

Potential meaning:

- Add new entity class.
- Add new field to an existing entity.
- Add new relation.

Risks:

- schema digest changes;
- existing ledger rows need compatibility validation;
- registry schema entry needs versioning;
- field defaults / nullable semantics may be required.

First slice could support only additive preflight / draft schema update, not mutation-in-place.

### 8.2 `fg.schema.delete(...)`

High risk.

Hard delete of schema components can orphan:

- ledger assertions;
- views;
- rules;
- derivations;
- proof frames / round evidence;
- registry versions.

This note recommends using `deprecate(...)` before `delete(...)`:

```python
fg.schema.deprecate(User.old_field)
```

Hard delete should require a migration plan and explicit destructive confirmation if it ever ships.

Important substrate cost: even `deprecate(...)` is not just a naming change. It likely requires durable schema metadata, registry manifest representation, docs, and compatibility checks. It should therefore be scoped as schema-evolution work, not as a small lifecycle facade add-on.

### 8.3 `fg.schema.update(...)` / `fg.schema.migrate(...)`

Likely needs a migration object:

```python
plan = fg.schema.plan_update([...])
fg.schema.apply_migration(plan)
```

This is probably too large for the first lifecycle slice. It is important to design the name now so `add/delete/update` do not trap future behavior into unsafe shortcuts.

## 9. Authoring Assets: Rules, Inferences, Queries

### 9.1 Keep value-object runtime use

This must remain valid:

```python
rule = Rule(...)
fg.eval.run(rule)

inf = Inference(...)
fg.eval.evaluate(inf, semantics=PyReasonSemantics(...))
```

Saving should not be required for evaluation.

Benefits:

- fast interactive use;
- notebooks stay lightweight;
- tests remain simple;
- no registry setup for local reasoning.

### 9.2 Add optional durable asset lifecycle

Candidate shape:

```python
fg.rules.save(rule)
fg.rules.list()
fg.rules.load("rule_id")

fg.inferences.save(inf)
fg.inferences.list()
fg.inferences.load("inference_id")
```

This can reuse the existing `SDKRegistry.register_rule(...)` and `SDKRegistry.register_inference(...)` implementation knowledge, because those methods already accept SDK objects and compile them. It should not be treated as a reason to preserve `SDKRegistry` as public API.

The public naming difference is important:

- `register_*` describes registry mechanics.
- `save/load/list` describes user intent.
- `Inference` describes the SDK value object that proposes inferred facts; `Derivation` remains available as internal/proof/wire vocabulary until renamed.

But the verb family remains a future G0 decision because current managers use `create/update/delete/get/list` or domain verbs, not `save/load`.

### 9.3 Query asset lifecycle

`Query` is currently part of the SDK DSL and runtime query stack, but not part of `SDKRegistry` persistence in the same way rules/inferences are.

The current runtime query id is generated from lowered query shape and schema context. It is useful for execution determinism, but it is not the same as a user-managed saved query id. A future query asset design therefore needs to decide whether query identity is explicit, versioned, digest-derived, or some combination.

This should not be interpreted as a final architecture decision. A future design may eventually consider:

```python
fg.queries.save(query)
fg.queries.load("query_id")
fg.queries.list()
```

But this likely requires new authoring payload / registry support. Therefore:

- mention `queries` in conceptual diagrams as future direction;
- do **not** expose a real `fg.queries` attribute until persistence exists;
- do **not** ship `fg.queries.*` methods that always raise `NotImplementedError`;
- defer query persistence implementation unless a source audit proves it is already cheap.

This follows the narrow-public-API principle: do not expand reflective SDK surface only for conceptual symmetry.

### 9.4 Why not public `fg.registry.register_rule(...)`?

Possible but not recommended as the main public path.

Reasons:

1. It exposes storage mechanism instead of domain concept.
2. It makes rules/inferences feel mandatory-registered even though direct runtime value-object use is valid.
3. It does not naturally answer where queries belong.
4. It creates a parallel public model next to `fg.rules.inspect(...)`.

Landed split:

- normal users: `fg.rules.*` and `fg.inferences.*`; future `fg.queries.*`
  only once real query persistence exists;
- backend implementation: registry substrate remains behind the domain facades;
- optional migration/debug surface: `kernel.sdk.registry.SDKRegistry` remains
  importable, but it is removed from `kernel.sdk.__all__`.

### 9.5 Return references are part of the public contract

Blueprint 2 locked saved refs as public load handles:

```python
rule_ref = fg.rules.save(rule)  # SavedRuleRef(rule_id, version)
inf_ref = fg.inferences.save(inf)  # SavedInferenceRef(inference_id, version)
```

`RuleRef` stays a where-clause carrier and is intentionally not reused as a
saved-asset handle. `SavedRuleRef` / `SavedInferenceRef` are load handles, not
runtime selectors; users load them before `run(...)` / `evaluate(...)`.

## 10. Explain / Evidence / Audit Placement

Evidence capability should be designed, but not inside the first lifecycle slice.

Reasons:

- Evidence relates to runtime rounds, proof frames, provenance, and auditability.
- Registry relates to authoring assets and their versions.
- Save/load relates to graph workspace persistence.

These overlap in a full system package, but they are not the same concept.

The earlier function-tree design note made a useful distinction that this note should preserve:

- `explain` owns current/live proof explanation.
- `audit` owns persisted/offline/cross-round review.
- internal evidence carriers remain distinct and do not need to collapse into one storage type.

Current carriers include `SupportArtifact`, `ProvenanceEnvelope`, `EvidenceGraph`, candidate evidence trees, and `RuleTraceArtifact`. They can remain implementation-specific. The user-facing shape should likely be a unified explanation namespace:

```python
fg.explain.evidence(candidate_or_support_digest)
fg.explain.graph(candidate_or_support_digest)
fg.explain.narrative(candidate_or_support_digest)
```

Existing current surfaces such as:

```python
fg.audit.explain_fact(...)
fg.audit.conflicts(...)
fg.audit.diff_proof_frames(...)
```

should be interpreted as today's implementation placement, not the final product taxonomy. `diff_proof_frames` belongs naturally under `audit` because it consumes persisted round events. `explain_fact` and proof-support surfaces may eventually move or alias into `fg.explain.*` if an explanation blueprint lands.

Blueprint 1 through Blueprint 3 should not migrate `fg.audit.explain_fact(...)` or other current audit/proof helpers into `fg.explain.*`. That placement stays current until a dedicated explain blueprint scopes the migration.

This should be a dedicated explain/evidence blueprint. The lifecycle design should only reserve space and avoid naming collisions.

When that explain blueprint happens, scope-freeze should lock the output contracts separately:

- `fg.explain.evidence(...)`: raw/structured evidence carrier view;
- `fg.explain.graph(...)`: proof/support graph view;
- `fg.explain.narrative(...)`: human-readable explanation text.

Round events already have a separate file-backed persistence layer. That reinforces the boundary: explain/evidence/audit persistence is not automatically included in ledger save, registry save, or package export.

## 11. Invariants / Non-Goals

Any future blueprint based on this note should preserve these boundaries unless it explicitly scopes a larger migration.

### 11.1 Assertion surface unchanged

Do not change:

- `fg.read.*`
- `fg.write.*`
- `fg.assertions.*`
- `fg.views.*`
- `AssertionRecordSet`
- `EntitySnapshot.field(...)`
- `snapshot.assertions.<field>`
- `ReadPolicy`

Lifecycle and authoring asset work should not alter assertion syntax.

### 11.2 Runtime direct use unchanged

Do not require saved assets for:

```python
fg.eval.run(rule)
fg.eval.evaluate(deriv)
fg.what_if.check(...)
```

Registered references can be supported, but value objects remain first-class.

### 11.3 SemanticsProfile / `*Semantics` unchanged

This note does not change:

- `ProbLogSemantics`
- `PyReasonSemantics`
- `SemanticsProfile`
- `fg.eval.inspect_semantics(...)`
- engine auto-derivation
- PyReason branch bounds
- `condition_weights` as a Rule template certainty/explain input

Those were completed in Track 3 + post-Track-3 plan.

If rules are saved and loaded, Track 3-era fields such as `condition_weights` must round-trip exactly through authoring payload / registry / load paths.

### 11.4 Public/internal vocabulary split

Blueprint 1 lands the public/internal vocabulary split for the candidate-producing value object:

- public SDK: `Inference`; future persistence slices may add `fg.inferences.*` and `InferenceRef` only when they carry real behavior;
- internal/application/authoring/service substrate: existing `derivation_*` names may remain until a dedicated wire/registry rename slice;
- proof/audit docs: avoid using bare `Derivation` as a concept heading; prefer `Proof`, `Proof Trace`, or `Support Trace` for "how a result was derived."

This creates a temporary two-vocabulary period. It is an explicit cost, not an implementation detail. Future blueprint sequencing should account for it.

### 11.5 Package export remains distinct

`fg.package.export_package(...)` and `fg.package.run_package(...)` are not automatically replaced by `fg.save/load`.

Possible future distinction:

- `save/load`: workspace persistence for continued editing/running;
- `package`: portable artifact for distribution / reproduction / deployment.

This distinction should be locked before implementation.

### 11.6 Verb collision preserved

Existing `_SDKBatchTx.save(...)` keeps its batch transaction meaning. Any future `FactGraph.save(...)` must be documented as graph/workspace persistence and must not alter batch transaction behavior.

### 11.7 `RuleRef` substitutability

A rule saved through future `fg.rules.save(rule)` should resolve by reference using the same semantic model as today's registry-backed `RuleRef(...)` path. If `SDKRegistry.register_rule(rule)` is retained temporarily, both paths should be equivalent. If `SDKRegistry` is deleted from public SDK, tests should still verify that the new facade preserves the old runtime reference behavior before the old surface is removed.

### 11.8 Registry-as-mechanism boundary

Domain namespace managers should not write files directly. They should call an application-layer authoring runtime or another shared DTO boundary. Any surviving `SDKRegistry` wrapper and `fg.rules.*` should converge on the same backend behavior; if `SDKRegistry` is removed, the application-layer function becomes the only orchestration path.

### 11.9 View persistence boundary

`fg.views` is currently a manager with `create/update/delete/get/list`, but it is not clearly part of registry/package persistence. A future `fg.save(...)` must explicitly include or exclude views. It should not silently change view lifetime.

## 12. Open Questions For A Future G0

### 12.1 Scope-freeze blockers

These must be answered before a concrete implementation blueprint is scoped:

1. What does `fg.save(...)` save: ledger only, registry only, or full workspace?
2. Does `FactGraph.load(...)` require Python schema classes in the first slice?
3. Should saved graph workspaces include views?
4. Should saved graph workspaces include artifact sidecars?
5. Should saved graph workspaces include audit/evidence round events, or is that a separate package/export mode?
6. Should `fg.rules.save(rule)` return a `RuleRef`, a manifest entry dict, or the original `Rule` with metadata?
7. Should `fg.inferences.save(inf)` introduce a new `InferenceRef`, return a manifest entry dict, or use another reference shape?
8. Does query persistence belong in the same slice, or should `fg.queries.*` remain design-only until authoring registry supports it?
9. Which implementation path owns persistence orchestration: direct `SDKRegistry`, direct `FileAuthoringRegistry`, or an application-layer authoring runtime?
10. Blueprint 1 hard-cuts public SDK `Derivation` to `Inference` and updates SDK docs in the same slice; remaining question is when substrate/wire vocabulary follows.
11. If public SDK uses `Inference`, when does service/registry wire vocabulary rename from `derivation` to `inference`?
12. If query persistence is ever added, what is the saved query identity model: explicit id/version, digest-derived id, or both?

### 12.2 Important but negotiable G0 questions

1. Should `FactGraph.create(...)` be purely additive, or should docs gradually make it canonical over `from_schema_classes(...)`?
2. Should `FactGraph.create(...)` accept `schema_classes` only, or also `schema_ir` / registry roots?
3. What is the exact graph workspace directory layout?
4. Should `SDKRegistry` be removed from `kernel.sdk.__all__` once `fg.rules/inferences.*` exists?
5. If any registry wrapper remains, is it internal-only, advanced-only, or test-only?
6. Should normal docs delete direct `SDKRegistry` teaching after `fg.rules.save/load` exists?
7. Should `fg.schema.add(...)` mutate immediately, or produce a migration plan?
8. Should schema deletion be exposed as `delete`, `remove`, `drop`, or only `deprecate` in the public SDK?
9. How does schema evolution interact with `schema_digest` already stored on ledgers?
10. How should `RuleRef(...)` bind to a default registry when a `FactGraph` has a workspace?
11. Should `fg.eval.run("rule_id")` be allowed as shorthand, or should references stay explicit?
12. How should workspace save/load interact with existing `ledger_path`?
13. Is there a user-facing distinction between `fg.schema.describe()` and current `fg.schema_ir`?
14. Should public method parameter names use `inference` instead of `derivation` even when internal helpers still lower to compiled derivation plans?

## 13. Recommended Blueprint Sequence

The original first-cut idea was too large if interpreted as one implementation slice. A safer sequence is:

### 13.1 Blueprint 1 — Public Inference naming + FactGraph asset inspection parity

Small-to-medium, SDK/docs-focused, no persistence.

Candidate scope:

1. Add `FactGraph.create(schema_classes=..., ledger_path=..., artifact_store_root=...)` as an additive classmethod wrapper over `from_schema_classes(...)`.
2. Hard-cut public SDK value-object name from `Derivation` to `Inference`.
3. Rename public method parameter names from `derivation` to `inference` where public SDK signatures expose them.
4. Add `fg.inferences.*` only if it has real functionality; do not create an empty namespace for symmetry.
5. Add `_SDKInferencesManager.inspect(...)` only if `fg.rules.inspect(rule_or_inference)` is not sufficient. Current Track 1 behavior may make this docs-only.
6. Decide whether query structural inspection belongs under a future namespace, but do not expose `fg.queries` unless there is real functionality.
7. Update SDK README, user guide, API surface, and rules/inferences docs in the same slice. Public docs should not lag behind code on the rename.

Non-goals:

- `FactGraph.load(...)`;
- `fg.save(...)`;
- `fg.rules.save/load/list`;
- `fg.inferences.save/load/list`;
- service route / payload rename from `/derivations/*` to `/inferences/*`
  (landed in the wire/registry vocabulary slice);
- registry filesystem path rename from `derivations/` to `inferences/`
  (landed in the wire/registry vocabulary slice);
- schema mutation;
- explain/evidence capability.

Recommended follow-up ordering: Blueprint 1 hard-cut public SDK to
`Inference`, and the dedicated wire/registry rename slice landed before the
persistence facade. Blueprint 2 can now start from a public inference
vocabulary instead of a mixed "public Inference + persistent derivation
registry" model.

### 13.2 Blueprint 2 — Authoring asset persistence facade

Medium-sized, application-layer first. **Landed in Blueprint 2.**

Landed scope:

1. Added `kernel.application.authoring_runtime` with registry-facing
   save/load/list/get helpers.
2. Added `registry_root=` and `registry=` attachment paths to `FactGraph` /
   `SDKStore`.
3. Added `fg.rules.save/load/list/get` over the application functions.
4. Added `fg.inferences.save/load/list/get` parity.
5. Removed `SDKRegistry` from public `kernel.sdk` exports/docs; advanced code
   can still import `kernel.sdk.registry.SDKRegistry`.
6. Locked return types as `SavedRuleRef` and `SavedInferenceRef` so they do not
   collide with `RuleRef` where-clause semantics.
7. Kept saved refs as load handles only. Runtime shorthand such as
   `fg.eval.run(saved_ref)` remains future ergonomic scope.
8. Auto-upserts registry schema on first save, is idempotent under matching
   `schema_digest`, and raises on mismatch.

Non-goals preserved by Blueprint 2 at the time:

- graph workspace `save/load` (landed later in Blueprint 3);
- class-less load;
- query persistence;
- schema mutation;
- explain/evidence capability.

### 13.3 Blueprint 3 — FactGraph workspace lifecycle

Blueprint 3 landed the workspace-layout slice.

Landed scope:

1. Locked compact workspace layout:
   - `factgraph_workspace.json`
   - `ledger.db`
   - `registry/`
2. Locked save scope as Level 4: ledger + schema IR + registry manifest/rules/inferences.
3. Added `fg.save(path=None)`, with no-arg save requiring a bound workspace
   path and `fg.save(path)` rebinding the graph.
4. Added `FactGraph.load(path, schema_classes=[...])`, requiring Python
   schema classes and validating manifest / ledger / registry / provided-class
   schema digests.
5. Added `kernel.application.workspace_runtime` as the application-layer
   layout/manifest/ledger-copy/registry-sync authority.
6. Documented workspace save/load as distinct from `fg.package.export_package(...)`.

Non-goals:

- class-less dynamic entity facade;
- destructive schema delete;
- full schema migration engine;
- explain/evidence/round archive unless explicitly scoped;
- query registry persistence unless Blueprint 2 already added it.

### 13.4 Inserted slice — Service and registry vocabulary rename

Blueprint 1 shipped public `Inference`. The follow-up wire/registry slice then
hard-cut the remaining public service and registry vocabulary before Blueprint
2, avoiding a longer mixed "public Inference + persistent derivation registry"
period.

Landed scope:

1. Service runtime routes are `/inferences/evaluate` and
   `/inferences/accept`; `/derivations/*` routes are no longer public.
2. Service runtime request payloads use top-level `"inference"` where they
   represent the public candidate-producing object.
3. Runtime evaluation response envelopes use `evaluation.inference_id`.
   Nested candidate payloads intentionally retain `derivation_id` /
   `derivation_version` until a future candidate/proof protocol cleanup.
4. Registry public asset language uses inference: route
   `/v1/registry/inferences/read`, request key `inference_id`, response key
   `inference_spec`, manifest key `inferences`, and filesystem path
   `inferences/{id}/{version}.json`.
5. Registry spec JSON uses `inference_id`. Compiler-facing payloads still use
   `derivation_id`; `FileAuthoringRegistry` translates at the storage
   boundary.
6. Internal application protocol names such as `CompiledDerivationPlan`,
   `DerivationEvaluateRequest`, and provenance standard `derivation_v1`
   remain substrate vocabulary.
7. Service docs, registry docs, SDK registry docs, and authoring docs were
   updated in the same slice.

Non-goals:

- persistence facade;
- workspace save/load;
- proof/audit "derivation" terminology cleanup unless directly user-facing.

### 13.5 Future independent blueprints

After the lifecycle sequence, these should be independent:

- schema add/deprecate/migrate;
- query persistence;
- explain/evidence/audit capability;
- package/workspace convergence;
- class-less dynamic FactGraph load.
- proof/audit doc vocabulary cleanup from bare `Derivation` to `Proof Trace` / `Support Trace` where appropriate.

## 14. Working Recommendation

The lifecycle/assets direction has now shipped through Blueprint 1, the
service/registry vocabulary slice, Blueprint 2, and Blueprint 3. Future work
should treat the current public model as:

- `FactGraph.create(...)`, `FactGraph.load(...)`, and `fg.save(...)` own graph
  lifecycle;
- `fg.rules.*` and `fg.inferences.*` own authoring asset persistence;
- `kernel.sdk.registry.SDKRegistry` and `FactGraph.from_schema_classes(...)`
  remain advanced/lower-level scaffolding, not the normal teaching path.

Because the product is not released, future blueprints should still prefer a
clean public model over compatibility preservation when expanding adjacent
surfaces.

Lifecycle/assets sequence state after Blueprint 3:

1. Public `Inference` naming is landed.
2. Service/registry wire vocabulary is landed.
3. Graph-bound authoring asset persistence facade is landed.
4. Graph workspace save/load is landed with compact Level 4 layout.
5. Preserve all assertion and runtime direct-use surfaces as hard invariants.
6. Revisit schema mutation, query persistence, and explain/evidence capability as separate slices.

The high-level shape is:

```text
FactGraph owns lifecycle.
Domain namespaces own authoring assets.
Registry remains the backing mechanism.
Application runtime owns persistence orchestration.
Public SDK uses Inference; derivation remains internal/proof/candidate substrate vocabulary.
Assertion/runtime surfaces remain stable.
Explain is the likely user-facing proof surface; evidence carriers remain internal and are not mixed into this slice.
```
