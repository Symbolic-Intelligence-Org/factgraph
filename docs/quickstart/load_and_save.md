# Load and save: working with a FactGraph workspace

A FactGraph workspace is a directory on disk that holds the persistent state of one graph. The SDK supports two ways to own and write a workspace.

**Mode A** (SDK-owned, `FactGraph.create` + `fg.save_workspace`) is the main mode. It supports the full ergonomic SDK write surface (`fg.entities.*`, `fg.fields.*`, batches, ingest) and is what every other quickstart page describes when it shows a `fg.<...>` call.

**Mode B** (Database-owned, `FactGraph.attach`) is a specialized substrate. It only accepts `fg.commit_assertions(list[AssertionInput])` as a write entry and supports durable view objects through `db.create_view(...)`. Use Mode B when you specifically need durable views, explicit `tx_id` tracking, or view-scoped read-only attach; otherwise use Mode A.

This page documents both modes, the disk layout each one produces, and the rule that governs which writes work where. The two modes write incompatible disk formats and are not interchangeable.

## 1. What a workspace is

A workspace is identified by its `db_id` and its `schema_digest`. Both are written once when the workspace is created and never change. Reopening a workspace with a set of `Entity` classes that compiles to a different schema digest is rejected (see §6.5).

There are two disk formats. They share the manifest filename and the `db/objects/schema/` schema-object location, but diverge on where the SQLite ledger lives and what transaction-tracking files exist.

### Mode A — workspace written by `fg.save_workspace()`

```
<workspace_root>/
├── factgraph_workspace.json     # app-layer manifest (version + components + schema_digest)
├── ledger.db                    # SQLite ledger (top-level)
└── db/
    └── objects/
        └── schema/<digest>.json # one schema-IR object, content-addressed
```

The manifest lists `components: {"ledger": "ledger.db", "db": "db/", "views": "views/"}` and `save_scope: "level_4"`.

### Mode B — workspace written by `Database.create()`

```
<workspace_root>/
├── factgraph_workspace.json     # Database-layer manifest (no `ledger` component)
└── db/
    ├── meta.json                # db_id
    ├── assertions.db            # SQLite ledger (under db/)
    ├── objects/
    │   ├── tx/<tx_id>.json      # one object per commit
    │   └── schema/<digest>.json
    └── refs/
        └── head.txt             # current head tx_id
└── views/<view_digest>.json     # one object per db.create_view(...) call
```

The manifest lists only `components: {"db": "db/", "views": "views/"}`. Every commit advances `refs/head.txt` and writes a new `objects/tx/<tx_id>.json`.

### Workspace-less runtime

`FactGraph.create(schema_classes=[...])` without `path=` is a pure in-memory FactGraph runtime: writes work, nothing is persisted, closing the process discards the state. It can be promoted to a Mode A workspace later by calling `fg.save_workspace(path=...)`.

## 2. Two ownership modes

A workspace has exactly one owner at any moment. The owner decides which write API is available.

| Owner | Constructor | Reopen | Write API | Persistence trigger |
|---|---|---|---|---|
| **SDK runtime** (Mode A) | `FactGraph.create(path=..., schema_classes=[...])` | `FactGraph.load_workspace(path, schema_classes=[...])` | `fg.entities.*`, `fg.fields.*`, `fg.assertions.retract`, `fg.batch`, `fg.ingest` | explicit `fg.save_workspace(path=None)` |
| **Database** (Mode B) | `Database.create(path, schema_ir=...)` + `FactGraph.attach(db, schema_classes=[...])` | `Database.open(path, schema_ir=...)` + `FactGraph.attach(...)` | `fg.commit_assertions([AssertionInput, ...])` only | every commit advances the head; no explicit save |

### The write APIs are mutually exclusive

