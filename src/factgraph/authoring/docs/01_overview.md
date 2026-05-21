# Authoring module overview (factgraph)

- Scope: `src/factgraph/authoring`
- Last updated: 2026-03-29
- Audience: developers who need to understand schema / rule /
  inference preflight, publish, and registry workflows

## 1. Module responsibilities

`authoring` is the **authoring / control plane**. It turns DSL,
DTOs, and Python objects into asset versions that can be
prechecked, published, and persisted.

It primarily handles:

- schema preflight / compile
- rule preflight / compile
- inference preview / compile
- schema-aware lowering of inference `head` syntax to canonical IR
- authoring diagnostics and DTOs
- registry file read/write
- publish / apply / session workflow

It does not handle:

- runtime fact persistence
- `Store` / `Ledger` queries and materialized execution
- HTTP / BFF routes

## 2. Recommended public entry points

`authoring` has completed its first consolidation phase. New code
should enter from the following grouped modules:

- `factgraph.authoring.schemas`
  - `schema_preflight(...)`
  - `compile_authoring_schema_v1(...)`
  - `parse_authoring_schema_dsl_v1(...)`
- `factgraph.authoring.rules`
  - `rule_preflight(...)`
  - `compile_authoring_rule_v1(...)`
  - `parse_authoring_rule_dsl_v1(...)`
- `factgraph.authoring.derivations`
  - `derivation_dry_run_preview(...)`
  - `compile_authoring_derivation_v1(...)`
  - `parse_authoring_derivation_dsl_v1(...)`
- `factgraph.authoring.workflow`
  - dry-run and publish DTO helpers that do not write filesystem registry
    state

`factgraph.authoring.__init__` already aggregates these public entry
points. The older leaf modules still exist but are better treated as
implementation detail or compatibility paths than as new dependency
entry points.

## 3. Declarative metadata contract (current implementation)

For the "managerial" declarative metadata of schema / rule /
derivation, authoring currently converges to the following
boundaries:

- schema / derivation:
  - `version`
  - `description`
  - `tags`
- rule:
  - `version`
  - `description`
  - `tags`
  - `condition_weights`

Boundary constraints:

- `Entity`
  - `entity_type` comes directly from the class name; no separate
    `schema_id` is declared
  - In the schema DSL, `class Meta:` provides
    `version / description / tags`
  - `Meta.description` takes precedence; the class docstring is used
    only as a fallback when `description` is not provided
  - `Meta` is not an open dictionary; any other key raises an error
    during parse / SDK declaration
- `Rule`
  - `description`, `tags`, `condition_weights` are passed through
    `Rule(...)` top-level parameters or through top-level keys of
    the authoring payload
  - `condition_weights` is version-scoped certainty/explain projection
    input, keyed by atom-position: `b{branch}.a{atom}`
  - `condition_weights` is preserved by the compiler / registry but
    does not enter `RuleSpec` or the where-evaluator execution
    surface
  - `condition_weights` is not an engine adapter parameter. Future
    runtime configuration for this lane belongs in
    `SemanticsProfile.certainty_projection`.
- `Derivation`
  - `description`, `tags` are passed through `Derivation(...)`
    top-level parameters or through top-level keys of the authoring
    payload
  - `target` remains a compatibility field; high-level declarations
    should prefer `head`

These fields are validated by the compiler and preserved in the
authoring asset, but they do not participate in `where` validation,
candidate generation, or accept semantics.

### 3.1 Schema DSL example

```python
class EmploymentEvent(Entity):
    """Used as description fallback only when Meta.description is absent."""

    class Meta:
        version = "v1"
        description = "Employment event"
        tags = ["employment", "event"]

    event_id: str = Identity(primary_key=True)
    company: str = Field(cardinality="single")
```

### 3.2 Rule / inference compiler payload examples

