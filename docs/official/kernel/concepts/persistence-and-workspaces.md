# Persistence and workspaces

FactGraph persistence has two layers.

| Layer | Saves | Public surface |
| --- | --- | --- |
| Authoring registry | Reusable `Rule` and `Inference` definitions | `fg.rules.save(...)`, `fg.inferences.save(...)` |
| Workspace | Graph state you can continue later | `fg.save(...)`, `FactGraph.load(...)` |

The registry answers "which reusable authoring assets have I saved?" The
workspace answers "what graph state should I reopen later?"

Keeping those questions separate prevents a common mistake: saving a rule does
not save the ledger, and saving a workspace does not turn saved refs into
runtime objects.

## Registry handles are not runtime objects

Saving a rule returns a `SavedRuleRef`. That ref is a durable handle. It is not
the rule value object that `fg.eval.run(...)` consumes.

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
workspace = Path(tmp.name) / "graph"


class User(Entity):
    user_id: str = Identity(primary_key=True)
    seed_tag: str = Field(cardinality="single")
    tags: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User], path=workspace)

alice = fg.read.ref(User, user_id="u-1")
fg.write.set(User.seed_tag, alice, "engineer")

with vars("u", "tag") as (u, tag):
    seeded_tags = Rule(
        id="rule.seeded_tags",
        version="v1",
        select=[u, tag],
        where=[Branch([Pred("user:seed_tag", u, tag)], id="seed_path")],
    )

saved_rule = fg.rules.save(seeded_tags)

assert isinstance(saved_rule, SavedRuleRef)
assert fg.rules.get("rule.seeded_tags") == saved_rule

loaded_rule = fg.rules.load(saved_rule)
rows = fg.eval.run(loaded_rule)

assert isinstance(loaded_rule, Rule)
assert rows == [{"u": alice, "tag": "engineer"}]
```

The sequence is:

```text
Rule -> save -> SavedRuleRef -> load -> Rule -> run
```

`fg.rules.get(...)` follows the same handle model. It returns the latest
`SavedRuleRef` for a rule id, not the loaded `Rule`.

Inferences use the same shape:

```python
with vars("u", "tag") as (u, tag):
    tags_from_seed = Inference(
        id="inf.tags_from_seed",
        version="v1",
        where=[Branch([Pred("user:seed_tag", u, tag)], id="seed_path")],
        target="user:tags",
        head_vars=[u, tag],
    )

saved_inference = fg.inferences.save(tags_from_seed)

assert isinstance(saved_inference, SavedInferenceRef)
assert fg.inferences.get("inf.tags_from_seed") == saved_inference

loaded_inference = fg.inferences.load(saved_inference)
candidates = fg.eval.evaluate(loaded_inference)

assert len(candidates) == 1
assert tuple(fg.read.get(User, user_id="u-1").tags) == ()
```

Again, save and load are separate: `SavedInferenceRef` is a durable handle;
`Inference` is the runtime value object.

## A workspace is the graph state

When you create a graph with `path=...`, the graph has a workspace root. Calling
`fg.save()` writes a Level-4 workspace:

```text
workspace/
  factgraph_workspace.json
  ledger.db
  registry/
    registry_manifest.json
    schema/schema_ir.json
    rules/...
    inferences/...
```

That includes the ledger and the registry. It does not include views, package
exports, artifact sidecars, audit reports, service state, or class-less schema
generation.

```python
fg.eval.accept(candidates[0])
save_result = fg.save()

assert Path(save_result["path"]) == workspace
assert (workspace / "factgraph_workspace.json").exists()
assert (workspace / "ledger.db").exists()
assert (workspace / "registry").is_dir()
```

Saving the workspace is the point where "the graph state" is written to disk.
Saving an individual rule or inference only writes that authoring asset to the
registry.

## Loading needs schema classes

Current public loading is typed. You provide the Python `Entity` classes so the
SDK can rebuild the same facade and validate the workspace schema digest.

```python
loaded = FactGraph.load(workspace, schema_classes=[User])

loaded_snap = loaded.read.get(User, user_id="u-1")
loaded_rule_ref = loaded.rules.get("rule.seeded_tags")
loaded_inference_ref = loaded.inferences.get("inf.tags_from_seed")

assert loaded_snap is not None
assert tuple(loaded_snap.tags) == ("engineer",)
assert loaded_rule_ref == saved_rule
assert loaded_inference_ref == saved_inference

loaded_rule_again = loaded.rules.load(loaded_rule_ref)
assert loaded.eval.run(loaded_rule_again) == [{"u": alice, "tag": "engineer"}]
```

Class-less dynamic load is a separate design problem. For now, load with the
same schema declarations that define your public SDK model.

## Which layer should I use?

| Need | Use |
| --- | --- |
| Reuse a rule definition later | `fg.rules.save(rule)` |
| Reuse an inference definition later | `fg.inferences.save(inference)` |
| Find the latest saved handle | `fg.rules.get(id)` / `fg.inferences.get(id)` |
| Get a runtime value object from a saved handle | `fg.rules.load(ref)` / `fg.inferences.load(ref)` |
| Continue the full graph later | `fg.save()` then `FactGraph.load(...)` |
| Distribute a runtime package | `fg.package.export_package(...)` |

Package export is intentionally separate from workspace save. A workspace is
for continued editing and authoring. A package is for distribution or runtime
execution.

## What to remember

- Saved refs are handles, not runtime objects.
- `get(...)` returns the latest saved handle.
- `load(...)` returns the runtime `Rule` or `Inference`.
- Registry persistence and workspace persistence solve different problems.
- `fg.save(...)` writes the Level-4 workspace: manifest, ledger, schema, and
  registry.
- `FactGraph.load(...)` requires `schema_classes=[...]`.
- Views, artifacts, audit reports, and package exports are outside the first
  workspace format.