| Method | Mode A | Mode B (writable attach) | Mode B (view-scoped attach) |
|---|---|---|---|
| `fg.entities.create` / `delete` | ✅ | ❌ rejected | ❌ rejected |
| `fg.entities.edit` | ✅ | ❌ rejected | ❌ rejected |
| `fg.fields.set` / `add` / `retract` / `delete` | ✅ | ❌ rejected | ❌ rejected |
| `fg.assertions.retract` | ✅ | ❌ rejected | ❌ rejected |
| `fg.batch` / `fg.ingest` / `fg.add_schema_classes` | ✅ | ❌ rejected | ❌ rejected |
| `fg.assertion_views.create` / `update` / `delete` | ✅ | ❌ rejected | ❌ rejected |
| `fg.save_workspace` | ✅ | ❌ rejected | ❌ rejected |
| `fg.commit_assertions` | ❌ rejected | ✅ the only write entry | ❌ rejected |
| `db.create_view` | (n/a) | ✅ writes durable view object | (n/a) |

Reads work identically in both modes: `fg.entities.{get,where,match,ref,exists}`, `fg.fields.get`, `fg.assertions.*`, `fg.eval.*`, `fg.audit.*`, `fg.rules.inspect`.

Ergonomic write methods reject attached calls with:

```text
SDKStoreError: attached FactGraph runtimes route writes only through
fg.commit_assertions(...); <method_name> is not available on attached runtimes
```

### Disk formats are incompatible

A Mode A workspace cannot be opened by `Database.open(...)` — it is missing `db/meta.json`, `db/refs/head.txt`, the transaction objects under `db/objects/tx/`, and the ledger is at the wrong path (`ledger.db` rather than `db/assertions.db`).

A Mode B workspace cannot be opened by `FactGraph.load_workspace(...)` — its manifest is missing the `components.ledger` field that `validate_workspace_manifest` requires. The error is:

```text
WorkspaceRuntimeError: workspace manifest ledger component mismatch
```

Choose the mode at workspace creation. There is no in-place migration path between formats.

## 3. Mode A: SDK-owned workspace

This is the main mode. The rest of the SDK quickstart material assumes a Mode A runtime.

### 3.1 Create

```python
from factgraph.sdk import FactGraph

fg = FactGraph.create(
    path="path/to/workspace",
    schema_classes=[User, Order],
)
```

At construction time, the SDK compiles the schema once and writes `<path>/db/objects/schema/<digest>.json`. The workspace path is stored on the runtime for later `fg.save_workspace()` calls. The SQLite ledger stays in memory until the first save.

### 3.2 Write

All ergonomic write methods are available. `fg.commit_assertions(...)` is rejected in this mode:

```text
SDKStoreError: fg.commit_assertions(...) is only available on FactGraph.attach(db)
runtimes; use fg.fields.set / fg.fields.add for non-attached SDKStores
```

Use the SDK namespaces:

- `fg.entities.create / delete / edit` for entity lifecycle
- `fg.fields.set / add / retract / delete` for field-cell mutations
- `fg.assertions.retract(asrt_id, ...)` for assertion-id retract
- `fg.batch(meta=...)` for transactional grouping
- `fg.ingest(...)` for bulk

Each is documented in the SDK quickstart pages. This page does not duplicate that material.

### 3.3 Save

```python
fg.save_workspace()                  # uses path set at FactGraph.create(...)
fg.save_workspace(path="other/path") # binds to a new path
```

Save writes the schema object (re-emitted in case the schema changed), backs up the in-memory ledger to `<path>/ledger.db`, and writes the manifest. If neither call form supplies a path:

```text
SDKStoreError: workspace path not bound; pass fg.save_workspace(path=...) or
create with FactGraph.create(path=...)
```

Saving an in-memory runtime to a path is the supported upgrade path from no-workspace to workspace.

### 3.4 Load

```python
fg = FactGraph.load_workspace(
    "path/to/workspace",
    schema_classes=[User, Order],
)
```

Load compiles `schema_classes`, computes its schema identity digest, and validates against the manifest. The digest excludes volatile top-level `generated_at`, so the same schema classes can be saved and loaded after a later recompilation timestamp. Mismatch:

```text
WorkspaceRuntimeError: workspace schema_digest mismatch: manifest='sha256:...',
expected='sha256:...'
```

If the workspace contains a legacy `registry/` directory, load tells you to run `python -m factgraph migrate-workspace <path>` first.

### 3.5 In-memory variant

`FactGraph.create(schema_classes=[...])` without `path=` returns a pure in-memory runtime. All Mode A writes work, nothing is persisted. Promote later with `fg.save_workspace(path=...)`.

## 4. Mode B: Database-owned workspace

