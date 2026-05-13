# Save rules, inferences, and workspaces

The earlier pages kept everything in memory. This page adds persistence.

There are two layers:

| Need | Use |
| --- | --- |
| Save one reusable rule or inference | `fg.rules.save(...)` / `fg.inferences.save(...)` |
| Load a saved authoring asset | `fg.rules.load(...)` / `fg.inferences.load(...)` |
| Save the whole graph state | `fg.save()` |
| Restore the whole graph state | `FactGraph.load(...)` |

Think of the registry as the place for authoring assets, and the workspace as
the place for a complete graph state. A workspace contains the ledger, schema
metadata, registry, and a workspace manifest.

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
    SavedInferenceRef,
    SavedRuleRef,
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

Because `path=` is set, the graph also gets default workspace registry and
ledger locations. You can still work in memory until you call `fg.save()`.

## Save a Rule

Rules and inferences are ordinary Python value objects first. Saving them
stores their authoring form in the registry and returns a saved-ref handle.

```python
with vars("u", "tag") as (u, tag):
    seeded_tags = Rule(
        id="rule.seeded_tags",
        version="v1",
        select=[u, tag],
        where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
    )


rule_ref = fg.rules.save(seeded_tags)

assert isinstance(rule_ref, SavedRuleRef)
assert rule_ref.rule_id == "rule.seeded_tags"
assert rule_ref.version == "v1"
```

`SavedRuleRef` is a registry handle. It is not the rule itself, and it is not
something you pass to `fg.eval.run(...)`.

Load the ref to get the runtime value object:

```python
loaded_rule = fg.rules.load(rule_ref)
rows = fg.eval.run(loaded_rule)

assert isinstance(loaded_rule, Rule)
assert rows == [{"u": alice, "tag": "engineer"}]
```

## List and get saved rules

`list()` returns saved refs for all saved versions. `get(id)` returns the
latest saved ref for one id.

```python
rule_refs = fg.rules.list()
latest_rule_ref = fg.rules.get("rule.seeded_tags")

assert rule_refs == [rule_ref]
assert latest_rule_ref == rule_ref
assert isinstance(latest_rule_ref, SavedRuleRef)
```

The last assertion is the important one. `get(...)` returns a handle, not a
`Rule`. Load it before running:

```python
latest_rule = fg.rules.load(latest_rule_ref)

assert fg.eval.run(latest_rule) == rows
```

## Save and load an Inference

Inferences use the same pattern.

```python
with vars("u", "tag") as (u, tag):
    tags_from_seed = Inference(
        id="inf.tags_from_seed",
        version="v1",
        where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
        target="user:tag",
        head_vars=[u, tag],
    )


inference_ref = fg.inferences.save(tags_from_seed)

assert isinstance(inference_ref, SavedInferenceRef)
assert inference_ref.inference_id == "inf.tags_from_seed"
```

Load before evaluating:

```python
loaded_inference = fg.inferences.load(inference_ref)
candidates = fg.eval.evaluate(loaded_inference)

assert isinstance(loaded_inference, Inference)
assert len(candidates) == 1
assert candidates[0].target == "user:tag"
assert tuple(fg.read.get(User, user_id="u-1").tag) == ()
```

Accepting the candidate writes it to the ledger:

```python
fg.eval.accept(candidates[0])

assert tuple(fg.read.get(User, user_id="u-1").tag) == ("engineer",)
```

The saved inference asset and the accepted assertion are different things. The
asset describes how to derive candidates. The ledger stores accepted facts.

## Save the workspace

Saving a rule or inference writes to the registry. It does not, by itself, mean
you have saved the whole graph state. Call `fg.save()` to persist the workspace.

```python
save_result = fg.save()

assert Path(save_result["path"]) == workspace
assert (workspace / "factgraph_workspace.json").exists()
assert (workspace / "ledger.db").exists()
assert (workspace / "registry").is_dir()
```

The workspace is a level-4 graph snapshot:

- schema metadata
- ledger database
- authoring registry
- workspace manifest

Artifact sidecars, views, audit reports, and service state are not part of this
workspace format.

