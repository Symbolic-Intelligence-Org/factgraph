# Audit: T11.2 Cross-doc Metadata Unblock

- Status: scoped
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-26_t11-2-cross-doc-metadata-unblock.md`
- Stage: scoped
- Class: L (predicted release-blocker documentation / tests / metadata decision slice; may narrow to M after Step 4.6)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked must be preserved
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-26 | draft | `e1bdfa43` | T11.2 blueprint pair drafted | Triggered by roadmap N3 and read-only Parfit inventory of database-view Step 1-6 / I10 / A10 seams. |
| 2026-05-26 | scoped | TBD | Step 4.6 inventory scoped | Filled Step 1-6 / I10 / A10 source map, accepted `view_snapshot_digest` as v0.2 bridge, scoped three release-facing docs fixes, and added T11.1 archive cleanup. |

## 2. Read-only Agent Inventory Summary

Parfit completed a read-only inventory before drafting. No files were edited.

Key finding: there are no literal `S1`-`S6` markers in the active design note.
The intended markers are `Step 1` through `Step 6` in
`workflow/design/design-points/active/database-view-fg-layered-architecture.zh.md`
§16. `I10` is in the invariants table and `A10` is in the commitments table.

| Source item | Read-only finding | Draft consequence |
|---|---|---|
| Step 1 | Durable Database view has anchor fields; SDK in-memory view is intentionally smaller. | Document split; no code expected. |
| Step 2 | Attach-based view consumer shipped; method-level `view=` still rejects. | v0.2 attach-only decision to formalize. |
| Step 3 / I10 / A10 | Shipped public bridge is `view_snapshot_digest`, not exact tuple fields. | Mandatory Step 4.6 metadata decision. |
| Step 4 | `Database.head()` shipped; `Database.as_of(...)` absent. | Snapshot attach deferred unless amended. |
| Step 5 | Base attach and view attach shipped; snapshot attach absent. | Release docs must avoid `as_of` overclaim. |
| Step 6 | Runtime hardening tests exist; metadata tests cover digest bridge. | Strengthen only if needed. |
| Docs | Official Database quickstart, core store docs, and SDK docs README contain stale/future wording. | Release-required docs cleanup. |
| Service/OpenAPI | Service serializes `view_snapshot_digest`; exact tuple fields absent. | Only touch if exact fields are chosen. |

## 3. Local Draft Cross-check

Draft-time local grep confirmed:

| Area | Evidence |
|---|---|
| Database-view design source | §16 contains Step 1-6; I10 requires db/view metadata; A10 repeats EvaluateResult / EvidenceGraph metadata requirement. |
| Official quickstart contradiction | `database.md` introduction says the page does not introduce view-scoped reads/evaluation, while later sections teach view-scoped attach. |
| Core store docs stale wording | `src/factgraph/core/store/docs/README.md` still says view-scoped attach remains future. |
| SDK docs stale wording | `src/factgraph/sdk/docs/README.md` still says snapshot and view-scoped attach forms remain future. |
| Shipped DTO bridge | `EvaluateResult` exposes `view_snapshot_digest`; evidence graph metadata copies it. |
| Shipped method-level boundary | `fg.read.find(..., view=...)`, `fg.eval.evaluate(..., view=...)`, and `fg.eval.explain(..., view=...)` reject with attach-based hint. |

## 4. Draft Scope Decisions

| Decision | Rationale |
|---|---|
| Do not assume exact I10/A10 fields | Exact fields would affect public DTOs and possibly service/OpenAPI; this must be an explicit Step 4.6 decision. |
| Treat attach-based view scope as v0.2 shipped surface | T11.1 implemented and tested `FactGraph.attach(db, view=view)`. |
| Treat method-level `view=` as v2 deferred | User simplification and T11.1 scope locked this boundary. |
| Treat `Database.as_of(...)` as deferred | Shipped code lacks it; release docs must not imply it exists. |
| Prefer docs/tests only | Production changes require amend unless Step 4.6 proves a shipped invariant lacks implementation. |
| Archive T11.1 blueprint pair in T11.2 | Step 4.2 found T11.1 implemented but still in `active/`; T11.2 includes this as lifecycle cleanup with no behavior change. |

## 5. Step 4.6 Inventory Checklist

To fill during scoped inventory:

| # | Item | Result |
|---|---|---|
| 1 | Database-view Step 1-6 exact source lines | Step 1 line 661, Step 2 line 669, Step 3 line 675, Step 4 line 680, Step 5 line 685, Step 6 line 695. |
| 2 | I10 and A10 exact source lines | I10 line 158; A10 line 729. |
| 3 | Step 1 durable view anchor shipped/tested status | Shipped for durable Database views: core `FrozenAssertionView` six fields at `src/factgraph/core/store/database.py:75`, creation at `database.py:478`; SDK in-memory view remains two-field at `src/factgraph/sdk/store.py:118`. |
| 4 | Step 2 attach vs method-level view status | Attach-based view scope shipped via `FactGraph.attach(..., view=...)` at `src/factgraph/sdk/store.py:1078`; method-level `view=` rejects with attach hint at `store.py:1277`, `store.py:2353`, `store.py:2449`. |
| 5 | Step 3 metadata bridge vs exact-field decision | **Bridge decision accepted for v0.2**: `EvaluateResult.view_snapshot_digest` is the public bridge; EvidenceGraph metadata copies it. Exact tuple fields remain v2/internal and would require amend/split. |
| 6 | Step 4 `DatabaseValue` / `as_of` status | `DatabaseValue` and `Database.head()` shipped; `Database.as_of(...)` absent and remains deferred. |
| 7 | Step 5 attach forms status | Base attach and view attach shipped; snapshot attach through `db.as_of(...)` deferred. |
| 8 | Step 6 hardening tests status | Existing tests cover view read/evaluate, stale/mismatch, read-only, method-level rejection, digest helper, and EvidenceGraph metadata copy. No new behavior test required for docs-only implementation. |
| 9 | Release-facing stale docs list | Required fixes: `docs/official/kernel/quickstart/database.md`, `src/factgraph/core/store/docs/README.md`, `src/factgraph/sdk/docs/README.md`. |
| 10 | Service/OpenAPI impact under chosen metadata decision | No service/OpenAPI change under bridge decision. `src/service/runtime_v1.py` already serializes `view_snapshot_digest`; exact tuple fields are not selected. |
| 11 | Focused verification commands | Docs/lifecycle implementation: `git diff --check`, `git status --short --branch`, `git rev-parse master`, and optional focused metadata tests if any test files are touched. G7 baseline not required unless tests or production change. |
| 12 | T11.1 blueprint archive cleanup | `workflow/blueprints/active/2026-05-26_t11-1-attach-view-scope.{md,audit.md}` are implemented but still active; implementation must `git mv` both to archive and update `archive/INVENTORY.md`. |
| 13 | Dirty baseline verification | Preserve existing 6 modified + 1 untracked; scoped commit touches only T11.2 blueprint/audit. |

## 6. Verification Plan

Expected after implementation:

- `git diff --check`.
- `git status --short --branch`.
- `git rev-parse master`.
- Focused tests only if tests are touched.
- G7 baseline only if scoped inventory says this is not docs-only.
- Review final docs for the three forbidden contradictions:
  - view-scoped attach future vs shipped;
  - method-level `view=` implied shipped;
  - exact db/view metadata fields implied public if only digest bridge exists.

## 7. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 inventory complete.
- [x] Metadata decision recorded.
- [ ] Release-facing docs aligned.
- [ ] Tests added or explicitly not needed.
- [ ] No production code changes unless amended.
- [ ] T11.1 blueprint pair archived.
- [ ] Closure notes filled.