Mode B is a specialized substrate. It supports two operations: low-level transactional commits via `fg.commit_assertions(...)`, and durable view creation via `db.create_view(...)`. The ergonomic SDK write surface (`fg.entities.*`, `fg.fields.*`, `fg.batch`, `fg.ingest`, `fg.assertions.retract`, `fg.save_workspace`) is not available here — those methods all reject on attached runtimes. If you need ergonomic writes, use Mode A.

`fg.commit_assertions(...)` requires the caller to assemble `AssertionInput` records by hand: resolve `pred_id` from the compiled schema IR, build the `fact_tuple` as `(tag, value)` pairs, attach optional `MetaEntry` rows.

### 4.1 Create

```python
from factgraph.sdk import Database, FactGraph, compile_schema_from_classes

schema_ir = compile_schema_from_classes([User, Order])

db = Database.create("path/to/workspace", schema_ir=schema_ir)
fg = FactGraph.attach(db, schema_classes=[User, Order])
```

`Database.create(path, schema_ir=...)` writes the full Mode B layout (§1) in one call: the manifest, the schema object, the initial tx object, `db/meta.json`, the head ref, and the empty SQLite ledger at `db/assertions.db`.

`FactGraph.attach(db, schema_classes=[...])` compiles `schema_classes`, computes its digest, and checks it against `db.schema_digest`. Mismatch:

```text
SDKStoreError: schema mismatch: Database has schema_digest='sha256:...',
but schema_classes compile to 'sha256:...'
```

`attach(...)` rejects nine keyword arguments that belong to Mode A: `artifact_store_root`, `ledger`, `ledger_path`, `path`, `policy`, `registry`, `registry_root`, `rules`, `workspace_path`.

### 4.2 Reopen

```python
db = Database.open("path/to/workspace", schema_ir=schema_ir)
fg = FactGraph.attach(db, schema_classes=[User, Order])
```

`Database.open(...)` does not accept `:memory:`:

```text
DatabaseError: Database.open does not support ':memory:'
```

### 4.3 The only write entry — `fg.commit_assertions`

`AssertionInput` is the assembly format for a commit:

```python
@dataclass(frozen=True)
class AssertionInput:
    pred_id: str
    fact_tuple: tuple[tuple[str, Any], ...]
    meta: tuple[MetaEntry, ...] = ()
```

`fact_tuple` is a tuple of `(tag, value)` pairs. The first element is conventionally the entity ref; the rest carry the field values for that predicate.

A complete single-assertion commit:

```python
from factgraph.sdk import AssertionInput, MetaEntry

# 1) resolve pred_id from the compiled schema
def field_pred_id(schema_ir, owner_type, field_name):
    for pred in schema_ir["predicates"]:
        if pred.get("owner_type") == owner_type and pred.get("py_field_name") == field_name:
            return pred["pred_id"]
    raise LookupError(f"{owner_type}.{field_name} predicate not found")

user_name_pred = field_pred_id(schema_ir, "User", "name")

# 2) assemble
input = AssertionInput(
    pred_id=user_name_pred,
    fact_tuple=(("entity_ref", "idref_v1:User:u-1"), ("string", "Alice")),
    meta=(MetaEntry("source", "str", "demo"),),
)

# 3) commit
result = fg.commit_assertions([input])
# result.parent_tx_id : the previous head's tx_id
# result.value        : the new DatabaseValue (db_id + tx_id + schema_digest + data_digest)
# result.assertions   : tuple[AssertionRecord, ...]

assert db.head() == result.value  # head has advanced
```

Errors raised by the commit path:

```text
DatabaseError: commit_assertions requires at least one assertion
DuplicateAssertionError: duplicate content-addressed assertion in commit
DuplicateAssertionError: assertion already exists: asrt:...
```

### 4.4 View creation — the main current capability

```python
view = db.create_view(
    name="snap-2026-06",
    asrt_ids=["asrt:abc...", "asrt:def..."],
)
```

`view` is a Database-layer `FrozenAssertionSet` (6 fields: `name`, `db_id`, `base_tx_id`, `schema_digest`, `asrt_ids: tuple[str, ...]`, `view_digest`). The call writes a content-addressed JSON object at `<workspace_root>/views/<view_digest>.json` and is durable for as long as the workspace exists.

