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
construct them when needed, and pass them directly to `fg.eval.run(...)` /
`fg.eval.evaluate(...)`. The old saved-rule and saved-inference registry
handles were removed in the Slice 7C registry-final-removal work.

## Create a path-backed graph

Pass `path=` to `FactGraph.create(...)` when you want the graph to know where
its workspace should live.

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from kernel.sdk import (
    Branch,
    Entity,
    FactGraph,
    Field,
    Identity,
    Inference,
    Pred,
    Rule,
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
    seeded_tags = Rule(
        id="rule.seeded_tags",
        version="v1",
        select=[u, tag],
        where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
    )

rows = fg.eval.run(seeded_tags)

assert rows == [{"u": alice, "tag": "engineer"}]
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

candidates = fg.eval.evaluate(tags_from_seed)

assert len(candidates) == 1
assert candidates[0].target == "user:tag"
```

Accepting a candidate writes ledger assertions:

```python
fg.eval.accept(candidates[0])

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
rows_after_load = loaded.eval.run(seeded_tags)

assert rows_after_load == [{"u": alice, "tag": "engineer"}]
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

from kernel.sdk import Branch, Entity, FactGraph, Field, Identity, Inference, Pred, Rule, vars


class User(Entity):
    user_id: str = Identity(primary_key=True)
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


def make_rule() -> Rule:
    with vars("u", "tag") as (u, tag):
        return Rule(
            id="rule.seeded_tags",
            version="v1",
            select=[u, tag],
            where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
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

    assert fg.eval.run(rule) == [{"u": alice, "tag": "engineer"}]

    candidate = fg.eval.evaluate(inference)[0]
    fg.eval.accept(candidate)

    assert tuple(fg.read.get(User, user_id="u-1").tag) == ("engineer",)

    fg.save()

    restored = FactGraph.load(workspace, schema_classes=[User])
    restored_rows = restored.eval.run(make_rule())

    assert tuple(restored.read.get(User, user_id="u-1").tag) == ("engineer",)
    assert restored_rows == [{"u": alice, "tag": "engineer"}]
```

## Syntax checklist

- Use `FactGraph.create(schema_classes=[...], path=workspace)` for a
  path-backed graph.
- Use `Rule(...)` and `Inference(...)` as in-memory Python values.
- Use `fg.eval.run(rule)` and `fg.eval.evaluate(inference)` directly.
- Use `fg.save()` for the Level-4 workspace: manifest, ledger, and Database
  schema object.
- Use `FactGraph.load(path, schema_classes=[...])` to restore a workspace.
- Use `python -m factgraph migrate-workspace <path>` for pre-v0.2 workspaces
  that still carry `registry/`.
- Class-less load is not part of the current public surface.
- Views, artifacts, audit packages, service state, package exports, rules, and
  inferences are not part of the workspace format.
- Workspace persistence and package export are different surfaces.
