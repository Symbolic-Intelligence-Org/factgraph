# Preflight Audit — Docs-vs-Shipped Drift Fix (2026-06-02)

- Blueprint: [`workflow/blueprints/active/2026-06-02_docs-vs-shipped-drift-fix.md`](../../blueprints/active/2026-06-02_docs-vs-shipped-drift-fix.md)
- Blueprint Audit Log: [`workflow/blueprints/active/2026-06-02_docs-vs-shipped-drift-fix.audit.md`](../../blueprints/active/2026-06-02_docs-vs-shipped-drift-fix.audit.md)
- Preflight Branch: `v0.2.0-docs-vs-shipped-drift-fix-preflight-2026-06-02` (forked from `646af37e`, blueprint Step 4.2 amend HEAD)
- Audit Mode: line-citation grounded; Step 4.7 author should be able to apply edits without re-opening source files.

## §1 Scope

Inherits blueprint LOCKED scope:

- **In-scope (7 findings)**: F1 / F2 / F3 (database.md 2-class disambiguation, merged at implementation layer per user directive — 3 separate findings preserved here for factual-boundary integrity) + F4 / F5 / F6 / F7 (04_api_surface.en.md §2.5 / §2.6 / §2.12).
- **Deferred to blueprint §10 carry-forward**: F8 / F9 / F10 / F11 — no action this slice.

Step 4.2 amend cite list applied (P2-1 F6 reject mechanism split, P2-2 F4 4-target-shape enumeration, P3-1 F4 source anchor split). All citations below reflect post-Step-4.2 text.

## §2 Method

Per finding, line-citation table with five columns:

| Column | Content |
|---|---|
| Current text | Verbatim text from doc file at cited line (no paraphrase). |
| Code source | Verbatim signature or guard logic from `src/factgraph/sdk/store.py` at cited line. |
| Drift class | (b) small gap / (c) shape conflict per CADENCE classification. |
| Expected text(short form) | Concise replacement intended for the docs table row (keeps API surface tables clean per user directive). |
| Expected sub-prose | Where applicable — narrative paragraph or footnote that lives outside the table row, carrying the detail kept out of the row. |

Step 4.7 author may apply table-row edits and sub-prose edits in the same commit but they are tracked as separate edit cells here.

## §3 PF-R (Required Findings)

### §3.1 PF-R1 — F1 / F2 / F3 merged paragraph rewrite in `docs/official/kernel/quickstart/database.md`

**Cited lines**: `database.md:357-358`.

**Verbatim current text** (`database.md:355-358`):

```markdown
| Surface | Shape | Persistence | Purpose |
| --- | --- | --- | --- |
| `fg.assertion_views.create(...)` | `FrozenAssertionSet` (6 fields: `name`, `db_id`, `base_tx_id`, `schema_digest`, `asrt_ids`, `view_digest`) | In-memory only; SDK-owned anchors (`db_id="db:<sdk>"`, empty `base_tx_id`/`schema_digest`) | Session-local named assertion-id sets |
| `db.create_view(...)` | `FrozenAssertionSet` (same 6-field dataclass) | Durable `views/objects/<view_digest>.json` object; anchored to a real Database head | Database-owned frozen scope object |
```

**Code source** — SDK class definition (`src/factgraph/sdk/store.py:116-119`):

```python
@dataclass(frozen=True)
class FrozenAssertionSet:
    name: str
    asrt_ids: frozenset[str]
```

**Code source** — Database class definition (`src/factgraph/core/store/database.py:74-81`):

```python
@dataclass(frozen=True)
class FrozenAssertionSet:
    name: str
    db_id: str
    base_tx_id: str
    schema_digest: str
    asrt_ids: tuple[str, ...]
    view_digest: str
```

**Code source** — SDK rename import (`src/factgraph/sdk/store.py:85-86`):

```python
from factgraph.core.store.database import (
    FrozenAssertionSet as DatabaseFrozenAssertionSet,
```

**Drift class**: (c) shape conflict — three independent factual claims false.