The workspace manifest records the save scope and schema digest. Loading checks
the manifest, ledger, registry schema metadata, and the `schema_classes=[...]`
you provide. That is why the loader asks for Python schema classes instead of
guessing a dynamic class model.

## Load the workspace

Load requires the schema classes. Class-less dynamic load is not part of the
current public surface.

```python
loaded = FactGraph.load(workspace, schema_classes=[User])

loaded_snap = loaded.read.get(User, user_id="u-1")
loaded_rule_ref = loaded.rules.get("rule.seeded_tags")
loaded_inference_ref = loaded.inferences.get("inf.tags_from_seed")

assert loaded_snap is not None
assert tuple(loaded_snap.tag) == ("engineer",)
assert loaded_rule_ref == rule_ref
assert loaded_inference_ref == inference_ref
```

The loaded graph has the ledger and the registry. You can load the saved rule
and run it again.

```python
rule_after_load = loaded.rules.load(loaded_rule_ref)
rows_after_load = loaded.eval.run(rule_after_load)

assert rows_after_load == [{"u": alice, "tag": "engineer"}]
```

## Which save should I use?

| Task | Use |
| --- | --- |
| Save a reusable rule definition | `fg.rules.save(rule)` |
| Save a reusable inference definition | `fg.inferences.save(inference)` |
| Get the latest saved handle | `fg.rules.get(id)` / `fg.inferences.get(id)` |
| Load a runtime value object | `fg.rules.load(ref)` / `fg.inferences.load(ref)` |
| Save graph state to disk | `fg.save()` |
| Restore graph state from disk | `FactGraph.load(path, schema_classes=[...])` |

## What not to do

Do not pass saved refs to runtime methods:

```text
fg.eval.run(saved_rule_ref)        # wrong
fg.eval.evaluate(saved_inf_ref)    # wrong
```

Saved refs are load handles. Runtime methods consume `Rule` and `Inference`
value objects.

Do not use `from_schema_classes(path=...)`. The workspace lifecycle lives on
the public `FactGraph.create(path=...)`, `fg.save(...)`, and
`FactGraph.load(...)` path.

Do not call `FactGraph.load(path)` without `schema_classes=[...]`. The loader
validates the workspace schema digest against your Python schema declarations.

## Complete example

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

    rule_ref = fg.rules.save(make_rule())
    inference_ref = fg.inferences.save(make_inference())

    rule = fg.rules.load(rule_ref)
    inference = fg.inferences.load(inference_ref)

    assert fg.eval.run(rule) == [{"u": alice, "tag": "engineer"}]

    candidate = fg.eval.evaluate(inference)[0]
    fg.eval.accept(candidate)

    assert tuple(fg.read.get(User, user_id="u-1").tag) == ("engineer",)

    fg.save()

    restored = FactGraph.load(workspace, schema_classes=[User])

    restored_rule = restored.rules.load(restored.rules.get("rule.seeded_tags"))
    restored_rows = restored.eval.run(restored_rule)

    assert tuple(restored.read.get(User, user_id="u-1").tag) == ("engineer",)
    assert restored_rows == [{"u": alice, "tag": "engineer"}]
```

## Syntax checklist

- Use `FactGraph.create(schema_classes=[...], path=workspace)` for a
  path-backed graph.
- Use `fg.rules.save(rule)` and `fg.inferences.save(inference)` for per-asset
  registry persistence.
- `fg.rules.get(id)` and `fg.inferences.get(id)` return the latest saved ref.
- Use `fg.rules.load(ref)` and `fg.inferences.load(ref)` to get runtime value
  objects.
- Runtime methods consume loaded `Rule` and `Inference` objects, not saved refs.
- Use `fg.save()` for the Level-4 workspace: manifest, ledger, schema IR, and
  registry rules/inferences.
- Use `FactGraph.load(path, schema_classes=[...])` to restore a workspace.
- Class-less load is not part of the current public surface.
- Views, artifacts, audit packages, service state, and package exports are not
  part of the workspace format.
- Workspace persistence and package export are different surfaces.
