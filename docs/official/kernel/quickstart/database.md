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

This page is for the shipped Database and durable view APIs, including
attach-time view-scoped reads and evaluation with
`FactGraph.attach(db, view=view)`. Method-level `view=` parameters remain
intentionally unsupported.

## When to use Database

| Need | Use |
| --- | --- |
| Normal SDK application code | `FactGraph.create(...)`, `fg.fields.*`, `fg.save()` |
| Low-level Database identity and head tracking | `Database.create(...)`, `Database.open(...)`, `db.head()` |
| Database-owned assertion commits | `fg.commit_assertions(...)` on an attached runtime |
| Durable frozen assertion-id objects | `db.create_view(...)` |
| Session-local named id sets | `fg.views.create(...)` |

`FactGraph.save()` and `FactGraph.load(...)` remain the high-level workspace
path. `Database` is useful when you need the lower Database boundary directly.

## Define a schema IR

The other quickstart pages use `FactGraph.create(schema_classes=[...])` and
never mention a "schema IR" — that is intentional. `FactGraph.create(...)`
calls `compile_schema_from_classes(schema_classes)` for you and stores the
resulting compiled IR inside the runtime.

`Database` is the lower identity boundary, so its constructor takes the
**already-compiled IR directly**:

| Surface | Accepts | Why |
| --- | --- | --- |
| `FactGraph.create(schema_classes=[...])` | Python `Entity` classes | High-level constructor. Compiles internally and stores the IR. |
| `FactGraph.load(path, schema_classes=[...])` | Python `Entity` classes | Compiles internally and validates the compiled digest against the saved workspace digest. |
| `FactGraph.attach(db, schema_classes=[...])` | Python `Entity` classes | Compiles internally and validates the compiled digest against `db.schema_digest`. |
| `Database.create(path, schema_ir=...)` | Already-compiled IR | Lower Database boundary. Identity-anchored; takes the IR directly. |
| `Database.open(path, schema_ir=...)` | Already-compiled IR | Lower Database boundary. Validates the workspace schema object against the supplied IR. |

So when you work directly with `Database`, compile once and reuse the IR:

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
    user_id: str = Identity()
    name: str = Field()


schema_ir = compile_schema_from_classes([User])
```

The Python `Entity` classes are still required separately when you `attach`
an SDK runtime over the Database, because the SDK needs the class objects
(not just the compiled IR) to bind read/write helpers. The attach call then
compiles those classes again and checks that the compiled digest matches
`db.schema_digest` (see [Schema strong correspondence](#schema-strong-correspondence)
below).

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

`schema_classes=[...]` is **not optional and not a filter**. The SDK compiles
those classes to a schema digest and requires it to match the Database's
schema digest exactly:

```text
schema_digest(compile_schema_from_classes(schema_classes)) == db.schema_digest
```

Any difference — missing entity classes, extra unrelated classes, or class
order causing a different compiled digest — rejects attach with:

```text
SDKStoreError: schema mismatch: Database has schema_digest=...,
but schema_classes compile to ...
```

`schema_classes` is not a way to view a subset of the Database; it must
reconstruct the same compiled schema the Database was created with.

Common SDK mutation shortcuts reject in attached mode:

```python
# fg.fields.set(...)    # rejected on attached runtimes
# fg.fields.add(...)    # rejected on attached runtimes
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
surface is lower-level than `fg.fields.*`, so this example supplies it
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

## Durable views are immutable

`Database` only ships `create_view(...)`. There is **no `update_view`**, **no
`delete_view`**, no `get_view`, and no `list_views`. This is by design:
durable Database views are **content-addressed immutable objects** whose file
path on disk is the `view_digest`, not the `name`.

That has three consequences worth knowing up front.

### Re-creating with the same name + assertion ids is idempotent

```python
v1 = db.create_view("review", [record.asrt_id])
v2 = db.create_view("review", [record.asrt_id])

assert v1.view_digest == v2.view_digest          # same digest
# views/objects/<view_digest>.json was written once and not rewritten.
```

The Database identity anchors (`db_id`, `base_tx_id`, `schema_digest`) and the
sorted `asrt_ids` fully determine `view_digest`. Calling `create_view(...)`
with the same inputs twice produces the same digest and no second filesystem
write.

