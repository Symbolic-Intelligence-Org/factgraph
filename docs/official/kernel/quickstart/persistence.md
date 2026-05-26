# Save and load workspaces

The earlier pages kept most examples in memory. This page adds workspace
persistence.

There is one supported persistence path in the public SDK:

| Need | Use |
| --- | --- |
| Save graph state to disk | `fg.save()` |
| Restore graph state from disk | `FactGraph.load(path, schema_classes=[...])` |
| Migrate a pre-v0.2 workspace with `registry/` | `python -m factgraph migrate-workspace <path>` |

Rules and inferences are ordinary Python value objects. Keep them in code,
construct them when needed, and pass them directly to
`fg.eval.evaluate(...)`. The old saved-rule and saved-inference registry
handles were removed in the Slice 7C registry-final-removal work.

## Create a path-backed graph

Pass `path=` to `FactGraph.create(...)` when you want the graph to know where
its workspace should live.

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from factgraph.sdk import (
    Branch,
    Entity,
    FactGraph,
    Field,
    Identity,
    Inference,
    Pred,
    Rule,
    build_application_rule,
    vars,
)


tmp = TemporaryDirectory()
workspace = Path(tmp.name) / "tutorial-workspace"


class User(Entity):
    user_id: str = Identity(primary_key=True)
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User], path=workspace)

alice = fg.read.ref(User, user_id="u-1")
fg.write.set(User.tag_seed, alice, "engineer")
```

Because `path=` is set, `fg.save()` can later write the workspace without
another path argument.

## Use rules and inferences in memory

Define rules and inferences as values in Python code:

```python
with vars("u", "tag") as (u, tag):
    seeded_tags = build_application_rule(
        id="user:tag",
        version="v1",
        where=[User(u), User(u).tag_seed == tag],
        ports={"user": u, "tag": tag},
    )

rule_result = fg.eval.evaluate(seeded_tags, head=seeded_tags)

assert rule_result.count() == 1
assert rule_result.first().claim.name == "user:tag"
```

Inferences work the same way:

```python
with vars("u", "tag") as (u, tag):
    tags_from_seed = Inference(
        id="inf.tags_from_seed",
        version="v1",
        where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
        target="user:tag",
        head_vars=[u, tag],
    )

result = fg.eval.evaluate(tags_from_seed)

assert result.count() == 1
row = result.first()
assert row is not None
assert row.claim.name == "user:tag"
```

Evaluation is read-only. Persist facts with explicit writes:

```python
fg.write.add(User.tag, alice, "engineer")

assert tuple(fg.read.get(User, user_id="u-1").tag) == ("engineer",)
```

The rule and inference definitions themselves are not stored in the workspace.
Keep them in source files, packages, or application configuration.

## Save the workspace

Call `fg.save()` to persist the workspace:

```python
save_result = fg.save()

assert Path(save_result["path"]) == workspace
assert (workspace / "factgraph_workspace.json").exists()
assert (workspace / "ledger.db").exists()
assert (workspace / "db" / "objects" / "schema").is_dir()
assert not (workspace / "registry").exists()
```

The workspace is a level-4 graph snapshot:

- workspace manifest (`factgraph_workspace.json`)
- ledger database (`ledger.db`)
- Database-owned schema object under `db/objects/schema/<digest>.json`

Artifact sidecars, in-memory views, audit reports, service state, package
exports, rules, and inferences are not part of this workspace format.

Durable Database views are a separate Database feature. Create them with
`db.create_view(...)` on a `Database`, then consume them with
`FactGraph.attach(db, schema_classes=[...], view=view)`. A view-attached runtime
is read-only and automatically scopes `fg.read.*` and `fg.eval.evaluate(...)` to
the view's assertion ids. Session-local `fg.views.create(...)` entries do not
carry Database anchors and cannot be passed to `FactGraph.attach(...)`.

See [Database and durable views](database.md) for the full Database identity
boundary, `Database.create/open/head/commit_assertions`, durable view object
shape (`name`, `db_id`, `base_tx_id`, `schema_digest`, `asrt_ids`, `view_digest`),
and the view-scoped attach pattern.

The two boundaries serve different concerns: **`FactGraph` is the runtime
layer** (per-session reads, writes, evaluation, evidence helpers) while
**`Database` is the only persistent write point** (durable identity,
content-addressed transactions, durable views). Workspace persistence
covered on this page (`fg.save(...)` / `FactGraph.load(...)`) is the
high-level path that wraps a Database underneath; the database.md tutorial
exposes the lower boundary directly when you need it.

## Load the workspace

Load requires the schema classes. Class-less dynamic load is not part of the
current public surface.

```python
loaded = FactGraph.load(workspace, schema_classes=[User])

loaded_snap = loaded.read.get(User, user_id="u-1")