| Finding | False claim | Reality |
|---|---|---|
| **F1** | SDK `FrozenAssertionSet` has **6 fields** (`name`, `db_id`, `base_tx_id`, `schema_digest`, `asrt_ids`, `view_digest`) | SDK class has **2 fields**: `name: str` + `asrt_ids: frozenset[str]` |
| **F2** | SDK and Database use the **same 6-field dataclass** | Two distinct classes — same name, different schemas — coexist (SDK file imports the Database one with `as DatabaseFrozenAssertionSet` rename to disambiguate) |
| **F3** | SDK returns "SDK-owned anchors (`db_id='db:<sdk>'`, empty `base_tx_id`/`schema_digest`)" | These fields **don't exist** on the SDK class; the claim is unverifiable because the class shape it presupposes is not the shipped shape |

**Expected text (short form)** — rewritten table at `database.md:355-358`:

```markdown
| Surface | Shape | Persistence | Purpose |
| --- | --- | --- | --- |
| `fg.assertion_views.create(...)` | `FrozenAssertionSet` (SDK-layer dataclass, 2 fields: `name`, `asrt_ids: frozenset[str]`) | In-memory only; not written by `fg.save_workspace(...)` | Session-local named assertion-id sets |
| `db.create_view(...)` | `FrozenAssertionSet` (Database-layer dataclass, 6 fields: `name`, `db_id`, `base_tx_id`, `schema_digest`, `asrt_ids: tuple[str, ...]`, `view_digest`) | Durable `views/objects/<view_digest>.json` object; anchored to a real Database head | Database-owned frozen scope object |
```

**Expected sub-prose** — replace the misleading "(same 6-field dataclass)" framing with a paragraph immediately following the table:

```markdown
The two surfaces return **different `FrozenAssertionSet` classes that share a
name but not a schema**. `factgraph.sdk.FrozenAssertionSet` is a 2-field
session-local set; `factgraph.core.store.database.FrozenAssertionSet` is a
6-field Database-anchored object whose extra fields (`db_id`, `base_tx_id`,
`schema_digest`, `view_digest`) tie the set to a specific Database head and
schema version. The SDK module imports the Database class with
`from factgraph.core.store.database import FrozenAssertionSet as
DatabaseFrozenAssertionSet` to keep the two names disambiguated inside the
SDK source; users importing `FrozenAssertionSet` from `factgraph.sdk` always
get the 2-field SDK version.
```

**Implementation note** (per blueprint §5.2): F1+F2+F3 collapse into one edit operation at Step 4.7 — modify the two table rows + insert the sub-prose paragraph immediately after. Blueprint + this preflight retain F1/F2/F3 as three separate findings so the factual boundary stays auditable.

---

### §3.2 PF-R2 — F4 `conflicts(target)` signature + target shapes (sub-prose)

**Cited line**: `04_api_surface.en.md:398`.

**Verbatim current text**:

```markdown
| `conflicts()` | Return active conflicting assertions |
```

**Code source** — method signature (`src/factgraph/sdk/store.py:1382-1385`):

```python
def conflicts(self, target: Any) -> Any:
    """Return conflict diagnostics for an assertion record or entity field cell."""
    pred_id, e_ref = self._conflict_cell_for_target(target)
    return self._sdk._store.conflicts(pred_id, e_ref)
```

**Code source** — shared target-resolution (`src/factgraph/sdk/store.py:1326-1339`, used by both `explain` and `conflicts`):

```python
def _resolve_record_asrt_id(self, target: Any, *, method: str) -> str:
    if isinstance(target, str) and target:
        return target
    asrt_id = getattr(target, "asrt_id", None)
    if isinstance(asrt_id, str) and asrt_id:
        return asrt_id
    raise SDKStoreError(f"fg.audit.{method}(...) expects asrt_id string or AssertionRecord")

def _claim_for_audit_target(self, target: Any, *, method: str) -> Claim:
    asrt_id = self._resolve_record_asrt_id(target, method=method)
    claim = self._sdk.ledger.get_claim(asrt_id)
    ...
```

**Code source** — tuple-branch normalizer specific to `conflicts` (`src/factgraph/sdk/store.py:1341-1371`):

```python
def _conflict_cell_for_target(self, target: Any) -> tuple[str, str]:
    if isinstance(target, tuple) and len(target) == 2:
        entity, field = target
        if isinstance(field, Field):
            schema_pred = self._sdk._schema_pred_for_field(field)
        elif isinstance(field, str) and field:
            e_ref_for_type = entity if isinstance(entity, str) else getattr(entity, "ref", None)
            ...
            schema_pred = {...}
        ...
        return pred_id, e_ref
    claim = self._claim_for_audit_target(target, method="conflicts")  # fallback to shapes 1+2
    return claim.pred_id, claim.e_ref
```