### Same name, different ids creates a *new* view; the old one stays

```python
v_one = db.create_view("review", [record.asrt_id])
v_two = db.create_view("review", [record.asrt_id, other_record.asrt_id])

assert v_one.view_digest != v_two.view_digest
# Both views/objects/<v_one_digest>.json and views/objects/<v_two_digest>.json
# now exist on disk. The "review" name resolves to two distinct view objects.
```

`name` is just a label inside the JSON payload. The Database does not
maintain a name → view registry, so re-using a name does not overwrite or
shadow the prior view object.

### "Update" and "delete" are deliberately not shipped

To change the assertion-id set in a logical view, **create a new view object**
with the desired `asrt_ids`. The old view object remains on disk until you
remove it at the filesystem level (e.g. delete the corresponding
`views/objects/<old_digest>.json` outside the SDK). The SDK does not expose a
public delete or update path because doing so would mutate
content-addressed objects.

If you only need a short-lived assertion-id set scoped to one SDK session,
use `fg.views.create(...)` instead — that surface **does** support
`update(...)`, `delete(...)`, `get(...)`, and `list()`, but it is
in-memory-only and is not written by `fg.save(...)` or restored by
`FactGraph.load(...)`. The contrast is summarized below in
[SDK views are different](#sdk-views-are-different).

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
# fg.entities.where(User, view=view)          # not a parameter; use attach(db, view=view)
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

- scopes every `fg.entities.*` call to the assertion-id set frozen by the view;
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

Pass `view=None` (the default) for a non-view attach.

### Schema strong correspondence

View-scoped attach extends the writable-attach schema-digest equality into a
**three-way correspondence chain**, all checked before the runtime is built:

```text
schema_digest(compile_schema_from_classes(schema_classes))
  == db.schema_digest
  == view.schema_digest
```

Plus the Database-identity binding and the view's frozen-base anchors:

| Check | Reject error |
| --- | --- |
| `compiled(schema_classes) != db.schema_digest` | `SDKStoreError: schema mismatch: Database has schema_digest=..., but schema_classes compile to ...` |
| `view.schema_digest != db.schema_digest` | `SDKStoreError: view schema mismatch: view.schema_digest=..., ...` |
| `view.db_id != db.db_id` | `SDKStoreError: view db_id mismatch: view.db_id=..., Database.db_id=...` |
| `view.base_tx_id` not materializable from this Database | `SDKStoreError: view base_tx_id not found in Database: ...` |
| `view.asrt_ids` not present at `view.base_tx_id` | `SDKStoreError: view references assertion ids not present at base_tx_id=...` |

There is no fallback to current head or the full assertion universe; any
broken link in the chain rejects attach.

This means a Database `view` object created against one Database **cannot** be
attached against a different Database, and a view created with one schema
**cannot** be attached with incompatible `schema_classes` — even if the view's
`asrt_ids` happen to exist in another workspace.

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
    user_id: str = Identity()
    name: str = Field()


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
  Durable views are **immutable**; there is no `update_view` / `delete_view` /
  `get_view` / `list_views`. Same name + same `asrt_ids` is idempotent; same
  name + different `asrt_ids` writes a new view object whose file path is the
  new `view_digest`. To "change" a view, create a new one; to "remove" one,
  delete `views/objects/<view_digest>.json` outside the SDK.
- Use `fg.views.create(name, asrt_ids=[...])` only for in-memory named id sets.
  `fg.views` **does** support `get(...)`, `list()`, `update(...)`, and
  `delete(...)`, but it is session-local and not written by `fg.save(...)`.
- `view=` is an attach-time argument: `FactGraph.attach(db, schema_classes=[...], view=view)`
  produces a read-only, view-scoped runtime. It is not accepted as a row-level
  parameter on `fg.entities.where(...)` or `fg.eval.evaluate(...)`.
- Attach enforces a **three-way schema strong correspondence**:
  `compiled(schema_classes) == db.schema_digest == view.schema_digest`
  (the third leg only on view-scoped attach). `schema_classes` is not a
  Database-side filter; incomplete or mismatched classes reject before any
  read.