```python
rule_payload = {
    "rule_id": "employment_match",
    "version": "v1",
    "description": "Matches employment-related facts",
    "tags": ["employment", "query"],
    "condition_weights": {"b0.a0": 0.75},
    "select": ["$u"],
    "where": [("pred", "user:name", ["$u", "$name"])],
}

derivation_payload = {
    "derivation_id": "employment_event_from_resume",
    "version": "v1",
    "description": "Derive employment events from resume facts",
    "tags": ["employment", "derivation"],
    "head": {...},
    "where": [...],
}
```

The authoring compiler substrate still names this low-level key
`derivation_id`. Registry storage translates to public `inference_id` at the
file boundary.

## 4. Internal structure (by topic)

- `schema_compile.py`, `schema_dsl_parse.py`
  - schema DSL parsing and `SchemaIR` compilation
- `rule_compile.py`, `rule_dsl_parse.py`
  - rule DSL parsing, validation, and compilation
- `derivation_compile.py`, `derivation_dsl_parse.py`
  - derivation DSL parsing, preview, and compilation (including the
    head auto-inference path)
- `dto.py`, `diagnostic_codes.py`
  - authoring DTO structures and stable diagnostic codes
- `registry_fs.py`
  - file-backed registry backend
- `publish.py`, `apply_execute.py`, `session.py`, `workflow.py`,
  `dsl_bridge.py`
  - authoring session / publish / apply / DSL bridge workflow
- `cli.py`
  - authoring CLI entry point

## 5. Derivation v2 semantics (implementation contract)

- `head` shape determines the default path:
  - `EntityType(...)` → entity path
  - `EntityType.field(...)` → fact path
- User syntax no longer supports `materialize_as` / `id_policy`; if
  inputs include either field, compile fails immediately.
- Schema compile auto-generates a `<T>:exists` predicate for every
  `Entity`; it no longer relies on `is_record` as a behavior switch.
- The no-head form (`target + head_vars`) remains as a fact-only
  compatibility path.
- ProbLog branch probability no longer enters through authoring
  payload `body_confidences` or SDK branch-wrapper confidence:
  - public authoring payloads reject `body_confidences`
  - public authoring payloads also reject `engine_ext`
  - adapter-local extension types remain internal compiled bridges only
  - future SemanticsProfile rule projection will replace this
    transitional bridge
- `condition_weights` is the separate certainty/explain projection
  input lane. It remains accepted on public rule payloads and is not
  part of engine adapter projection; future runtime configuration for
  it belongs in `SemanticsProfile.certainty_projection`.

### 5.1 Minimal input examples (authoring payload)

Fact path (`head=Entity.field(...)`):

```python
payload = {
    "derivation_id": "drv.country_copy",
    "version": "1.0.0",
    "head": {
        "kind": "head_call",
        "callee_kind": "pred_ref",
        "entity_type": "Person",
        "field": "country_copy",
        "kwargs": {"person": "$E", "country_copy": "$C"},
    },
    "where": [("pred", "person:country", ["$E", "$C"])],
}
```

Entity path (`head=EntityType(...)`):

```python
payload = {
    "derivation_id": "drv.speaks",
    "version": "1.0.0",
    "head": {
        "kind": "head_call",
        "callee_kind": "entity_type",
        "entity_type": "Speaks",
        "kwargs": {"user": "$U", "language": "$L"},
    },
    "where": [("pred", "person:country", ["$U", "de"]), ("pred", "user:lang_pref", ["$U", "$L"])],
}
```

These examples are compiler-facing payloads, so they intentionally use
`derivation_id`. Persisted registry specs use `inference_id`.

### 5.2 Common compile errors (quick localization)

- `$.materialize_as`: the caller still passed the deprecated
  `materialize_as` field.
- `$.id_policy`: the caller still passed the deprecated `id_policy`
  field.
- `$.head`: `head` shape is invalid, or does not match a field /
  entity in the schema.
- `$.where[...]`: a where-sugar atom cannot find a corresponding
  exists / role predicate in the schema.

