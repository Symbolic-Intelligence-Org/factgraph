# Audit: Quickstart Database And View — Rebase Onto T11.1

- Status: implemented
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-26_quickstart-database-view-rebase-onto-t11-1.md`
- Stage: implemented
- Class: M (predicted docs-only)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked preserved
- Ownership: self-owned (Claude as both owner and reviewer; Codex on parallel work)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-26 | scoped | `20bae7ba` | Reconciliation blueprint pair drafted | Self-owned cycle. Triggered by retroactive review of T5 branch's `quickstart-database-view` cycle (8 commits `bf161c62..c77d0442`) which authored against pre-T11.1 state and now contradicts T11.1's shipped `attach(..., view=view)` (`76f46ada`). |
| 2026-05-26 | implemented | `1c54f587` | Database.md content cherry-picked + A1+A2+A3 amends + 4 cross-link reconciliations | 5 docs files touched: new database.md (+388 LOC), index.md (database.md inserted as #5), persistence.md (+5-line cross-link paragraph), assertions.md (+7-line cross-link paragraph), namespace-map.md (+1-sentence cross-link in attach row). 7-step end-to-end smoke green; Complete example block also runs green. 0 production files. |
| 2026-05-26 | fix | `00029fdd` | Step 4.8 post-archive fix: schema strong correspondence explicit | User review caught that database.md mentions schema validation in two scattered places but does not name the **three-way strong correspondence chain** locked by the T11.1 blueprint: `compiled(schema_classes) == db.schema_digest == view.schema_digest`. Added (1) writable-attach 2-way chain explanation + exact error message in §"Attach a FactGraph runtime"; (2) new §"Schema strong correspondence" subsection under §"View-scoped attach" with 5-row reject table covering compiled-vs-db / view-vs-db schema / view-vs-db id / base_tx_id materialization / asrt_ids presence; (3) syntax checklist bullet summarizing the 3-way chain. 3 new negative-path smoke assertions verified green. |
| 2026-05-26 | fix | `2c556189` | Step 4.8 follow-up: schema_classes vs schema_ir surface ambiguity | User review caught a second issue: schema.md teaches `FactGraph.create(schema_classes=[...])` directly while database.md teaches `compile_schema_from_classes(...)` + `Database.create(schema_ir=...)`, with no explanation that these are the high-level vs lower-level surfaces of the same compile step. Added (1) explicit table in database.md §"Define a schema IR" mapping 5 surfaces to which form they accept (`schema_classes` vs `schema_ir`) and why; (2) trailing paragraph explaining attach still needs Entity classes (for read/write binding) and recompiles to validate the digest, with anchor link to §"Schema strong correspondence"; (3) one-paragraph addition to schema.md after the `FactGraph.create(...)` example pointing readers to database.md and explaining the high-level constructors hide the `compile_schema_from_classes(...)` call. Verified empirically: both paths produce identical schema_digest. |
| 2026-05-26 | fix | pending | Step 4.8 follow-up 2: durable view update/delete shipped boundary | User review caught a third issue: database.md teaches `db.create_view(...)` but never mentions that **`update_view` / `delete_view` / `get_view` / `list_views` are not shipped**. Empirically confirmed against `src/factgraph/core/store/database.py:478-512`: only `create_view` exists on `Database`. Same-name + same-ids is idempotent (`_write_once_bytes` no-ops on identical digest); same-name + different-ids writes a new view object whose filename is the new `view_digest`, with the old `views/objects/<old_digest>.json` left on disk. Added new §"Durable views are immutable" with three subsections (idempotent re-create / same-name-new-ids creates new view / "update" + "delete" deliberately not shipped + how to "change" or "remove"). Extended syntax checklist with two paragraph-length bullets covering the durable view immutability boundary and the `fg.views` session-local CRUD contrast. |

## 2. Source Reads

| Source | Reason |
|---|---|
| `git diff v0.2.0-t5-result-evidence-explain-audit-2026-05-25 HEAD -- docs/official/kernel/quickstart/*.md` | Exact diff between T5 and T11.1 for all quickstart pages. Confirmed 5 files in conflict (index/persistence/assertions/namespace-map have direct diffs; database.md is T5-only). |
| T5 `database.md` (via `git show`) | Source content to cherry-pick + amend. 342 LOC. |
| T11.1 `persistence.md` lines 131-138 | Already teaches shipped `attach(..., view=view)`. Amend reference. |
| T11.1 `namespace-map.md` lines 69, 119-120 | Already teaches shipped `attach(..., view=None)` and view-scoped consumption. Amend reference. |
| `src/factgraph/sdk/store.py:887-918` | Shipped `attach` signature with `view=` kwarg (T11.1 `76f46ada`). |

## 3. Initial Inventory

| Area | Finding | Treatment |
|---|---|---|
| `database.md` existence on T11.1 | Absent. T5 has 342-LOC content. | Cherry-pick from T5 with 3 amends. |
| T5's `# FactGraph.attach(db, view=view, ...)   # not shipped` line | Now factually wrong (shipped on T11.1 by 76f46ada). | Amend A1: remove the wrong line; replace with positive cross-link to new §View-scoped attach. |
| T5's checklist bullet "Do not pass view= to read, evaluate, or attach APIs" | Partially wrong: `view=` IS attach-time, not row-level. | Amend A2: rewrite to scope-correctly. |
| T5's database.md has no view-scoped attach section | T11.1's shipped feature lacks tutorial coverage in database.md. | Amend A3: add new §View-scoped attach with end-to-end example. |
| `index.md` on T11.1 | 9-item sequence; no database.md slot. | Insert database.md as #5; renumber #5..#9 → #6..#10. |
| `persistence.md` on T11.1 | Already teaches `attach(..., view=view)` (lines 131-138); has no cross-link to database.md. | Add 1 cross-link sentence near the existing paragraph. |
| `assertions.md` on T11.1 | T11.1 76f46ada removed the database.md cross-link paragraph. | Re-introduce a precise cross-link paragraph (not verbatim T5 wording — updated to reference shipped `view=` attach). |
| `namespace-map.md` on T11.1 | Already teaches `attach(db, schema_classes=[...], view=None)`; no cross-link to database.md. | Add 1 cross-link sentence near the attach row. |

## 4. Step 4.6 Scoped Inventory Plan

Pre-implementation inventory is locked inline below in §5 (Step 4.6 results). Self-owned cycle means the survey is done before the draft.

## 5. Step 4.6 Scoped Inventory Results

| # | Item | Result | Source / evidence |
|---|---|---|---|
| 1 | T5 `database.md` line containing wrong "not shipped" claim | Line near "Neither surface is a read policy today" block (T5 line ~221-227). Three commented-out lines; the third is the wrong one. | `git show v0.2.0-t5-result-evidence-explain-audit-2026-05-25:docs/official/kernel/quickstart/database.md` |
| 2 | T5 `database.md` checklist bullet | Last bullet: "Do not pass `view=` to read, evaluate, or attach APIs." | Same source, bottom of file. |
| 3 | T5 `database.md` total LOC | 342 lines. | T5 `git show --stat d9b5f449` |
| 4 | T11.1 `persistence.md` shipped attach paragraph location | Lines 131-138 (after the "Artifact sidecars, in-memory views..." paragraph). Wording: `db.create_view(...)` on a `Database`, then consume them with `FactGraph.attach(db, schema_classes=[...], view=view)`. A view-attached runtime is read-only and automatically scopes `fg.read.*` and `fg.eval.evaluate(...)` to the view's assertion ids. | `docs/official/kernel/quickstart/persistence.md:131-138` |
| 5 | T11.1 `namespace-map.md` shipped attach row | Line 69: `FactGraph.attach(db, schema_classes=[...], view=None)` Bind the SDK to a `Database`. Passing a durable `db.create_view(...)` view creates a read-only, view-scoped runtime. | `docs/official/kernel/quickstart/namespace-map.md:69` |
| 6 | T11.1 shipped attach implementation file | `src/factgraph/sdk/store.py:887-918` (post-T11.1). Accepts `view: FrozenAssertionView \| None = None` keyword; validates `view.db_id == db.db_id` and `view.schema_digest == db.schema_digest`; sets attached runtime read-only and view-scoped. | `src/factgraph/sdk/store.py` |
| 7 | T11.1 view-scoped read/eval scoping | Same `store.py:887-918`; view-attached runtime sets `_attached_view_asrt_ids` which is consulted in `fg.read.*` and `fg.eval.evaluate(...)` to filter the assertion universe. | `src/factgraph/sdk/store.py` |
| 8 | Pre-existing dirty baseline files | 6 M: docs/references/working/design-points/readme.md, examples/01_sdk_check_diagnose.ipynb, examples/02_overlay_why_not_frontier.ipynb, examples/archive/01_sdk_basics.ipynb, src/factgraph/sdk/facade.py, tests/test_sdk_assertion_record_set_view_filters.py. 1 untracked: rainbird-ai sdk code/. | `git status` |
| 9 | Sacred master commit | `562c74195df43e933bed92a3ff25de94dd8ce666`. | `git rev-parse master` |
| 10 | `index.md` current sequence | 9 items: 1 first-factgraph → 2 schema → 3 read-write → 4 assertions → 5 rules-and-inferences → 6 semantics → 7 evidence → 8 persistence → 9 namespace-map. Need database.md at #5. | `docs/official/kernel/quickstart/index.md:5-13` |
| 11 | `assertions.md` location for re-inserted cross-link | End of "SDK views are different" subsection on assertions.md; the paragraph was at line ~478 in T5. | T5 diff vs HEAD shows assertions.md removed a 5-line paragraph; needs re-add with updated wording. |
| 12 | Cherry-pick mechanic | NOT `git cherry-pick` on 8 commits (would carry blueprint cycle noise); instead `git show v0.2.0-t5-...:database.md > working file` + manual amends. Other 4 cross-link files: manual edits (not raw checkout from T5, because T11.1 wording differs and must be preserved). | Design decision based on diff inspection. |

### Drift findings (recorded as design vs shipped)

- **D1 (already resolved by T11.1 `76f46ada`)** Design-point `database-view-fg-layered-architecture.zh.md` originally proposed `FactGraph.attach(db, view=view)` as a future / deferred capability. T11.1 shipped it. T5's database.md was written before T11.1 ship and still says "not shipped". This cycle reconciles the doc with the shipped reality.

### Scoped decisions

- Cherry-pick `database.md` content via raw `git show` extraction; do NOT `git cherry-pick` the 8 T5 commits.
- Apply amends A1+A2+A3 to database.md content before committing.
- Apply 4 cross-link reconciliations (index/persistence/assertions/namespace-map) via direct edits on T11.1 state — do not import T5's cross-link content verbatim (T5 wording is partially stale).
- Single feat commit on T11.1 branch for all docs changes.
- T5 branch's 8 commits remain as historical record on that branch; not deleted, not force-rebased. T5 branch will not be pushed; the canonical published line will be T11.1.

## 6. Verification Plan

7-step end-to-end smoke covering the database.md page including the new §View-scoped attach section:

1. Create temporary workspace; build `schema_ir` via `compile_schema_from_classes`.
2. `Database.create(workspace, schema_ir=...)`; verify `db_id`, `schema_digest`, `head().tx_id`.
3. `FactGraph.attach(db, schema_classes=[User])` (writable attached).
4. `fg.commit_assertions([AssertionInput(...)])`; verify commit.
5. `view = db.create_view("name", [asrt_id])`; verify 6-field shape and view_digest.
6. `view_fg = FactGraph.attach(db, schema_classes=[User], view=view)`; verify read-only + view-scoped reads.
7. `Database.open(workspace, schema_ir=...)` + reattach with view=view; verify still works.

Additionally:

- `git diff --check` clean.
- Only 5 docs files + blueprint pair touched.
- Dirty baseline preserved at 6 M + 1 U.
- Sacred master unchanged.

## 7. Review Checklist

- [x] Step 4.6 scoped inventory recorded before implementation.
- [x] Implementation applied amends A1+A2+A3 correctly.
- [x] Smoke 7/7 passed (and post-Step-4.8 fix: smoke 7/7 + 3 new schema-correspondence reject paths green).
- [x] No `# FactGraph.attach(db, view=view, ...)   # not shipped` line remains anywhere in docs.
- [x] No "Do not pass `view=` ... or attach APIs" wording remains anywhere in docs.
- [x] No production files touched; dirty baseline preserved.
- [x] **Step 4.8 fix**: Schema **three-way strong correspondence** chain (`compiled(schema_classes) == db.schema_digest == view.schema_digest`) explicitly named, with 5-row reject table and writable-attach 2-way chain explanation.

## 8. Closure Notes

Implemented with `1c54f587` on top of scoped blueprint pair `20bae7ba`.

Self-owned cycle summary:

- Cycle ran self-owned because Codex was on parallel work after T11.1
  attach-view-scope close. Owner and reviewer were both Claude.
- 12-item Step 4.6 inventory was pre-locked into the scoped state at
  blueprint creation (not draft -> scoped, but draft+scoped combined as
  a single commit, mirroring the rules-ports-ruleexpr self-owned cycle
  pattern from earlier today).
- Step 4.7 self-review took the form of a fresh-read pass over the new
  database.md content (388 LOC) plus the 7-step end-to-end smoke that
  specifically exercises the new shipped `view=` attach branch — the
  branch that was incorrectly marked "not shipped" in T5's original
  database.md content.

Final landed scope:

- New `database.md` (388 LOC): Database identity boundary, attach
  workflow, commit_assertions, durable view objects, SDK views vs
  durable views contrast, **View-scoped attach (new section)**,
  Complete example with view-scoped attach + writable reattach, and
  syntax checklist.
- index.md, persistence.md, assertions.md, namespace-map.md cross-links
  reconciled.

Drift records:

- D1 (already resolved by T11.1 `76f46ada`): T5 database.md was
  authored before `attach(..., view=view)` shipped. This cycle removed
  the "not shipped" line and reframed the checklist bullet.

Verification:

- 7-step end-to-end smoke (Database.create -> writable attach ->
  commit_assertions -> create_view -> view-scoped attach (read-only)
  -> view-attached mutation reject -> Database.open + reattach with
  view) all GREEN against the live SDK on T11.1 branch.
- Complete example block reproduced verbatim and runs GREEN.
- `git diff --check`: clean.
- Diff scope: 5 docs files + blueprint pair.
- Sacred master at `562c74195df43e933bed92a3ff25de94dd8ce666` unchanged.
- Pre-existing 6 modified + 1 untracked dirty baseline preserved end-to-end.

Deferred / non-goals (left for future cycles):

- T5 branch's 8 commits remain as historical record on T5 branch; not
  pushed, not deleted.
- Eventual T5 branch retirement / pruning is a separate decision.
- Promoting row-level `view=` parameters on `fg.read.find` /
  `fg.eval.evaluate` was a non-goal — these remain rejected with the
  message "method-level view= is not supported; use FactGraph.attach
  (db, view=view) instead", and docs now teach that.
