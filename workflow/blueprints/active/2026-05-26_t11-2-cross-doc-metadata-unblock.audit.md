# Audit: T11.2 Cross-doc Metadata Unblock

- Status: draft
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-26_t11-2-cross-doc-metadata-unblock.md`
- Stage: draft
- Class: L (predicted release-blocker documentation / tests / metadata decision slice; may narrow to M after Step 4.6)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked must be preserved
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-26 | draft | TBD | T11.2 blueprint pair drafted | Triggered by roadmap N3 and read-only Parfit inventory of database-view Step 1-6 / I10 / A10 seams. |

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

## 5. Step 4.6 Inventory Checklist

To fill during scoped inventory:

| # | Item | Result |
|---|---|---|
| 1 | Database-view Step 1-6 exact source lines | TBD |
| 2 | I10 and A10 exact source lines | TBD |
| 3 | Step 1 durable view anchor shipped/tested status | TBD |
| 4 | Step 2 attach vs method-level view status | TBD |
| 5 | Step 3 metadata bridge vs exact-field decision | TBD |
| 6 | Step 4 `DatabaseValue` / `as_of` status | TBD |
| 7 | Step 5 attach forms status | TBD |
| 8 | Step 6 hardening tests status | TBD |
| 9 | Release-facing stale docs list | TBD |
| 10 | Service/OpenAPI impact under chosen metadata decision | TBD |
| 11 | Focused verification commands | TBD |
| 12 | Dirty baseline verification | TBD |

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

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 inventory complete.
- [ ] Metadata decision recorded.
- [ ] Release-facing docs aligned.
- [ ] Tests added or explicitly not needed.
- [ ] No production code changes unless amended.
- [ ] Closure notes filled.