In-memory Databases reject this:

```text
DatabaseError: durable view persistence requires a new-layout Database workspace
```

There is also a session-local SDK-layer `FrozenAssertionSet` returned by `fg.assertion_views.create(...)` in Mode A (2 fields: `name`, `asrt_ids: frozenset[str]`). The two types share a class name but are distinct dataclasses with different schemas; the SDK module renames the Database one to `DatabaseFrozenAssertionSet` internally to keep them disambiguated.

### 4.5 View-scoped attach (read-only)

```python
view = db.create_view(name="snap", asrt_ids=[...])
fg_view = FactGraph.attach(db, schema_classes=[...], view=view)
```

The view-scoped runtime sees only the assertions in `view.asrt_ids`. All writes are rejected, including `fg.commit_assertions(...)`:

```text
SDKStoreError: fg.commit_assertions(...) is not available on
FactGraph.attach(db, view=view) runtimes; view-attached runtimes are read-only
```

Reads work as on a regular attach.

## 5. Choosing a mode

| You want to ... | Use |
|---|---|
| Build a graph with ergonomic SDK writes, save it, load it later | **Mode A** |
| Single-process, no persistence | **Mode A** in-memory variant |
| Build a durable, content-addressed view object that other processes can read | **Mode B** + `db.create_view(...)` |
| Read a database at a specific view snapshot | **Mode B** with `view=` |
| Track `db_id` / `tx_id` explicitly for replication or audit | **Mode B** |
| Anything else | **Mode A** |

Once a workspace is created in one mode, it cannot be opened in the other (see §2 "Disk formats are incompatible"). Treat the mode as a workspace-level commitment made at create time.

## 6. Reference

### 6.1 Class and method signatures

```python
# Mode A
FactGraph.create(
    schema_classes: list[type[Entity]],
    *,
    ledger: Ledger | None = None,
    ledger_path: str | None = None,
    path: str | Path | None = None,
    artifact_store_root: str | None = None,
    default_row_format: str | None = None,
) -> FactGraph

fg.save_workspace(path: str | Path | None = None) -> dict[str, Any]

FactGraph.load_workspace(
    path: str | Path,
    *,
    schema_classes: list[type[Entity]],
    default_row_format: str | None = None,
) -> FactGraph

# Mode B
Database.create(path: str | Path = ":memory:", *, schema_ir: dict) -> Database
Database.open(path: str | Path, *, schema_ir: dict) -> Database
db.head() -> DatabaseValue
db.commit_assertions(assertions: Sequence[AssertionInput]) -> CommitResult
db.create_view(name: str, asrt_ids: Iterable[str], *, base: DatabaseValue | None = None) -> FrozenAssertionSet

FactGraph.attach(
    db: Database,
    *,
    schema_classes: list[type[Entity]],
    view: FrozenAssertionSet | None = None,
    default_row_format: str | None = None,
    # rejects: artifact_store_root, ledger, ledger_path, path, policy,
    #          registry, registry_root, rules, workspace_path
) -> FactGraph

fg.commit_assertions(assertions: Sequence[AssertionInput]) -> CommitResult
```

### 6.2 Returned types

```python
@dataclass(frozen=True)
class DatabaseValue:
    db_id: str
    tx_id: str
    schema_digest: str
    data_digest: str

@dataclass(frozen=True)
class CommitResult:
    parent_tx_id: str               # previous head's tx_id
    value: DatabaseValue             # new head
    assertions: tuple[AssertionRecord, ...]

# factgraph.core.store.database.FrozenAssertionSet
@dataclass(frozen=True)
class FrozenAssertionSet:
    name: str
    db_id: str
    base_tx_id: str
    schema_digest: str
    asrt_ids: tuple[str, ...]
    view_digest: str

# factgraph.sdk.FrozenAssertionSet — distinct class, same name
@dataclass(frozen=True)
class FrozenAssertionSet:
    name: str
    asrt_ids: frozenset[str]

@dataclass(frozen=True)
class AssertionInput:
    pred_id: str
    fact_tuple: tuple[tuple[str, Any], ...]
    meta: tuple[MetaEntry, ...] = ()

@dataclass(frozen=True)
class MetaEntry:
    key: str
    kind: str
    value: Any
```

