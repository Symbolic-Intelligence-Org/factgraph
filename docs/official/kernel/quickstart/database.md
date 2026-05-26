# Database and durable views

Most quickstart pages use `FactGraph.create(...)`. That is the everyday SDK
runtime: it owns schema classes, read/write helpers, evaluation, evidence, and
workspace save/load.

`Database` is the lower identity boundary underneath that runtime. Use it when
you need to work directly with Database heads, content-addressed assertion
commits, or durable view objects.

```text
Database workspace -> Database.head() -> FactGraph.attach(db, schema_classes=[...])
                   -> fg.commit_assertions(...) -> db.create_view(...)
```

This page is for the shipped Database and view APIs. It does not introduce
view-scoped reads or evaluation.

## When to use Database

| Need | Use |
| --- | --- |
| Normal SDK application code | `FactGraph.create(...)`, `fg.write.*`, `fg.save()` |
| Low-level Database identity and head tracking | `Database.create(...)`, `Database.open(...)`, `db.head()` |
| Database-owned assertion commits | `fg.commit_assertions(...)` on an attached runtime |
| Durable frozen assertion-id objects | `db.create_view(...)` |
| Session-local named id sets | `fg.views.create(...)` |

`FactGraph.save()` and `FactGraph.load(...)` remain the high-level workspace
path. `Database` is useful when you need the lower Database boundary directly.

## Define a schema IR

`Database.create(...)` takes a compiled schema IR, not entity classes directly.
Use `compile_schema_from_classes(...)` when starting from SDK schema classes.

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from factgraph.sdk import (
    AssertionInput,
    Database,
    Entity,
    FactGraph,
    Field,
    Identity,
    MetaEntry,
    compile_schema_from_classes,
)


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


schema_ir = compile_schema_from_classes([User])
```

The same schema classes are passed again when you attach an SDK runtime. The
attach call validates that the classes compile to the Database schema digest.

## Create a Database workspace

Create a new-layout Database workspace with `Database.create(...)`:

```python
tmp = TemporaryDirectory()
workspace = Path(tmp.name) / "database-workspace"

db = Database.create(workspace, schema_ir=schema_ir)
head = db.head()

assert db.db_id.startswith("db:")
assert db.schema_digest.startswith("sha256:")
assert head.db_id == db.db_id
assert head.schema_digest == db.schema_digest
assert head.tx_id.startswith("tx:")
assert head.data_digest.startswith("sha256:")
```

`DatabaseValue` is the immutable head identity. It carries:

- `db_id`
- `tx_id`
- `schema_digest`
- `data_digest`

Every Database commit advances the head to a new `DatabaseValue`.

## Attach a FactGraph runtime

Attach creates an SDK runtime over the Database ledger:

```python
fg = FactGraph.attach(db, schema_classes=[User])
```

Attached runtimes are deliberately stricter than ordinary SDK runtimes. Writes
route through `fg.commit_assertions(...)`, which delegates to
`Database.commit_assertions(...)`.

Common SDK mutation shortcuts reject in attached mode:

```python
# fg.write.set(...)    # rejected on attached runtimes
# fg.write.add(...)    # rejected on attached runtimes
# fg.save()            # rejected on attached runtimes
# fg.views.create(...) # rejected on attached runtimes
```

Use attached runtimes for SDK readback and schema-aware helpers around a
Database-owned commit path.

## Commit assertions

`fg.commit_assertions(...)` accepts `AssertionInput` values. Each input uses the
normalized fact shape:

```python
("entity_ref", "idref_v1:User:u-1")
("string", "Alice")
```

Find the predicate id from the compiled schema IR:

```python
def field_pred_id(schema_ir: dict, owner_type: str, field_name: str) -> str:
    for pred in schema_ir["predicates"]:
        if pred.get("owner_type") == owner_type and pred.get("py_field_name") == field_name:
            return pred["pred_id"]
    raise LookupError(f"{owner_type}.{field_name} predicate not found")


user_name_pred = field_pred_id(schema_ir, "User", "name")
```

Then commit an assertion:

```python
before = db.head()