## 6. Registry Adapter Removal

A20(E) / Q6-A removed the filesystem authoring registry adapters:
`FileAuthoringRegistry`, `SDKRegistry`, `registry_root=`, `registry=`, and the
apply-execute write path are gone. Authoring now focuses on schema/rule/inference
DTO compilation, validation, and in-memory `Rule(...)` / `Inference(...)`
values. Legacy workspaces that still carry `registry/schema/schema_ir.json`
must be migrated explicitly:

```bash
python -m factgraph migrate-workspace <path>
```

Pre-Phase-2 workspaces may contain `registry/rules/` and
`registry/inferences/` files on disk. Those files remain inert historical data:
no runtime, SDK, service, or authoring path reads or migrates them.

## 7. Typical workflows

### 7.1 Preflight / compile

1. Provide schema / rule / inference as DSL, DTO, or object
   definitions
2. Run parse / preflight / compile through the
   `schemas / rules / derivations` grouped modules
3. Receive structured results or diagnostics

### 7.2 Registry publishing retired

Publishing to a filesystem registry is retired. Use `fg.schema.add(...)` /
`fg.save()` for schema evolution, in-memory `Rule(...)` / `Inference(...)`
values for execution, and the migration CLI for legacy workspaces.

### 7.3 Consumption by SDK / service

- `FactGraph.create(..., path=...)` binds the graph to a workspace root. The
  workspace owns `ledger.db`, `factgraph_workspace.json`, and the Database schema
  object under `db/objects/schema/<digest>.json`. Clean SDK workspaces no longer
  create or write a live `registry/` schema anchor. `FactGraph.load(path,
  schema_classes=[...])` restores the graph with explicit schema-class
  validation. Legacy `registry/schema/schema_ir.json` anchors now require the
  explicit `python -m factgraph migrate-workspace <path>` CLI. Construct
  `Rule(...)` and `Inference(...)` in memory each session.
- `factgraph.application.authoring_runtime` is now a forward-compat shell:
  Q8 Phase 2 removed the save/load/list/get orchestration; only the
  `AuthoringRuntimeError` class remains.
- `factgraph.application.workspace_runtime` owns workspace manifest validation
  and ledger backup/checkpoint behavior. Live SDK schema anchors are Database
  schema objects. It deliberately does not include artifact sidecars, in-memory
  views, audit/evidence round files, registry data, or package export output.
- `service.registry_v1` and `/v1/registry/*` routes were deleted.
- `service.runtime_v1` opens sessions from `schema_ir`; runtime rule
  registration uses in-memory ephemeral rules only.

## 8. Boundaries with other layers

- `core`
  - `authoring` calls core's `SchemaIR`, rule compilation, and
    runtime contract, but does not own runtime facts
  - Declarative metadata such as `version / description / tags` is
    validated and preserved here; core itself assigns them no
    execution semantics
- `sdk`
  - graph-bound `fg.rules.inspect(...)` is the only remaining `fg.rules.*`
    surface after Q8 Phase 2 (Slice 6); `fg.inferences.*` is an empty
    namespace. Persistence helpers were removed.
- filesystem registry adapters were removed in A20(E) / Q6-A.
- `service`
  - The service layer exposes rules validation/preview and runtime execution,
    not filesystem registry reads.
- `ecss`
  - `domains.ecss` provides shared domain presets (e.g. ECSS VCD
    predicates, Scenario A's first-round temporal / uncertainty
    predicates)
  - `authoring` can consume these presets into the schema / registry
    workflow but does not own the presets themselves
- `audit`
  - `audit` reads exported packages; it does not consume the
    authoring registry directly

## 9. Current limitations

- `authoring` solves "asset versioning" and the "preflight / publish
  workflow"; it is not the runtime execution loop.
- Rules / derivations in the registry are not yet first-class
  runtime execution entry points.
- Leaf modules remain in a compatibility window; further internal
  surface shrinkage may follow in the second consolidation phase.