**Drift class**: (b) signature gap — table row signature `conflicts()` shows zero-arity; code is `conflicts(target)` with 4 accepted shapes.

**Expected text (short form)** — table row replacement at `04_api_surface.en.md:398`:

```markdown
| `conflicts(target)` | Diagnose conflicts for an assertion record or entity field cell (see target shapes below) |
```

Per user Step 4.3 directive: table row stays **brief** — no 4-shape enumeration inside the row to avoid API-surface table bloat.

**Expected sub-prose** — sentence inserted immediately after the §2.12 table, before the existing "`diff_proof_frames` is pure (no store/registry/engine/IO)..." paragraph at L401:

```markdown
`fg.audit.conflicts(target)` accepts four target shapes:

1. assertion id string (e.g. `"asrt:..."`);
2. object exposing `.asrt_id` (e.g. `AssertionRecord` or any record returned by
   `fg.assertions.*`);
3. `(entity, Field)` tuple, where `entity` is an `e_ref` string or any object
   with a `.ref` attribute (e.g. an `EntitySnapshot`);
4. `(entity, field_name: str)` tuple, with the same `entity` shape as (3).

`fg.audit.explain(target)` accepts only shapes 1 and 2 — the `(entity, field)`
tuple branch is specific to `conflicts` because it resolves to a cell, not a
specific assertion. Passing shapes 3 or 4 to `explain(...)` raises
`SDKStoreError`.
```

**Step 4.7 edit cells**: 1 table-row replacement + 1 sub-prose paragraph insert.

---

### §3.3 PF-R3 — F5 missing `field(Field) -> AssertionView` row in `04_api_surface.en.md` §2.5

**Cited lines**: `04_api_surface.en.md:343-348` (table).

**Verbatim current text** (§2.5 table):

```markdown
| Method | One-liner |
|---|---|
| `by_id(asrt_id)` | Return `AssertionRecord | None` for one assertion id |
| `by_ids(asrt_ids)` | Return `AssertionRecordSet` for an iterable of assertion ids; unknown ids are skipped |
| `where(*, field=None, e_ref=None, value=None, value_tag=None, _meta=None)` | Filter active assertions by canonical Layer 3 criteria |
| `retract(asrt_id, *, meta=None)` | Retract a specific assertion id; Identity Claims and legacy `:exists` Claims are protected |
| `active` / `all` | Active or all assertion records |
```

**Code source** — public method (`src/factgraph/sdk/store.py:480-501`):

```python
def field(self, field: Field) -> Any:
    if not isinstance(field, Field):
        raise SDKStoreError("fg.assertions.field(...) expects sdk.Field descriptor; string names are ambiguous")
    schema_pred = self._sdk._schema_pred_for_field(field)
    pred_id = schema_pred.get("pred_id")
    ...
    return AssertionView(
        entity_type=str(schema_pred.get("owner_type", "")),
        field_name=str(getattr(field, "sdk_attr_name", schema_pred.get("py_field_name", ""))),
        cardinality=str(schema_pred.get("cardinality", getattr(field, "cardinality", "single"))),
        active_records=tuple(record for record in history_records if record.is_active),
        history_records=history_records,
    )
```

`AssertionView` is documented at `04_api_surface.en.md:418` (existing).

**Drift class**: (b) omitted method row.

**Expected text (short form)** — table row inserted between the existing `by_ids` row and the existing `where` row:

```markdown
| `field(Field)` | Return `AssertionView` for one schema field; exposes `active_records` and `history_records` |
```

Rejects string names; only `sdk.Field` descriptors accepted.

**Expected sub-prose**: none — the existing `AssertionView` documentation at §2.x already explains the returned-object shape.

**Step 4.7 edit cells**: 1 table-row insertion.

---

### §3.4 PF-R4 — F6 `evaluate(...)` reject list completeness + mechanism split

**Cited lines**: `04_api_surface.en.md:362-363` (rejection sentence after §2.6 table).

**Verbatim current text**:

```markdown
Public `evaluate(...)` rejects `engine_options=`, `registry=`, `mode=`, and
candidate compatibility flags.
```

**Code source** (`src/factgraph/sdk/store.py:2374-2395`):

```python
def _evaluate(self, *args: Any, **kwargs: Any) -> EvaluateResult:
    if "view" in kwargs:
        raise SDKStoreError("method-level view= is not supported by evaluate(); use FactGraph.attach(db, view=view) instead")
    if "policy" in kwargs:
        raise SDKStoreError("policy= was removed for read APIs and is not accepted for inference evaluation")
    if "semantics_profile" in kwargs:
        raise SDKStoreError("evaluate() does not accept semantics_profile= in SDK; use config=")
    if "mode" in kwargs:
        raise SDKStoreError("evaluate() does not accept mode= in E; use engine=")
    if "temporal_view" in kwargs:
        raise SDKStoreError("temporal_view is removed from evaluate(); use active/history views on read APIs")
    registry = kwargs.pop("registry", None)
    engine_options = kwargs.pop("engine_options", None)
    if registry is not None:
        raise SDKStoreError("evaluate() does not accept registry= in T5; ...")
    if engine_options is not None:
        raise SDKStoreError("evaluate() does not accept engine_options= in T5; ...")
```

**Drift class**: (b) under-specified — only 3 of 7 rejected kwargs named; reject **mechanism** not described.

**Mechanism split** (per blueprint G4 + Step 4.2 P2-1 amend):

| Mechanism A — presence-rejected | Mechanism B — non-None-rejected |
|---|---|
| `view=` (`if "view" in kwargs:`, L2375) | `registry=` (`kwargs.pop("registry", None)` + `if registry is not None`, L2390/2392) |
| `policy=` (`if "policy" in kwargs:`, L2379) | `engine_options=` (`kwargs.pop("engine_options", None)` + `if engine_options is not None`, L2391/2394) |
| `semantics_profile=` (`if "semantics_profile" in kwargs:`, L2381) | |
| `mode=` (`if "mode" in kwargs:`, L2383) | |
| `temporal_view=` (`if "temporal_view" in kwargs:`, L2385) | |
| **Even `key=None` raises** | **Only non-None values raise** (`key=None` passes through silently) |

**Expected text (short form)** — replace L362-363 sentence with:

```markdown
Public `evaluate(...)` rejects **seven** deprecated/blocked kwargs through two
distinct mechanisms:

- **Presence-rejected (5 kwargs)** — raises even when the value is `None`:
  `view=`, `policy=`, `semantics_profile=`, `mode=`, `temporal_view=`.
- **Non-None-rejected (2 kwargs)** — popped with a `None` default; raises
  only on a non-None value: `registry=`, `engine_options=`.

The mechanism distinction matters when threading kwargs through wrappers: a
wrapper that passes `view=None` to `evaluate(...)` will still raise, while
`registry=None` is silently dropped.
```

**Step 4.7 edit cells**: 1 sentence-block replacement.

---

### §3.5 PF-R5 — F7 `engine=` default precision in `04_api_surface.en.md` §2.6 table

**Cited lines**: `04_api_surface.en.md:358-360`.

**Verbatim current text**:

```markdown
| `evaluate(inference_or_expr, *, head=None, engine='native', config=None)` | Evaluate an `Inference`, `Rule`, or `RuleExpr`; returns `EvaluateResult`. |
| `explain(expr, *, head=closed_head, engine='native', config=None)` | Replay a closed-head explanation; returns `Explanation`. |
| `preview_config(profile)` | Inspect public semantics wrappers or canonical `SemanticsProfile`. |
```

**Code source** — `evaluate` (`src/factgraph/sdk/store.py:2396-2397`):

```python
raw_engine = kwargs.pop("engine", None)
raw_config = kwargs.pop("config", None)
```

**Code source** — `engine` resolution (`src/factgraph/sdk/store.py` — searched `engine = "native" if raw_engine is None`):

```python
engine = "native" if raw_engine is None else raw_engine
allowed = {"native", "souffle", "problog", "pyreason"}
if not isinstance(engine, str) or engine not in allowed:
    raise SDKStoreError(f"{api_path}: engine= must be one of: native, problog, pyreason, souffle")
```

