# Q4 Decision: FrozenAssertionView Shape

- Status: proposed for user review
- Created: 2026-05-20
- Branch: `v0.1-q4-frozenassertionview-shape-decision-2026-05-20`
- Inputs:
  - `docs/decisions/2026-05-20_q1-database-class-boundary-decision.md`
  - `docs/decisions/2026-05-20_q2-attach-lifecycle-decision.md`
  - `docs/decisions/2026-05-20_q3-tx-identity-primitives-decision.md`
  - `docs/decisions/2026-05-20_q7-assertionrecord-shape-reconciliation-decision.md`
  - `docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md`
  - `docs/references/working/design-points/database-view-fg-layered-architecture.zh.md`
  - `feedback_preflight_code_audit_required.md`
  - `feedback_audit_execution_discipline.md`
- Scope: resolve audit Q4: shipped 2-field `FrozenAssertionView(name, asrt_ids)` vs design 6-field anchored `FrozenAssertionView(name, db_id, base_tx_id, schema_digest, asrt_ids, view_digest)`.
- Non-scope: Q5 (`view=` scope vs `is_active` composition), view persistence layout (`views/objects/<view_digest>.json`, A18 implementation detail), read/evaluate `view=` API redraft, evidence/evaluate metadata carriers, concrete migration timing for legacy 2-field view objects.

## 1. Decision

Q4 chooses **option (c), with a compatibility boundary**:

1. The design-target `FrozenAssertionView` keeps the existing name and is upgraded to the 6-field anchored shape from the design document.
2. Shipped 2-field `FrozenAssertionView(name, asrt_ids)` is a legacy / compatibility shape, not the design target and not a valid durable view-scope carrier for new `view=` APIs.
3. Q4 does NOT introduce a second public design type such as `AnchoredAssertionView`.

Canonical design-target shape:

```python
@dataclass(frozen=True)
class FrozenAssertionView:
    name: str
    db_id: str
    base_tx_id: str
    schema_digest: str
    asrt_ids: frozenset[str]
    view_digest: str
```

This preserves the design's explicit statement that `FrozenAssertionView` is the v1 concrete DTO / Python type for the `SubsetView` concept, not a second concept beside it.

## 2. Field Semantics

### 2.1 `name`

`name` is a runtime / user-facing label. It is part of the DTO because the SDK has named view ergonomics, but it is NOT part of the view identity.

Consequence: renaming a view label does not change `view_digest` if all anchor fields and `asrt_ids` stay identical.

### 2.2 `db_id`

`db_id` identifies the Database that owns the assertions. It is sourced from Q1's `Database` boundary. A view cannot span databases.

### 2.3 `base_tx_id`

`base_tx_id` is the transaction snapshot that was current when the view was created, or the explicit snapshot used to create it. It is a `tx:<hex>` token per Q3.

The field is named `base_tx_id` rather than `tx_id` because the view is a subset anchored to a base DatabaseValue;it is not itself a new Database transaction.

### 2.4 `schema_digest`

`schema_digest` is the schema digest of the base snapshot. Q3 already locked that this is the existing `sha256:<hex>` schema digest token, not a parallel schema digest algorithm.

### 2.5 `asrt_ids`

`asrt_ids` is the frozen assertion-id universe requested by the caller. It is stored as `frozenset[str]`.

At creation time, every `asrt_id` must exist in the attached base DatabaseValue and must belong to the same `db_id`. Q4 does not decide whether the runtime later intersects this set with active/revocation state;that is Q5.

### 2.6 `view_digest`

`view_digest` is a deterministic `sha256:<hex>` token over the anchored view identity:

```text
subset-view-v1
db_id
base_tx_id
schema_digest
sorted(asrt_ids)
```

`name` is deliberately excluded.

Q4 locks the semantic inputs and token form. The exact byte protocol used to canonicalize these inputs is blueprint-level work, but it must be deterministic, cross-process reproducible, and must not include local paths, object ids, insertion order, process state, timestamps, or SDK registry order.

## 3. Rejected Alternatives

### 3.1 Option (a) — reuse shipped 2-field shape as the design target

Rejected.

Shipped currently has `FrozenAssertionView(name, asrt_ids)` only. Reusing that shape would drop `db_id / base_tx_id / schema_digest / view_digest` from the design and would remove the anchor fields needed for reproducibility, stale detection, cross-doc metadata, and view-scope validation.