commit = fg.commit_assertions(
    [
        AssertionInput(
            pred_id=user_name_pred,
            fact_tuple=(("entity_ref", "idref_v1:User:u-1"), ("string", "Alice")),
            meta=(
                MetaEntry("source", "str", "database-quickstart"),
                MetaEntry("ingested_at", "time", 1_800_000_000_000_000_000),
            ),
        )
    ]
)

record = commit.assertions[0]

assert commit.parent_tx_id == before.tx_id
assert commit.value == db.head()
assert record.asrt_id.startswith("asrt:")
```

`ingested_at` is required for snapshot projection policies. The Database commit
surface is lower-level than `fg.write.*`, so this example supplies it
explicitly.

Attached SDK readback works at the assertion-record layer:

```python
readback = fg.assertions.by_id(record.asrt_id)

assert readback is not None
assert readback.value == "Alice"
```

## Create a durable Database view

`Database.create_view(...)` creates a durable six-field view object:

```python
view = db.create_view("name_review", [record.asrt_id])

assert view.name == "name_review"
assert view.db_id == db.db_id
assert view.base_tx_id == db.head().tx_id
assert view.schema_digest == db.schema_digest
assert view.asrt_ids == (record.asrt_id,)
assert view.view_digest.startswith("sha256:")
```

The view object is written under:

```text
views/objects/<64hex>.json
```

`name` is only a label. It is not part of `view_digest`; the digest is based on
the Database identity anchors and the sorted assertion-id set.

`base=` is an advanced current-head check:

```python
same_view = db.create_view("name_review", [record.asrt_id], base=db.head())

assert same_view.view_digest == view.view_digest
```

Historical-base view creation is not part of the current public surface.

## Open the Database again

Open validates the workspace schema object against the schema IR you provide:

```python
reopened = Database.open(workspace, schema_ir=schema_ir)

assert reopened.head() == db.head()
```

Reattach when you want SDK read helpers over the reopened Database:

```python
reattached = FactGraph.attach(reopened, schema_classes=[User])
again = reattached.assertions.by_id(record.asrt_id)

assert again is not None
assert again.value == "Alice"
```

`Database.open(":memory:", ...)` is not supported. Memory Databases are created
with `Database.create(schema_ir=...)` and do not support durable view object
persistence.

## SDK views are different

The SDK also has `fg.views`, taught in
[Assertion records and views](assertions.md). That surface is intentionally
different:

| Surface | Shape | Persistence | Purpose |
| --- | --- | --- | --- |
| `fg.views.create(...)` | `name`, `asrt_ids` | In-memory only | Session-local named assertion-id sets |
| `db.create_view(...)` | `name`, `db_id`, `base_tx_id`, `schema_digest`, `asrt_ids`, `view_digest` | Durable `views/objects` object | Database-owned frozen scope object |

SDK views are not written by `fg.save(...)`, and `FactGraph.load(...)` does not
restore them. Database durable views are content-addressed objects owned by the
Database workspace.

`view=` is an **attach-time** argument, not a row-level read or evaluate
parameter. The next section shows the shipped attach pattern. These row-level
forms are explicitly rejected:

```python
# fg.read.find(User, view=view)          # not a parameter; use attach(db, view=view)
# fg.eval.evaluate(rule, view=view)      # not a parameter; use attach(db, view=view)
```

The SDK raises `SDKStoreError: method-level view= is not supported by ...; use
FactGraph.attach(db, view=view) instead` on both forms.

Use `fg.assertions.by_ids(view.asrt_ids)` for assertion-record readback when
you have a view's assertion ids without view-scoped attach.

## View-scoped attach

Pass a durable `db.create_view(...)` view to `FactGraph.attach(...)` to obtain
a **read-only, view-scoped** SDK runtime:

```python
view = db.create_view("name_review", [record.asrt_id])