**Drift class**: (b) signature precision — `engine='native'` in docs suggests signature default `'native'`; actual signature default is `None` (resolved internally to `"native"` if not provided).

**Expected text (short form)** — replace L358-359 rows:

```markdown
| `evaluate(inference_or_expr, *, head=None, engine=None, config=None)` | Evaluate an `Inference`, `Rule`, or `RuleExpr`; returns `EvaluateResult`. `engine=None` resolves to `"native"`; explicit values must be one of `"native"`, `"souffle"`, `"problog"`, `"pyreason"`. |
| `explain(expr, *, head, engine=None, config=None)` | Replay a closed-head explanation; `head=` is required (no default). `engine=` resolves the same way as `evaluate`. Returns `Explanation`. |
```

**Expected sub-prose**: none — the table-row precision is sufficient.

**Implementation note**: `head=closed_head` in the existing `explain` row was a meta-syntactic placeholder for "the closed Rule you want to replay against", not a Python default value. F8 (P3, deferred) would clarify this convention further; this slice's edit incidentally improves the situation by writing `head` as required (no default rendering), which is closer to ground truth.

**Step 4.7 edit cells**: 2 table-row replacements.

## §4 PF-r (Recommended Findings)

(Step 4.3 entry: no recommended findings beyond the LOCKED 7. Step 4.4 review may surface PF-r rows here if the user finds new gaps.)

## §5 PF-v (Verified — invariants and self-checks)

**Step 4.2 amend self-check points re-verified at Step 4.3 entry**:

| ID | Self-check | Status |
|---|---|---|
| PF-v1 | Fork basis `80a60f66` consistent across blueprint §0 / §4.1 / audit Event Log row 1 / audit Decision Note 1 (no "from master" residual except the meta-mention in audit log row 2 describing the self-check itself) | ✅ PASS |
| PF-v2 | F1 SDK 2-field claim verified at `sdk/store.py:117-119` fresh read | ✅ PASS |
| PF-v3 | F2 two-class coexistence verified at `sdk/store.py:86` (rename import) + `core/store/database.py:74-81` (Database class) | ✅ PASS |
| PF-v4 | F4 `conflicts(target)` 4-shape enumeration verified at `sdk/store.py:1326-1339` (shapes 1+2 via `_resolve_record_asrt_id`) + `1341-1371` (shapes 3+4 via tuple branch in `_conflict_cell_for_target`) | ✅ PASS |
| PF-v5 | F4 asymmetry: `explain(target)` accepts only shapes 1+2 verified at `sdk/store.py:1373-1380` (only calls `_claim_for_audit_target`, no tuple branch) | ✅ PASS |
| PF-v6 | F5 `field(Field)` is public method (no underscore prefix), returns `AssertionView`, rejects string names — verified at `sdk/store.py:480-501` | ✅ PASS |
| PF-v7 | F6 5 presence-rejected kwargs verified at `sdk/store.py:2375/2379/2381/2383/2385` | ✅ PASS |
| PF-v8 | F6 2 non-None-rejected kwargs verified at `sdk/store.py:2390-2395` | ✅ PASS |
| PF-v9 | F7 `engine=` signature default `None`, effective resolution to `"native"` verified at `sdk/store.py:2396` + `engine = "native" if raw_engine is None` | ✅ PASS |
| PF-v10 | F8 / F9 / F10 / F11 deferred boundary consistent with blueprint §3 Non-goals N11/N12/N13/N14 + §10 carry-forward rows | ✅ PASS |
| PF-v11 | Q-PR1 5 sacred paths 0-diff vs `4c472b50` at preflight HEAD | ✅ PASS (`git diff` returns 0 lines) |
| PF-v12 | Sacred master `562c74195df43e933bed92a3ff25de94dd8ce666` unchanged | ✅ PASS |
| PF-v13 | Dirty baseline 8 entries preserved (4 M + 2 D + 2 untracked) | ✅ PASS |
| PF-v14 | Q-NAMING-F impl branch `v0.2.0-impl-build-application-rule-when-rename-2026-06-01` untouched | ✅ PASS (separate branch) |
| PF-v15 | No release.sh execution; release surface allowlist untouched | ✅ PASS (no script invocation) |

## §6 PF-S (Scoped — implementation decisions)

