# Lifecycle / Assets Remaining Work After rc.3

- Date: 2026-05-13
- Context: `v0.1.0-rc.3` is published, but lifecycle/assets design is not fully complete.
- Current release source: `f49ccc58`
- Current release commit: `e996aa5b`

## Completed Sequence

The following lifecycle/assets slices are shipped:

1. Public `Inference` + `FactGraph.create(...)`.
2. Service / registry / wire vocabulary renamed to inference.
3. Authoring asset persistence facade:
   - `fg.rules.save/load/list/get`;
   - `fg.inferences.save/load/list/get`;
   - `SavedRuleRef` / `SavedInferenceRef`;
   - `kernel.application.authoring_runtime`.
4. FactGraph workspace lifecycle:
   - `FactGraph.create(path=...)`;
   - `fg.save(path=None)`;
   - `FactGraph.load(path, schema_classes=[...])`;
   - compact Level 4 workspace layout;
   - `kernel.application.workspace_runtime`.

## Not Complete

The design is still incomplete in several independent areas. Do not treat
rc.3 as design closure.

### 1. Schema Mutation

The next most natural design slice is schema mutation:

- `fg.schema.add(...)`;
- `fg.schema.deprecate(...)` or a safer alternative to `delete(...)`;
- `fg.schema.update(...)` / `fg.schema.migrate(...)`;
- schema digest / ledger compatibility rules;
- registry/workspace behavior when schema evolves.

This was part of the original user concern. It should start from
`docs/references/working/design-points/factgraph-lifecycle-and-assets.zh.md`,
especially the schema mutation sections, and needs a fresh blueprint before
code.

### 2. Query Persistence

Queries are still runtime value objects, not authoring assets:

- no `fg.queries` namespace;
- no `SavedQueryRef`;
- current query ids are shape-derived runtime ids, not durable authoring ids.

This is intentionally deferred because query asset identity needs its own
design. Do not add namespace parity without solving durable query identity.

### 3. Explain / Evidence Surface

Evidence carriers remain internally distinct. The likely future public surface
is `fg.explain.*`, informed by the older function-tree design note:

- `fg.explain.evidence(...)`;
- `fg.explain.graph(...)`;
- `fg.explain.narrative(...)`.

Current `fg.audit.explain_fact(...)` placement is implementation placement, not
final product taxonomy. A dedicated explain/evidence blueprint should lock the
live-vs-persisted boundary and output contracts.

### 4. Dynamic Class-Less Workspace Load

`FactGraph.load(path, schema_classes=[...])` still requires Python schema
classes. Class-less dynamic load is deferred because registry schema IR cannot
reconstruct typed SDK entity classes by itself.

### 5. Workspace Level 5

Blueprint 3 shipped Level 4 workspace save:

- ledger;
- schema IR;
- registry manifest/rules/inferences.

It does not save:

- artifact sidecars;
- views;
- audit/evidence round files;
- package metadata.

Those belong to future workspace/package convergence design, not implicit
extension of `fg.save(...)`.

### 6. Runtime Ergonomics For Saved Refs

`SavedRuleRef` and `SavedInferenceRef` are load handles, not runtime selectors.
The ergonomic shorthand below remains deferred:

```python
fg.eval.run(saved_rule_ref)
fg.eval.evaluate(saved_inference_ref)
```

Current intended flow remains:

```python
rule = fg.rules.load(saved_rule_ref)
fg.eval.run(rule)
```

### 7. `from_schema_classes(...)` Public Fate

`FactGraph.create(...)` is the canonical constructor. `from_schema_classes(...)`
remains a lower-level class-first constructor substrate. A future pre-release
cleanup may hard-cut it from public teaching or exports, but Blueprint 3 did
not do that.

## Recommended Next Task

Start a new blueprint for **schema mutation**.

Suggested working title:

```text
2026-05-13_schema-mutation-lifecycle.md
```

Recommended first pass:

1. Source audit current `fg.schema` manager, `schema_runtime`, ledger metadata,
   registry schema IR, and workspace schema digest validation.
2. Decide whether first slice is additive-only (`schema.add`) or includes
   deprecate/update/migrate vocabulary.
3. Avoid destructive `delete(...)` until ledger compatibility and migration
   semantics are locked.
4. Preserve rc.3 shipped lifecycle surface.