### 6.3 Manifest schema

Both modes write `factgraph_workspace.json` at the workspace root. The payloads differ.

Mode A payload (from `application/workspace_runtime.py`):

```json
{
  "factgraph_workspace_version": "1",
  "save_scope": "level_4",
  "schema_digest": "sha256:...",
  "components": {"ledger": "ledger.db", "db": "db/", "views": "views/"},
  "created_at": "<ISO timestamp>",
  "last_saved_at": "<ISO timestamp>"
}
```

Mode B payload (from `core/store/database.py`):

```json
{
  "factgraph_workspace_version": "<database-layer version>",
  "components": {"db": "db/", "views": "views/"}
}
```

`validate_workspace_manifest` (used by `FactGraph.load_workspace`) checks that `components.ledger == "ledger.db"`. Mode B manifests fail this check.

### 6.4 Errors

| Raised by | Type | Message |
|---|---|---|
| `Database.open(":memory:", ...)` | `DatabaseError` | `Database.open does not support ':memory:'` |
| `db.commit_assertions([])` | `DatabaseError` | `commit_assertions requires at least one assertion` |
| `db.commit_assertions(...)` with duplicate | `DuplicateAssertionError` | `duplicate content-addressed assertion in commit` or `assertion already exists: asrt:...` |
| `db.create_view(...)` on `:memory:` | `DatabaseError` | `durable view persistence requires a new-layout Database workspace` |
| `FactGraph.attach(db, ...)` with non-Database `db` | `SDKStoreError` | `FactGraph.attach(db) expects a Database instance` |
| `FactGraph.attach(db, schema_classes=...)` digest mismatch | `SDKStoreError` | `schema mismatch: Database has schema_digest=..., but schema_classes compile to ...` |
| `FactGraph.attach(db, **rejected_kwarg=...)` | `SDKStoreError` | `FactGraph.attach(...) does not accept keyword(s): <list>` |
| `fg.commit_assertions(...)` on non-attached | `SDKStoreError` | `fg.commit_assertions(...) is only available on FactGraph.attach(db) runtimes; use fg.fields.set / fg.fields.add for non-attached SDKStores` |
| `fg.commit_assertions(...)` on view-attached | `SDKStoreError` | `fg.commit_assertions(...) is not available on FactGraph.attach(db, view=view) runtimes; view-attached runtimes are read-only` |
| ergonomic write on attached | `SDKStoreError` | `attached FactGraph runtimes route writes only through fg.commit_assertions(...); <method> is not available on attached runtimes` |
| `fg.save_workspace()` with no path bound | `SDKStoreError` | `workspace path not bound; pass fg.save_workspace(path=...) or create with FactGraph.create(path=...)` |
| `FactGraph.load_workspace(...)` digest mismatch | `WorkspaceRuntimeError` | `workspace schema_digest mismatch: manifest=..., expected=...` |
| `FactGraph.load_workspace(...)` on Mode B workspace | `WorkspaceRuntimeError` | `workspace manifest ledger component mismatch` |
| `FactGraph.load_workspace(...)` with legacy `registry/` | `SDKStoreError` | (instructs `python -m factgraph migrate-workspace <path>`) |

### 6.5 Schema strong correspondence

Two validation sites enforce `schema_digest(compile_schema_from_classes(schema_classes)) == workspace_schema_digest` but raise different error types and messages. The comparison is schema-identity based: top-level `generated_at` metadata may differ between the stored schema object and the freshly compiled schema IR, while structural schema changes still fail.

| Site | File | Compared against | Error type | Error message |
|---|---|---|---|---|
| `FactGraph.attach(db, schema_classes=...)` | `sdk/store.py:1755-1761` | `db.schema_digest` | `SDKStoreError` | `schema mismatch: Database has schema_digest=..., but schema_classes compile to ...` |
| `FactGraph.load_workspace(path, schema_classes=...)` | `application/workspace_runtime.py:106-109` | manifest `schema_digest` field | `WorkspaceRuntimeError` | `workspace schema_digest mismatch: manifest=..., expected=...` |

`Database.create(path, schema_ir=...)` and `Database.open(path, schema_ir=...)` take a pre-compiled schema IR. They compute the digest from the IR for storage and for the open-time validation.