Per `feedback_audit_execution_discipline` Rule 2, Q4 must not soften the new design's strict shape to match shipped reality.

### 3.2 Option (b) — rename the design shape to `AnchoredAssertionView`

Rejected.

The design document explicitly says `FrozenAssertionView` is the v1 concrete DTO / Python type name, and that `FrozenAssertionView` implements `SubsetView`. Renaming the design shape would create two view concepts where the design intended one: shipped 2-field `FrozenAssertionView` and a separate anchored type. That would preserve term drift instead of resolving it.

If implementation needs an internal migration helper or adapter class, that is allowed, but the durable public design-target DTO remains `FrozenAssertionView`.

### 3.3 Option (c) — breaking upgrade of shipped shape

Accepted as the design target, with a compatibility boundary.

This is the only option that keeps the design name, preserves the anchor fields, and resolves the shipped-vs-design conflict. It is "breaking" in the sense that new design-target APIs must not treat the 2-field object as sufficient. It does not require an immediate removal of every compatibility constructor or legacy SDK view helper;those migration details are blueprint / release-engineering work.

## 4. Compatibility Boundary

### 4.1 Existing 2-field objects

Existing 2-field `FrozenAssertionView(name, asrt_ids)` values are compatibility artifacts. They may continue to exist behind legacy SDK APIs during migration, but they are not valid inputs to new Database-attached `view=` runtime semantics unless upgraded / anchored.

An implementation may choose one of these compatibility mechanics:

- adapt legacy `fg.views.create(...)` so it can populate anchors when called from a Database-attached runtime;
- reject legacy unanchored views at new `view=` boundaries with a clear error;
- provide an explicit migration / anchoring helper that requires a DatabaseValue source.

Q4 does not choose among those mechanics. Q4 only locks the design-target shape.

### 4.2 `fg.views.create(...)`

The design-target creation path still supports the ergonomic pattern:

```python
records = fg.read.find(User, status="active")
view = fg.views.create("active_users", asrt_ids=[r.asrt_id for r in records])
```

Under Q4, this call can only produce a design-target `FrozenAssertionView` when `fg` is attached to a Database / DatabaseValue that supplies:

- `db_id`
- `base_tx_id`
- `schema_digest`

The caller supplies `name` and `asrt_ids`;the runtime supplies anchors and computes `view_digest`.

### 4.3 Named registry vs view identity

The shipped `_SDKViewsManager` is a named in-memory registry. Q4 keeps the user-facing name field but does not make names part of identity.

Persistent named view registry remains deferred by design. Anonymous content-addressed view persistence (`views/objects/<view_digest>.json`) is A18 / blueprint territory, not Q4.

## 5. Supporting Evidence

### 5.1 Design references

- §3.3 lines 112-122: `SubsetView` is the semantic concept;`FrozenAssertionView` is the v1 concrete DTO / Python type;it participates in reproducibility through `db_id + base_tx_id + schema_digest + view_digest`.
- §5.3 lines 233-242: design-target dataclass has 6 fields: `name / db_id / base_tx_id / schema_digest / asrt_ids / view_digest`.
- §5.3 lines 244-254: `view_digest` is computed from `subset-view-v1 + db_id + base_tx_id + schema_digest + sorted(asrt_ids)`.
- §8.1 lines 373-378: creation reads `db_id / base_tx_id / schema_digest` from current attachment and freezes `asrt_ids`.
- §8.2 lines 382-385: creation validates assertion existence, database membership, and runtime name uniqueness.
- §8.3 lines 387-389: persisted named view can stay out of `fg.save(...)` in the minimum version, but the structure already contains the anchor fields.
- §18 A5 line 724: `FrozenAssertionView` must carry `db_id / base_tx_id / schema_digest / view_digest`.

### 5.2 Shipped references

Shipped `FrozenAssertionView` is currently a 2-field SDK dataclass:

```python
@dataclass(frozen=True)
class FrozenAssertionView:
    name: str
    asrt_ids: frozenset[str]
```

This appears at `src/factgraph/sdk/store.py:88-92`.

The shipped `_SDKViewsManager` (`src/factgraph/sdk/store.py:101-179`) exposes `create / update / delete / get / list`. It stores a process-local `_views` dict and explicitly states that a view "stores assertion ids only" and is "not included in `fg.save(...)` workspace persistence" (`src/factgraph/sdk/store.py:128-131`).

