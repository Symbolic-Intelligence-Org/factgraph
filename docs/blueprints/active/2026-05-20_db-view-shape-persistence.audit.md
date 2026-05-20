# Task Blueprint Audit: DB View Shape And Persistence

- Blueprint: [2026-05-20_db-view-shape-persistence.md](./2026-05-20_db-view-shape-persistence.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-20 | draft | Blueprint created | Scoped Slice 3 as canonical view shape, view digest, anonymous view-object persistence, and SDK compatibility boundary. |
| 2026-05-20 | draft | Preflight amendments applied | PF-1 through PF-6 from `docs/audit/2026-05-20_db-view-persistence-preflight.md` folded into the draft. |
| 2026-05-20 | scoped | Preflight amendments and self-check passed | PF-1 through PF-6 covered by `92c898e6`;preflight `a7105ba1` has no remaining scoped blocker. |
| 2026-05-20 | implemented | Scoped implementation landed | Implementation `c51ed752` added Database-owned durable frozen view objects, view digest bytes, `Database.create_view(...)`, tests, and module docs without expanding into excluded slices. |

## Decision Notes

### 2026-05-20 — Initial Slice 3 scope

The blueprint follows the post-Q synthesis Slice 3 recommendation: implement view shape and persistence only after Slice 1 DB identity substrate and Slice 2 DB workspace physical layout are implemented and archived.

Adopted Q decisions:

- Q4 supplies the canonical six-field `FrozenAssertionView` target and `view_digest` semantic inputs.
- Q5 supplies the scope-universe invariant: view-supplied scope is exactly `view.asrt_ids`; default no-view behavior remains active-only.
- Q3 supplies digest token conventions and existing schema/tx identity context.
- Q7 supplies canonical assertion identity context, but this slice does not alter assertion records.

### 2026-05-20 — Explicit exclusions

The draft deliberately excludes:

- public `fg.read.find(view=...)`, `fg.run(view=...)`, and `fg.eval.evaluate(view=...)` semantics;
- `FactGraph.attach(...)`;
- evidence/explain metadata behavior;
- persistent named view registry;
- view set algebra;
- DB identity protocol changes;
- Q6/Q8 registry migration work.

These exclusions preserve the post-Q synthesis boundary between blueprint-eligible DB/view substrate work and cross-doc blocked rule-expression/evidence seams.

### 2026-05-20 — Preflight items already visible from draft

The draft intentionally leaves several choices to preflight before `scoped`:

- exact `view_digest` byte protocol for Q4's semantic inputs;
- module placement for the canonical durable view record versus SDK compatibility adapter;
- current-head-only versus historical base snapshot membership validation;
- exact JSON canonicalization for view object content;
- whether to create `views/` eagerly or on first persisted view object.

### 2026-05-20 — Preflight PF-1/PF-2/PF-3/PF-4 required amendments

Preflight `a7105ba1` required four amendments before `scoped`;all are now applied:

- PF-1: durable view persistence is new-layout workspace only. Memory-mode and legacy-ledger-mode Database instances reject durable view persistence in this slice.
- PF-2: durable view creation uses a Database-owned API shape, `Database.create_view(name, asrt_ids, *, base=None)`, with `base=None` meaning current head.
- PF-3: `view_digest` uses dedicated `factpy\0subset_view_v1\0` domain-separated bytes over `db_id`, `base_tx_id`, `schema_digest`, and sorted `asrt_ids`.
- PF-4: view creation is current-head-only until replay/snapshot tooling exists. Membership validation checks current ledger claim existence and deliberately does not require active status.

### 2026-05-20 — Preflight PF-5/PF-6 recommended amendments

Preflight `a7105ba1` recommended two additional amendments;both are applied:

- PF-5: view object content uses the same canonical JSON style, write-once behavior, and temp-file plus `os.replace(...)` per-file write pattern as Slice 2 tx/schema objects.
- PF-6: SDK `fg.save(...)` remains unchanged and continues excluding `_SDKViewsManager` in-memory views. A future SDK adapter must require an explicit Database-backed path and must not silently persist the SDK view dictionary as a named registry.