view_fg = FactGraph.attach(db, schema_classes=[User], view=view)
```

The view-attached runtime:

- scopes every `fg.read.*` call to the assertion-id set frozen by the view;
- scopes `fg.eval.evaluate(...)` to the same assertion universe;
- rejects mutation methods on the runtime, including
  `fg.commit_assertions(...)`, which raises:

```text
SDKStoreError: fg.commit_assertions(...) is not available on
FactGraph.attach(db, view=view) runtimes; view-attached runtimes are
read-only
```

Use the writable attach (`FactGraph.attach(db, schema_classes=[User])`)
when you need to write through `fg.commit_assertions(...)`. Use the
view-scoped attach when you need a frozen read-only view of a specific
Database view object.

Pass `view=None` (the default) for a non-view attach. The kwarg validates
that `view.db_id == db.db_id` and `view.schema_digest == db.schema_digest`
before the runtime is built; mismatches raise `SDKStoreError` immediately.

## Complete example

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from factgraph.sdk import (
    AssertionInput,
    Database,
    Entity,
    FactGraph,
    Field,
    Identity,
    MetaEntry,
    compile_schema_from_classes,
)


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


def field_pred_id(schema_ir: dict, owner_type: str, field_name: str) -> str:
    for pred in schema_ir["predicates"]:
        if pred.get("owner_type") == owner_type and pred.get("py_field_name") == field_name:
            return pred["pred_id"]
    raise LookupError(f"{owner_type}.{field_name} predicate not found")


with TemporaryDirectory() as tmp_dir:
    workspace = Path(tmp_dir) / "database-workspace"
    schema_ir = compile_schema_from_classes([User])

    db = Database.create(workspace, schema_ir=schema_ir)
    before = db.head()

    fg = FactGraph.attach(db, schema_classes=[User])
    commit = fg.commit_assertions(
        [
            AssertionInput(
                pred_id=field_pred_id(schema_ir, "User", "name"),
                fact_tuple=(("entity_ref", "idref_v1:User:u-1"), ("string", "Alice")),
                meta=(
                    MetaEntry("source", "str", "database-quickstart"),
                    MetaEntry("ingested_at", "time", 1_800_000_000_000_000_000),
                ),
            )
        ]
    )

    record = commit.assertions[0]
    view = db.create_view("name_review", [record.asrt_id])

    # View-scoped attach: read-only runtime frozen to the view's asrt_ids.
    view_fg = FactGraph.attach(reopened := Database.open(workspace, schema_ir=schema_ir), schema_classes=[User], view=view)
    view_readback = view_fg.assertions.by_id(record.asrt_id)

    # Plain reattach: writable; reads see the live ledger.
    reattached = FactGraph.attach(reopened, schema_classes=[User])
    readback = reattached.assertions.by_id(record.asrt_id)

    assert commit.parent_tx_id == before.tx_id
    assert reopened.head() == db.head()
    assert view.asrt_ids == (record.asrt_id,)
    assert view_readback is not None
    assert view_readback.value == "Alice"
    assert readback is not None
    assert readback.value == "Alice"
```

## Syntax checklist

- Use `compile_schema_from_classes([...])` to produce `schema_ir` for
  `Database.create(...)` and `Database.open(...)`.
- Use `Database.create(path, schema_ir=schema_ir)` for a new durable Database
  workspace.
- Use `Database.open(path, schema_ir=schema_ir)` to reopen an existing Database.
- Use `db.head()` to read the current `DatabaseValue`.
- Use `FactGraph.attach(db, schema_classes=[...])` for SDK read helpers over a
  Database.
- Use `fg.commit_assertions([AssertionInput(...)])` for Database-owned writes
  on attached runtimes.
- Include required metadata such as `MetaEntry("ingested_at", "time", epoch_ns)`
  when writing low-level assertions that should participate in snapshot
  projection.
- Use `db.create_view(name, asrt_ids=[...])` for durable Database view objects.
- Use `fg.views.create(name, asrt_ids=[...])` only for in-memory named id sets.
- `view=` is an attach-time argument: `FactGraph.attach(db, schema_classes=[...], view=view)`
  produces a read-only, view-scoped runtime. It is not accepted as a row-level
  parameter on `fg.read.find(...)` or `fg.eval.evaluate(...)`.
