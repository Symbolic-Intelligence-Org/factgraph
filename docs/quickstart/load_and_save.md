# Load and save: the v0.3 workspace lifecycle

A durable FactGraph workspace has one physical format and one transactional
history. Whether the SDK creates the `Database` for you or you attach to a
caller-owned `Database`, canonical writes use the same SQLite transaction and
advance the same head.

The most important lifecycle rule is that durable writes are **write-through**:
when a mutation call returns successfully, its facts and new head are already
durable. `save_workspace()` is not a persistence or commit boundary.

## 1. Choose an entry point

| Entry point | Database owner | Writable? | Durable? |
|---|---|---|---|
| `FactGraph.create(path=..., schema_classes=[...])` | SDK runtime | yes | yes |
| `FactGraph.load_workspace(path, schema_classes=[...])` | SDK runtime | yes | yes |
| `Database.create/open(...)` + `FactGraph.attach(db, ...)` | caller | yes, for a base attach | yes |
| `FactGraph.attach(db, ..., view=view)` | caller | no; the view runtime is read-only | yes |
| `FactGraph.create(schema_classes=[...])` without `path=` | SDK runtime | yes | no; in-memory only |

`FactGraph.from_schema_classes(...)` is a lower-level unmanaged `Ledger`
compatibility lifecycle. It is not the v0.3 durable workspace lifecycle. In
particular, its legacy raw entity-reference ingest fallback does not apply to
Database-backed created, loaded, or attached graphs.

### 1.1 SDK-owned create and load

Use a context manager so the workspace lock is released promptly:

```python
from factgraph.sdk import FactGraph

with FactGraph.create(
    path="path/to/workspace",
    schema_classes=[User, Order],
) as fg:
    user = fg.entities.create(User, user_id="u-1")
    fg.fields.set(User.name, user, "Alice")
    fg.fields.set(User.name, user, "Alicia")

with FactGraph.load_workspace(
    "path/to/workspace",
    schema_classes=[User, Order],
) as fg:
    assert fg.entities.get(User, user_id="u-1").name == "Alicia"
```

The supplied classes are compiled and checked against the schema object and
current schema digest recorded by the Database. Class-less dynamic load is not
supported. A mismatching class set fails closed.

### 1.2 Caller-owned Database and attach

Attach is useful when the caller needs direct access to `db.head()`, low-level
commit results, or durable frozen views:

```python
from factgraph.sdk import Database, FactGraph, compile_schema_from_classes

schema_classes = [User, Order]
schema_ir = compile_schema_from_classes(schema_classes)

with Database.create("path/to/workspace", schema_ir=schema_ir) as db:
    fg = FactGraph.attach(db, schema_classes=schema_classes)
    user = fg.entities.create(User, user_id="u-1")
    fg.fields.set(User.name, user, "Alice")
    head = db.head()
```

A base attach supports the same ergonomic write surface as SDK-owned
create/load: `fg.entities.*`, `fg.fields.*`, `fg.assertions.*`, `fg.batch`,
ingest, metadata append, and additive `fg.schema.*` changes. The caller, not
the attached `FactGraph`, owns and closes the `Database`.

`FactGraph.attach(...)` accepts attach-specific options only. Lifecycle and
storage options such as `path=`, `ledger=`, `ledger_path=`, and
`registry_root=` are rejected rather than silently ignored.

### 1.3 In-memory graphs

Omitting `path=` creates an in-memory Database:

```python
with FactGraph.create(schema_classes=[User]) as fg:
    fg.entities.create(User, user_id="temporary")
```

Its contents disappear when the runtime closes. It cannot later be promoted
to a durable workspace with `save_workspace(path=...)`; create a durable graph
up front or explicitly transfer the data through supported write APIs.

## 2. Writes, commits, and the head

Every logical commit is one SQLite transaction. Assertion rows, revocations,
metadata, schema history, the current schema digest, state commitment, and
head update succeed or roll back together.

- A normal SDK mutation is one transaction per call.
- Operations inside `fg.batch(...)` are committed as one transaction.
- A bulk-ingest batch is one transaction.
- An additive schema transition is its own `schema_change` transaction.
- A no-op or rejected operation does not advance the head.

The SDK also exposes `fg.commit_assertions(...)` and `fg.commit_changes(...)`
on writable Database-backed graphs. These accept low-level protocol DTOs and
are advanced mechanisms, not a second workspace format. Raw schema-transition
DTOs are deliberately not part of the public SDK namespace; SDK schema policy
is enforced through additive-only `fg.schema.register/extend/apply`.

`db.head()` returns:

```python
@dataclass(frozen=True)
class DatabaseValue:
    db_id: str
    tx_id: str
    schema_digest: str
    state_digest: str
    digest_scheme: str
    tx_seq: int

    @property
    def data_digest(self) -> str: ...  # v0.2 compatibility alias for state_digest
```

`state_digest` is an order-independent LtHash commitment to the active factual
assertion ids and their content digests. The transaction chain separately
commits each normalized delta, so different histories that reach the same
active state retain different `tx_id` histories.

## 3. What `save_workspace()` means now

For a writable durable graph, `fg.save_workspace()` updates only
`db/meta.json:last_saved_at_epoch_ns`. It does not write pending facts (there
are none), advance the head, rewrite the manifest, or create a transaction.

```python
info = fg.save_workspace()
print(info["last_saved_at_epoch_ns"])
```

Callers using `FactGraph.attach(db, ...)` can compare `db.head()` before and
after this call to verify that the head is unchanged.