| ID | Scope decision |
|---|---|
| PF-S1 | F1+F2+F3 merge into single `database.md:355-362` table+paragraph edit at Step 4.7 (per blueprint §5.2 + user Step 4.1 directive); 3 separate findings preserved at blueprint §4.2 + this preflight §3.1 for factual-boundary integrity. |
| PF-S2 | F4 `conflicts(target)` table row stays brief (per user Step 4.3 directive) — 4 target-shape enumeration goes to sub-prose immediately after the §2.12 table, NOT inside the row. Prevents API-surface table bloat. |
| PF-S3 | F6 reject list expanded with **2-column mechanism split** (presence-rejected vs non-None-rejected) per user Step 4.3 directive — not a flat 7-name list. Distinguishes the two code mechanisms a kwarg-threading wrapper author needs to know. |
| PF-S4 | F7 `engine=` precision: signature shown as `engine=None`; one-liner notes "`None` resolves to `'native'`" + lists 4 permitted engine strings. F8 (`head=closed_head` placeholder convention) is partially relieved as side-effect since `head` is rendered as required (no default), but full F8 fix stays deferred. |
| PF-S5 | All 7 fixes land in **one Step 4.7 commit** (`docs(quickstart+sdk): fix 7 docs-vs-shipped drift findings (P0+P1+P2)`); 2 files; ~6 edit cells (PF-R1 = 2 cells: table + paragraph; PF-R2 = 2 cells: row + sub-prose; PF-R3 = 1 cell: row; PF-R4 = 1 cell: sentence block; PF-R5 = 2 cells: 2 rows). |

## §7 PF-A (Abandoned / Deferred Findings)

Mirrors blueprint §10 carry-forward:

| ID | Severity | Reason |
|---|---|---|
| F8 | P3 | `head=closed_head` rendering convention works for closed-head replay readers; explicit reframing has low value vs maintenance risk. **Partially relieved** by PF-R5 PF-S4 — `head` will be rendered as required (no default) post-Step-4.7, which improves clarity even if the "what is closed_head" wording reframe is still deferred. |
| F9 | P3 | §2.10 / §2.11 numbering holes are cosmetic; renumbering risks breaking cross-references outside this blueprint's scope. |
| F10 | P3 | `ingest(items, ...)` doc vs `ingest(data, ...)` code: positional parameter; user-invisible. |
| F11 | P3 | Standalone `quickstart/package.md` requires non-trivial new content authoring; out of audit-then-fix lightweight cadence scope. |

## §8 Findings → Step 4.7 Edit Cell Mapping

Step 4.7 author's single commit should produce these edits in this order (groups them by file to minimize context switching):

### `docs/official/kernel/quickstart/database.md`

| Cell | Edit | Source | Target |
|---|---|---|---|
| 1 | Replace 2 table rows + insert 1 sub-prose paragraph | §3.1 PF-R1 verbatim text | `database.md:355-362` |

### `src/factgraph/sdk/docs/04_api_surface.en.md`

| Cell | Edit | Source | Target |
|---|---|---|---|
| 2 | Replace §2.6 `evaluate` table row | §3.5 PF-R5 expected | L358 |
| 3 | Replace §2.6 `explain` table row | §3.5 PF-R5 expected | L359 |
| 4 | Replace §2.6 reject sentence | §3.4 PF-R4 expected | L362-363 |
| 5 | Insert §2.5 `field(Field)` row | §3.3 PF-R3 expected | between L345 and L346 |
| 6 | Replace §2.12 `conflicts()` row | §3.2 PF-R2 expected (short form) | L398 |
| 7 | Insert §2.12 4-shape sub-prose paragraph | §3.2 PF-R2 expected sub-prose | between L399 and L401 |

Total: 7 edit cells, 2 files. PF-R1 is one logical edit but Edit-tool granularity may split it into table + paragraph operations.

## §9 Step 4.4 Carry-back Candidates

Step 4.3 surfaced no new Required or Recommended findings beyond blueprint §4.2 LOCKED scope. Step 4.4 review need not amend blueprint.

If user Step 4.4 review surfaces additional precision points (analogous to Step 4.2 P2-1 / P2-2 / P3-1), they will be amended on the blueprint branch (not this preflight branch) per Slice 7B cadence.