The shipped builder (`src/factgraph/sdk/store.py:2682-2699`) constructs the 2-field shape from `name + asrt_ids` or `name + asrts`.

### 5.3 Audit references

Audit §8 Q4 enumerated the 3 options and identified the collision: shipped 2-field `FrozenAssertionView(name, asrt_ids)` vs design 6-field shape. Audit §9.2 marked I3 / A5 / A18(A) as blocked by Q4.

## 6. Consequences

### 6.1 Q1 / Q3 consumed

Q4 consumes Q1 and Q3 outputs:

- `db_id` comes from Q1's Database boundary.
- `base_tx_id` is a Q3 `tx:<hex>` transaction token.
- `schema_digest` is the existing `sha256:<hex>` schema digest token.

Q4 does not reopen Q1 or Q3.

### 6.2 Q2 view-scoped attach partially unblocked

Q2 already locked that `FactGraph.attach(db, view=view)` is read-only and materializes `view.base_tx_id`. Q4 now provides the `view` DTO shape needed by that form.

Detailed `attach(..., view=...)` parameter typing and validation order remain blueprint-level work.

### 6.3 Q5 unblocked but not answered

Q4 locks the view identity set (`view.asrt_ids`) and its immutable `view_digest`. It does not decide how runtime read/evaluate/explain visibility composes `view.asrt_ids` with shipped `is_active(...)` / revocation behavior.

That remains Q5.

### 6.4 Evidence / evaluate metadata still cross-doc blocked

Q4 supplies `view_digest` as a source value. It does not define `EvaluateResult`, `EvidenceGraph.metadata`, or sibling evidence / rule-expression carrier shapes.

Those remain cross-doc redraft work, as captured in the audit S-series and I10/A10 rows.

### 6.5 Q7 unaffected

Q7 governs assertion record shape. Q4 governs view shape. The only connection is that `FrozenAssertionView.asrt_ids` contains assertion ids whose canonical form was settled by Q3/Q7;Q4 does not reopen assertion payload or record-shape decisions.

### 6.6 Q8 unaffected

Q8 governs SavedRule persistence (rule/inference registry layer). Q4 governs view DTO shape. They are mutually orthogonal — Q4 does not touch rule persistence;Q8 does not touch view shape.

## 7. Acceptance Criteria For This Decision

Future Q4-dependent blueprints must obey:

1. Do make the design-target `FrozenAssertionView` a 6-field frozen DTO: `name / db_id / base_tx_id / schema_digest / asrt_ids / view_digest`.
2. Do NOT drop the 4 anchor fields to preserve the shipped 2-field shape.
3. Do NOT introduce `AnchoredAssertionView` or another durable public design-target type that duplicates `FrozenAssertionView`.
4. Do compute `view_digest` from `subset-view-v1 + db_id + base_tx_id + schema_digest + sorted(asrt_ids)`.
5. Do exclude `name` from `view_digest`.
6. Do require `base_tx_id` to be a Q3 `tx:<hex>` token and `schema_digest` to be the existing `sha256:<hex>` token.
7. Do validate at view creation that every `asrt_id` exists in the base DatabaseValue and belongs to the same `db_id`.
8. Do keep Q5 open: do not decide active-only vs all-asserted visibility in Q4.
9. Do allow legacy 2-field view objects only as compatibility artifacts;they are not valid design-target `view=` carriers unless anchored or explicitly migrated.
10. Do keep persistent named view registry deferred;Q4 decides DTO shape, not registry persistence.

## 8. Decision Record

Q4 resolution: **upgrade `FrozenAssertionView` to the anchored 6-field design-target DTO**.

Accepted shape:

```python
FrozenAssertionView(
    name: str,
    db_id: str,
    base_tx_id: str,
    schema_digest: str,
    asrt_ids: frozenset[str],
    view_digest: str,
)
```

`view_digest` is a deterministic `sha256:<hex>` digest over `subset-view-v1 + db_id + base_tx_id + schema_digest + sorted(asrt_ids)`. `name` is not part of identity.

Shipped 2-field `FrozenAssertionView(name, asrt_ids)` remains a compatibility artifact during migration, not the design target. Q4 rejects both dropping anchor fields and renaming the anchored design shape to a second public type.

Q1 / Q3 / Q2 consumed;Q5 remains next for view visibility semantics.