Passing the already-bound path is accepted. Passing another path is rejected:
save cannot copy or rebind a workspace. It also cannot turn an in-memory graph
into a durable one.

The old pattern “load → modify → omit save to discard” therefore no longer
works. For a dry run or sandbox, first close the workspace, copy the entire
directory, and open the copy. Do not copy a live workspace.

## 4. Ownership, locking, and close

Every durable `Database.create/open` acquires a non-blocking exclusive writer
lock for the lifetime of the Database. v0.3 has no concurrent read-only open
channel: a second open of the same workspace, even one intended only for
reading, fails explicitly.

- `FactGraph.create(path=...)` and `FactGraph.load_workspace(...)` own their
  Database. `fg.close()` or context-manager exit closes it and releases the
  lock.
- `FactGraph.attach(db, ...)` does not own the caller's Database. Closing the
  attached graph does not replace the caller's responsibility to close `db`.
- `close()` is idempotent.
- Writing through an SDK-owned graph after close raises `SDKStoreError` with
  `code="GRAPH_CLOSED"` and lifecycle guidance.

Arrange multi-worker deployments around a single durable writer. A second
process cannot use `FactGraph.load_workspace(...)` as a read-only observer.

## 5. On-disk format

Both SDK-owned and caller-owned durable lifecycles use this layout:

```text
workspace/
  factgraph_workspace.json
  db/
    assertions.db
    meta.json
    writer.lock
    objects/
      schema/<64hex>.json
      tx/<64hex>.json
  views/
    objects/<64hex>.json
```

`factgraph_workspace.json` contains version `"1"` and only the `db/` and
`views/` component locations. It does not contain a top-level
`schema_digest`. The authoritative current head, Database id, schema digest,
state digest, digest scheme, and transaction sequence live together in the
`ledger_meta` table inside `db/assertions.db`; there is no `db/refs/head.txt`.

Canonical schema objects and transaction objects are content-addressed and
write-once. A successful additive schema change writes the new schema object
and advances the Database's schema digest in the same logical commit. The
manifest does not need a later save to catch up.

## 6. Durable frozen views

Create a view from a durable Database, then attach it read-only:

```python
with Database.open("path/to/workspace", schema_ir=schema_ir) as db:
    view = db.create_view(name="review-set", asrt_ids=["asrt:..."])
    fg_view = FactGraph.attach(db, schema_classes=[User, Order], view=view)
    rows = fg_view.assertions.all()
```

The view object is stored at `views/objects/<view_digest>.json`. It records the
Database id, base transaction, schema digest, and assertion-id membership.
In-memory Databases cannot persist views.

A view-attached runtime is read-only. Any write entry fails directly with a
message that the method is unavailable and view-attached runtimes are
read-only; it is not reported as a schema-policy or non-additive error.

## 7. Migrating a v0.2 workspace

Migration is explicit and opt-in. Close every process using the source, then
inspect or migrate it with:

```bash
python -m factgraph migrate-workspace path/to/workspace --dry-run
python -m factgraph migrate-workspace path/to/workspace
```

The supported source is a complete v0.2 workspace whose authoritative SQLite
file is `ledger.db`. The command stages and verifies a v0.3 replacement,
preserves assertion/revocation rows and ids, and writes an auditable genesis
repair anchor because the old per-commit history cannot be reconstructed.
`FactGraph.load_workspace(...)` never migrates automatically.

By default the complete old workspace is archived inside the replacement as
`workspace.legacy.<UTC timestamp>/`. Use `--no-archive` only when that backup
is intentionally unnecessary.

### 7.1 Interrupted replacement recovery

During the two-rename replacement window, the complete source is temporarily
stored in a visible sibling named
`<workspace-name>.legacy-<UTC timestamp>`. If the process stops there, rerun
the same command. It returns `workspace_recovery_required` with
`recovery_candidates` and `replacement_present` instead of guessing which copy
to keep.

- If the requested workspace is missing, verify a candidate, rename it back
  to the requested path, then rerun migration.
- If both a replacement and candidate exist, verify the replacement, then
  explicitly archive or remove the sibling.

A registry-only directory or torn create is reported as
`workspace_incomplete` with recreate guidance. It is not treated as a
migratable v0.2 workspace.

## 8. Common failures

| Situation | Result and recovery |
|---|---|
| Schema classes do not match the current Database schema | fail-closed schema mismatch; supply the current classes |
| A second durable open is attempted | exclusive-lock error; close the current owner first |
| A write is attempted through a view attach | direct read-only `SDKStoreError` |
| A write is attempted after SDK-owned close | `SDKStoreError(code="GRAPH_CLOSED")`; create/load a new graph or attach an open Database |
| `save_workspace(path=other)` is used as copy/export | rejected; close and copy the whole directory instead |
| A v0.2 `ledger.db` workspace is loaded | run `python -m factgraph migrate-workspace <path>` |
| A torn or registry-only workspace is found | `workspace_incomplete`; recreate rather than looping migration |
| Migration stopped during replacement | follow `workspace_recovery_required.recovery_candidates` |

## 9. Current boundaries

The v0.3 lifecycle does not promise lazy loading, a SQL-first query surface,
or multiprocess concurrent readers. It also does not reconstruct a missing
content-addressed transaction object from an otherwise intact ledger; such a
workspace fails closed pending a separately designed re-anchor flow.

For lower-level integrity and repair details, see
[`src/factgraph/core/store/docs/README.md`](../../src/factgraph/core/store/docs/README.md).
For schema evolution, see [`schema_definition.md`](schema_definition.md).