assert loaded_snap is not None
assert tuple(loaded_snap.tag) == ("engineer",)
```

Recreate rule/inference values from code when you need to run them again:

```python
result_after_load = loaded.eval.evaluate(seeded_tags, head=seeded_tags)

assert result_after_load.count() == 1
```

## Migrate legacy workspaces

Older workspaces may still contain a filesystem `registry/` directory and a
schema snapshot at `registry/schema/schema_ir.json`. `FactGraph.load(...)` now
rejects that shape with an `SDKStoreError` and points you to the migration CLI.

Run:

```bash
python -m factgraph migrate-workspace /path/to/workspace
```

Useful options:

```bash
python -m factgraph migrate-workspace /path/to/workspace --dry-run
python -m factgraph migrate-workspace /path/to/workspace --no-archive
```

The default migration writes the schema object under `db/objects/schema/`,
updates the workspace manifest, and archives the old `registry/` directory as
`registry.legacy.<timestamp>/`. It does not recreate saved-rule or
saved-inference persistence; historical `registry/rules/` and
`registry/inferences/` files remain inert data.

## Which persistence surface should I use?

| Task | Use |
| --- | --- |
| Persist facts and schema anchor | `fg.save()` |
| Restore a graph workspace | `FactGraph.load(path, schema_classes=[...])` |
| Reuse rule/inference definitions | Keep `Rule(...)` / `Inference(...)` in Python code |
| Share executable engine artifacts | `fg.package.export_package(...)` |
| Migrate old registry-backed workspace | `python -m factgraph migrate-workspace <path>` |

## What not to do

Do not use removed registry persistence methods:

```text
fg.rules.save(rule)             # removed
fg.rules.load(saved_rule_ref)   # removed
fg.inferences.save(inference)   # removed
fg.inferences.load(saved_ref)   # removed
```

Do not pass `registry_root=` or `registry=` to `FactGraph.create(...)`; both
raise `SDKStoreError` with migration guidance.

Do not call `FactGraph.load(path)` without `schema_classes=[...]`. The loader
validates the workspace schema digest against your Python schema declarations.

## Complete example

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from factgraph.sdk import Branch, Entity, FactGraph, Field, Identity, Inference, Pred, Rule, build_application_rule, vars


class User(Entity):
    user_id: str = Identity(primary_key=True)
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


def make_rule() -> Rule:
    with vars("u", "tag") as (u, tag):
        return build_application_rule(
            id="user:tag",
            version="v1",
            where=[User(u), User(u).tag_seed == tag],
            ports={"user": u, "tag": tag},
        )


def make_inference() -> Inference:
    with vars("u", "tag") as (u, tag):
        return Inference(
            id="inf.tags_from_seed",
            version="v1",
            where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
            target="user:tag",
            head_vars=[u, tag],
        )


with TemporaryDirectory() as tmp_dir:
    workspace = Path(tmp_dir) / "workspace"
    fg = FactGraph.create(schema_classes=[User], path=workspace)

    alice = fg.read.ref(User, user_id="u-1")
    fg.write.set(User.tag_seed, alice, "engineer")

    rule = make_rule()
    inference = make_inference()

    rule_result = fg.eval.evaluate(rule, head=rule)
    assert rule_result.count() == 1

    result = fg.eval.evaluate(inference)
    row = result.first()
    assert row is not None
    assert row.claim.name == "user:tag"
    fg.write.add(User.tag, alice, "engineer")

    assert tuple(fg.read.get(User, user_id="u-1").tag) == ("engineer",)

    fg.save()

    restored = FactGraph.load(workspace, schema_classes=[User])
    restored_rule = make_rule()
    restored_result = restored.eval.evaluate(restored_rule, head=restored_rule)

    assert tuple(restored.read.get(User, user_id="u-1").tag) == ("engineer",)
    assert restored_result.count() == 1
```

## Syntax checklist

- Use `FactGraph.create(schema_classes=[...], path=workspace)` for a
  path-backed graph.
- Use `build_application_rule(...)` for application `Rule` values and
  `Inference(...)` for inference values; both stay in-memory.
- Use `fg.eval.evaluate(rule, head=rule)` for application rules and
  `fg.eval.evaluate(inference)` for inferences.
- Use `fg.save()` for the Level-4 workspace: manifest, ledger, and Database
  schema object.
- Use `FactGraph.load(path, schema_classes=[...])` to restore a workspace.
- Use `python -m factgraph migrate-workspace <path>` for pre-v0.2 workspaces
  that still carry `registry/`.
- Class-less load is not part of the current public surface.
- Views, artifacts, audit packages, service state, package exports, rules, and
  inferences are not part of the workspace format.
- Workspace persistence and package export are different surfaces.
