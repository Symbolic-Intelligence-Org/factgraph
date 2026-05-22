# Q2 Decision: FactGraph attach Lifecycle

- Status: proposed for user review
- Created: 2026-05-20
- Branch: `v0.1-q2-attach-lifecycle-decision-2026-05-20`
- Inputs:
  - `docs/decisions/2026-05-20_q1-database-class-boundary-decision.md`
  - `docs/decisions/2026-05-20_q3-tx-identity-primitives-decision.md`
  - `docs/decisions/2026-05-20_q7-assertionrecord-shape-reconciliation-decision.md`
  - `docs/decisions/2026-05-20_q8-savedrule-existence-governance-decision.md`
  - `docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md`
  - `docs/references/working/design-points/database-view-fg-layered-architecture.zh.md`
  - `feedback_preflight_code_audit_required.md`
  - `feedback_audit_execution_discipline.md`
- Scope: pick `FactGraph.attach(db)` lifecycle pattern — distinct from constructors vs rename of `SDKStore.load(...)`;close audit §8 Q2. Cover the **core lifecycle pattern**: where `attach` lives, what it consumes, what read/write boundary it produces.
- Non-scope: Q4 (FrozenAssertionView shape), Q5 (view↔is_active composition), I5 (specific `as_of(tx_id)` snapshot signature beyond noting Q2 unblocks it), I6 (specific `view=` filter signature beyond noting Q4 dependency), detach semantics, concurrency model details beyond the per-form multi-attach allowance.

## 1. Decision

Q2 chooses **option (a) — `attach(db)` is a NEW lifecycle distinct from constructors**.

The core lifecycle pattern:

```text
# Phase 1: Database obtained via Q1-owned constructors (not Q2 scope)
db = Database.create(path=..., schema_ir=...)   # or Database.open(path=...)

# Phase 2: FactGraph runtime binding (Q2 scope) — three attach forms
fg       = FactGraph.attach(db)                       # current head, writable
fg_ro    = FactGraph.attach(db.as_of(tx_id))          # snapshot, read-only
fg_view  = FactGraph.attach(db, view=view)            # view-scoped, read-only
```

`attach` is a class-method-style constructor on `FactGraph` (`SDKStore`) that takes a `Database` object (and optionally a snapshot reference or view-scope argument) and returns a runtime-bound `FactGraph` instance.

The **three attach forms have different read/write semantics**, locked verbatim from design §9.1-§9.2:

| Form | `writable` | Write behavior | Source |
|---|---|---|---|
| `FactGraph.attach(db)` | yes | commits to `db` current head | design line 401 + line 419 |
| `FactGraph.attach(db.as_of(tx_id))` | no | raises `ReadOnlyAttachmentError` | design line 407 + line 420 |
| `FactGraph.attach(db, view=view)` | no | raises `ReadOnlyAttachmentError` | design line 413 + line 421 |

The design's "scoped runtime read-only" constraint (A14) applies specifically to the snapshot + view-scoped forms, NOT to the base `attach(db)` form. The base form is the writable runtime against current head.

Database lifecycle (creation, opening, persistence) is owned by Q1's `Database` boundary;`attach` is only the runtime-binding step.

The shipped constructors `SDKStore.create / from_schema_classes / load` (`src/factgraph/sdk/store.py:783-895`) remain as compatibility constructors during migration. They are not the design-target lifecycle and may later be refactored to internally route through `Database.create / Database.open + FactGraph.attach(db)`, but that refactor is blueprint-level work, not Q2.

## 2. Lifecycle Properties

### 2.1 `attach` consumes a `Database` object, not a path

`FactGraph.attach(db)` accepts a `Database` instance as its primary argument, not a filesystem path. This is the key separation from `SDKStore.load(path, schema_classes)`.

Rationale: Q1 established `Database` as a new layer above `Ledger`. If `attach` took a path, Database would be implicit (created internally) and the Q1-established separation would collapse. By requiring an explicit `Database` argument, the lifecycle stays in two phases — Database creation/opening is owned by Q1's surface, runtime binding is owned by Q2.

### 2.2 Read/write semantics are per-form

Per design §9.2 line 419-421 (write rules table), the three attach forms have distinct write semantics:

- **`attach(db)` base form is writable**. It binds to `db` current head and permits write operations that commit to `db` current head. The exact write API surface (whether the attached FactGraph exposes `fg.commit_assertions(...)` directly, or whether it exposes `db` for callers to use `db.commit_assertions(...)`, or both) is blueprint-level work that consumes Q2 + Q1. Q2 commits to: `attach(db)` returns a writable runtime;writes commit to the Q1 `Database` boundary at current head.
- **`attach(db.as_of(tx_id))` snapshot form is read-only**. Per design line 407 + line 420, this form has `writable=False` and all write paths raise `ReadOnlyAttachmentError`. Snapshot is immutable by construction.
- **`attach(db, view=view)` scoped form is read-only**. Per design line 413 + line 421, this form materializes `view.base_tx_id`'s snapshot and attaches a scoped read-only runtime. All write paths raise `ReadOnlyAttachmentError`.

**A14 ship-gate applies only to the scoped (snapshot + view) forms**. Per design A14 (line 733) "attach-to-view / attach-to-snapshot 与 read-only enforcement 必须同 ship" — A14's "read-only enforcement" requirement is specifically about the two scoped forms, NOT the base form. Per design Step 5 (line 685-693), the ship-gate is explicit: `FactGraph.attach(db, view=view)` and `FactGraph.attach(db.as_of(tx_id))` must not ship before read-only enforcement is implemented;if they ship earlier, they must default `writable=False` and raise `ReadOnlyAttachmentError` on all write paths.

The base `attach(db)` form does not have this ship-gate — it is writable from the start.

### 2.3 `attach` signature does not contain `rules=`

Per design A15 (D), confirmed via Q8 (A15-A-persisted handled via SavedRule governance): `attach(...)` does not accept a `rules=` parameter. Rules live in user Python code (per A20 literal, locked by Q8) and reach the runtime via in-memory `Rule(...)` / `Inference(...)` construction + `_register_rule_dependencies` + `RuleRegistry` (the runtime path Q8 explicitly retained).

`attach` therefore does not have a rule-loading responsibility. Future blueprints that wire rules into an attached runtime must use the runtime in-memory path Q8 blessed, NOT a `rules=` attach parameter.

### 2.4 Multi-attach concurrency

Q2's lifecycle permits multiple `FactGraph` instances to attach to the same `Database`. The concurrency model splits by form:

- **Multiple read-only attaches (snapshot + view forms) safely coexist**. They bind to immutable snapshots (`db.as_of(tx_id)`) or view-pinned snapshots (`db, view=view` materializes `view.base_tx_id`), so they cannot interfere with each other or with Database head writes.
- **Writable base-form attach (`attach(db)`) concurrency is blueprint-level**. Whether multiple writable attaches can coexist (and if so, whether commits serialize through Database, whether attached FactGraphs see each others' head advances, etc.) is a downstream model decision. Q2 does not lock this. Implementation may start with single-writable-attach-per-Database semantics and relax later, or pick a stronger model from day one;both are open per Q2.

Q2 commits to: the lifecycle pattern accommodates multi-attach;detailed concurrency invariants (head advancement visibility, write serialization, snapshot consistency across simultaneous writable attaches) are blueprint-level.

### 2.5 Snapshot and view variants — read/write status locked, signature details deferred

Q2 LOCKS the read/write status for the snapshot and view variants (per §2.2: both are read-only with `ReadOnlyAttachmentError` on write paths). Q2 DEFERS the parameter shape details:

- **`FactGraph.attach(db.as_of(tx_id))` (snapshot attach per I5)**: `db.as_of(tx_id)` is a Database method (per Q1 + Q3 ownership) that returns a snapshot-bound Database-like object. `attach` accepts it and returns a read-only runtime. The exact `as_of(...)` method signature on Database is Q1-owned follow-up;the snapshot semantics (e.g., what immutability invariants the snapshot guarantees) are blueprint-level.
- **`FactGraph.attach(db, view=view)` (view-scoped attach per I6)**: `view=` parameter shape depends on Q4 (FrozenAssertionView shape resolution). Q2 commits to: `attach` accepts an optional view scope when Q4 closes, and the resulting runtime is read-only with `view.base_tx_id` materialized;exact parameter shape is a Q4 + I6 follow-up.

Both variants reuse Q2's "attach takes Database" core pattern PLUS add read-only enforcement per A14. The base `attach(db)` form is the only writable variant.

## 3. Rejected Alternatives

### 3.1 Option (b) — `attach(db)` is a rename of `SDKStore.load(path, schema_classes)`

Rejected.

Reason: option (b) collapses `Database` back into `SDKStore`'s lifecycle. `SDKStore.load(path, schema_classes)` (`src/factgraph/sdk/store.py:860-895`) takes a filesystem path + schema classes, opens the workspace, creates a `Ledger` from `paths.ledger`, and returns a fully-bound `SDKStore`. There is no separate "Database object" in this flow — the path is the only handle.

Renaming `load` to `attach` does not change this. It would merely give the existing lifecycle a new name while erasing Q1's design intent (Database as an independent object). Per Q1 §4.2: "if `attach(db)` is introduced, `db` means the new `Database` boundary, not raw `Ledger`" — option (b) violates this by making `db` implicitly a path-derived value rather than an explicit Database object.

Per `feedback_audit_execution_discipline` Rule 2, Q2 cannot soften Q1's strict Database-above-Ledger separation to fit shipped reality. Option (b) is exactly that softening.

### 3.2 Sub-option: `attach` as instance method on a pre-existing FactGraph

Considered and rejected.

Pattern: `fg = FactGraph(...); fg.attach(db)` — caller constructs an empty FactGraph first, then attaches a Database.

Reason: this introduces an unbound FactGraph state that has no meaningful semantics (no Database to read/eval against). It complicates lifecycle reasoning and serves no use case Q2 needs to cover. Class-method form `FactGraph.attach(db)` is simpler and matches the "new lifecycle distinct from constructors" framing.

If future use cases require re-binding (e.g., detach + re-attach to a different Database), they can be added by separate decision. Q2 v1 does not require this.

## 4. Supporting Evidence

### 4.1 Design references (verified literal per Rule 1)

- §9.1 lines 397-413 (attach 模式): three forms with `writable=True` (base), `writable=False` (snapshot), and scoped read-only (view-scoped materializes `view.base_tx_id`)
- §9.2 lines 417-423 (写入规则 table): base form `writable=yes` commits to db current head;snapshot + view forms `writable=no` raise `ReadOnlyAttachmentError`. "writable sub-fg 必须等 fork/merge/write-back 语义单独落定后再开放" (writable sub-fg deferred per §17).
- §16 Step 5 lines 685-693 (implementation roadmap): ship-gate `FactGraph.attach(db, view=view) 与 FactGraph.attach(db.as_of(tx_id)) 不能早于 read-only enforcement 发布`. If they ship earlier, must default `writable=False` and raise `ReadOnlyAttachmentError` on all write paths. Base `attach(db)` form has no such ship-gate.
- §18 A14 (line 733): "attach-to-view / attach-to-snapshot 与 read-only enforcement 必须同 ship;禁止出现 scoped runtime 可写的 transient release". A14 is SPECIFICALLY about scoped (view + snapshot) forms — "scoped runtime" is the design's term for these. The base `attach(db)` form is NOT a "scoped runtime" and is NOT constrained by A14's read-only enforcement.
- §18 A15 (line 734): "...`FactGraph.attach(...)` 签名不含 `rules=`...". This signature constraint is form-independent — applies to all three attach forms equally.
- §18 A6: "attach 到 `DatabaseValue` 或 `FrozenAssertionView` 的 runtime 第一版 read-only" — this is design intent for the scoped forms;consistent with §9.2 table.

Key clarification: the design has a single attach API with three forms, of which two are read-only (snapshot + view-scoped). The base form is writable. Q2 must NOT over-apply A14's "scoped runtime read-only" constraint to the base form.

### 4.2 Shipped constructor surface

Shipped `SDKStore` has three constructors (`src/factgraph/sdk/store.py`):

| Constructor | File:Line | Lifecycle |
|---|---|---|
| `SDKStore.create(schema_classes, *, ledger=None, ledger_path=None, path=None, ...)` | `:783-833` | Creates new SDKStore;may use existing ledger or create fresh;optional workspace path |
| `SDKStore.from_schema_classes(classes, *, ledger=None, ledger_path=None, ...)` | `:837-857` | Creates SDKStore from entity classes;simpler signature than `create` |
| `SDKStore.load(path, *, schema_classes=None, default_row_format=None)` | `:860-895` | Loads saved workspace from disk;validates schema digest |

All 3 produce a fully-bound SDKStore in one step (Ledger creation + schema + workspace path + all managers, see `_from_schema_classes_impl` at `:716-777`). There is no two-phase "open storage then bind runtime" separation.

Q2's `attach(db)` introduces that two-phase separation, consistent with Q1's "Database above Ledger" boundary.

### 4.3 Q1 attach guidance

Q1 §4.2: "Q1 does not decide `FactGraph.attach(...)`. It only establishes that if `attach(db)` is introduced, `db` means the new `Database` boundary, not raw `Ledger`."

Q2 honors this: `db` is a `Database` object (Q1's new layer), not a `Ledger` reference and not a filesystem path.

### 4.4 Q8 runtime-path retention

Q8 §8 criterion 9: "Do NOT remove the runtime in-memory `RuleRegistry` mechanism — it is the design-blessed path going forward."

Q2 honors this: `attach(db)` does not load rules from any persistence layer (no `rules=` parameter per A15-D). Rule binding remains the runtime in-memory path Q8 retained.

## 5. Consequences

### 5.1 Q1 Database boundary preserved

Q1 chose Database as a new layer above Ledger. Q2 preserves this by requiring `attach(db)` to take a Database object explicitly. No collapse back into SDKStore lifecycle.

### 5.2 Q3 / Q7 unaffected

Q3 (transaction identity primitives) and Q7 (AssertionRecord shape) operate at the storage/identity layer. Q2 operates at the runtime-binding layer. No interaction.

`tx_id` (Q3) becomes relevant for `attach(db.as_of(tx_id))` — but that snapshot signature is I5 follow-up, not Q2 scope. Q2 only commits to: the attach lifecycle can accept snapshot-bound Database-like objects when Q1/Q3 produce them.

### 5.3 Q4 unblocked for view-scoped attach signature

Q2 establishes that `attach` may take an optional view-scope parameter when Q4 closes. The exact parameter shape (e.g., `attach(db, view=view)` vs `attach(db.with_view(view))`) is Q4 + I6 follow-up territory. Q2 commits only to: the lifecycle pattern accommodates view scope.

### 5.4 Q5 unaffected by Q2 directly

Q5 (view↔is_active composition) operates inside view scope semantics. Q2 does not pick a view scope semantics. Q5 remains downstream of Q4, independent of Q2.

### 5.5 Q8 SavedRule layer unaffected

Q8 governs rule persistence (file-backed SavedRule layer). Q2 governs runtime binding. They are mutually orthogonal — Q2 explicitly does NOT add a rules-loading responsibility to `attach`, which would have re-entered Q8 territory.

### 5.6 I4 / I5 / I6 partially unblocked

- **I4** (attach lifecycle absent): Q2 closes the lifecycle pattern decision. Detailed signature work is blueprint-level.
- **I5** (`attach(db.as_of(tx_id))` snapshot): Q2 unblocks by committing to "attach accepts Database-like snapshot objects". Specific `as_of(tx_id)` signature on Database is Q1-owned follow-up;the snapshot semantics are blueprint-level.
- **I6** (`attach(db, view=view)` view scope): Q2 partially unblocks. Full unblocking requires Q4 (view shape).

### 5.7 Shipped constructors become compatibility surface

Following Q1's "compatibility-during-migration" pattern (Q1 §4.4) and Q8's gradual deprecation pattern (Q8 §1):

- `SDKStore.create / from_schema_classes / load` remain as compatibility constructors. They may continue to function during migration.
- The design-target lifecycle for new code is `Database.create / Database.open + FactGraph.attach(db)`.
- Whether shipped constructors get deprecation warnings + a Phase-2 removal (analogous to Q8's SavedRule pattern) is a release-engineering question, not decided by Q2.
- Future blueprints may refactor shipped constructors to internally route through the Q1+Q2 lifecycle, but this is implementation detail.

## 6. Acceptance Criteria For This Decision

Future Q2-dependent blueprints must obey:

1. Do introduce `FactGraph.attach(db)` as a class-method-style constructor distinct from existing `SDKStore.create / from_schema_classes / load`.
2. Do require `attach` to take a `Database` object (Q1 boundary), not a filesystem path and not a raw `Ledger`.
3. Do honor the **per-form read/write split** locked from design §9.2:
   - `attach(db)` base form is **writable**;writes commit to `db` current head via the Q1 `Database` boundary. Exact write API surface is blueprint-level.
   - `attach(db.as_of(tx_id))` snapshot form is **read-only**;all write paths raise `ReadOnlyAttachmentError`.
   - `attach(db, view=view)` view-scoped form is **read-only**;materializes `view.base_tx_id`;all write paths raise `ReadOnlyAttachmentError`.
4. Do NOT include `rules=` in the `attach(...)` signature per A15 (D), regardless of form. Rule binding uses the runtime in-memory `RuleRegistry` path Q8 retained.
5. Do permit multiple `FactGraph` instances to attach to the same `Database`. Read-only forms (snapshot + view) compose safely because they pin to immutable snapshots. Concurrency model for multiple writable base-form attaches is blueprint-level (Q2 does not lock it).
6. Do NOT add an unbound-FactGraph instance state followed by `fg.attach(db)`. `attach` is a class-method constructor, not an instance method.
7. Do leave snapshot-attach (`attach(db.as_of(tx_id))`) DETAILED signature to I5 + Q1 snapshot-API follow-up. (The read-only status itself is locked per criterion 3.)
8. Do leave view-scoped attach (`attach(db, view=view)` or equivalent) DETAILED signature to Q4 + I6. (The read-only status itself is locked per criterion 3.)
9. Do NOT collapse `attach` semantics back into a filesystem-path-only signature (option (b) is rejected).
10. Do keep shipped `SDKStore.create / from_schema_classes / load` as compatibility constructors during migration. Their deprecation/removal is a separate release-engineering decision, NOT bundled into Q2.
11. Do NOT auto-create a `Database` inside `attach` from a path argument. If a user has only a path, they construct `Database.open(path=...)` first (Q1-owned surface), then call `attach(db)`.
12. Do treat detach semantics as out-of-scope for Q2 v1. If a future use case requires detach + re-attach to a different Database, it surfaces as a separate decision.
13. Do honor the **Step 5 ship-gate** (design line 685-693): `attach(db.as_of(tx_id))` and `attach(db, view=view)` MUST NOT ship before read-only enforcement is in place. If they ship before enforcement, they MUST default `writable=False` and raise `ReadOnlyAttachmentError` on every write path. The base `attach(db)` form has no such ship-gate.

## 7. Decision Record

Q2 resolution: **`attach(db)` is a new lifecycle distinct from constructors** (option (a)), with **per-form read/write semantics locked from design §9.2**.

`FactGraph.attach(...)` is a class-method-style constructor that takes a `Database` object (Q1 boundary). Three forms with locked read/write status:

| Form | `writable` | Write behavior |
|---|---|---|
| `FactGraph.attach(db)` | yes | commits to `db` current head via Q1 `Database` boundary |
| `FactGraph.attach(db.as_of(tx_id))` | no | raises `ReadOnlyAttachmentError` |
| `FactGraph.attach(db, view=view)` | no | raises `ReadOnlyAttachmentError`; materializes `view.base_tx_id` |

A14's "scoped runtime read-only" constraint applies to the snapshot + view forms only, NOT to the base form. Step 5 ship-gate (design line 685-693) blocks scoped forms from shipping before read-only enforcement;base form has no such gate.

Signature does not contain `rules=` (A15-D) for any form. Snapshot-attach and view-scoped-attach DETAILED signatures (parameter shapes, `as_of` API on Database, view= shape) are deferred to I5 / Q4 / I6 follow-ups, but their read-only status is locked by Q2.

Shipped `SDKStore.create / from_schema_classes / load` (`sdk/store.py:783-895`) remain as compatibility constructors during migration;they are NOT removed by Q2.

Q1 / Q3 / Q7 / Q8 preserved. Q4 / Q5 unaffected (Q4 still owns view shape;Q5 still owns view↔is_active composition).
