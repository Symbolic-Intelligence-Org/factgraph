# Task Blueprint: Quickstart Database And View — Rebase Onto T11.1

- Status: scoped
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Class: M (predicted docs-only)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Claude
- Reviewer: Claude (self-owned; Codex on parallel work)
- Related audit: `workflow/blueprints/active/2026-05-26_quickstart-database-view-rebase-onto-t11-1.audit.md`
- Source cycle (now historically diverged on T5 branch):
  - `workflow/blueprints/archive/2026-05-26_quickstart-database-view.md` (on `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`)
  - 8 commits `bf161c62..c77d0442` on T5 branch
- Related modules (read-only):
  - `src/factgraph/sdk/store.py` (`FactGraph.attach(..., view=)` shipped on T11.1 by `76f46ada`)
  - `src/factgraph/core/store/database.py`
- Related docs (write):
  - `docs/official/kernel/quickstart/database.md` (new file, amended from T5 version)
  - `docs/official/kernel/quickstart/index.md`
  - `docs/official/kernel/quickstart/persistence.md`
  - `docs/official/kernel/quickstart/assertions.md`
  - `docs/official/kernel/quickstart/namespace-map.md`

## 0. Scope Locks

### In scope

Cherry-pick the T5 branch's `quickstart-database-view` cycle content (the database.md page + 4 cross-link edits) onto the T11.1 branch, and **amend the content for the post-T11.1 reality** in which `FactGraph.attach(db, schema_classes=[...], view=view)` is shipped (`76f46ada` on T11.1).

Specifically:

- Add `docs/official/kernel/quickstart/database.md` (~340 LOC, sourced from T5 branch with 3 amends listed below).
- **Amend (A1)** the "Not supported" example block: `# FactGraph.attach(db, view=view, ...)   # not shipped` → reframe as "view= attach is shipped — see [persistence](persistence.md) and §View-scoped attach below".
- **Amend (A2)** the "Do not pass `view=` to read, evaluate, or attach APIs" checklist bullet: rewrite to reflect that `view=` IS supported on `attach` (but still not on `fg.read.find` / `fg.eval.evaluate` parameters at row level).
- **Amend (A3)** add a new §"View-scoped attach" section showing `FactGraph.attach(db, schema_classes=[...], view=view)` with read-only / view-scoped read+eval behavior.
- Add database.md as item #5 in `index.md` (between Assertion records #4 and Rules and inferences #6).
- Re-introduce the cross-link paragraph in `assertions.md` pointing to database.md (with updated wording reflecting shipped `view=` attach).
- Add a cross-link in `persistence.md` near the existing `db.create_view(...)` + `attach(..., view=view)` paragraph (lines 135-136) pointing readers to database.md.
- Add a cross-link in `namespace-map.md` near the existing attach row (line 69) pointing to database.md.

### Out of scope

- Production code changes.
- Changing the shipped behavior of `attach(..., view=view)` (already shipped by T11.1 `76f46ada`).
- Promoting `fg.read.find(view=...)` or `fg.eval.evaluate(..., view=...)` as parameters (these remain non-goals — only attach-time view scoping is shipped).
- Cherry-picking T5 branch's blueprint cycle commits themselves (only the doc content is in scope; the T5 blueprint archive stays on T5 branch as historical record).
- Touching pre-existing 6 M + 1 untracked dirty baseline.
- Rewriting unrelated quickstart pages.

### M-to-L / stop-and-amend triggers

Pause if implementation requires:

- production code edits (any `.py` change);
- introducing a new attach kwarg or read parameter;
- claiming `view=` works on `fg.read.find` / `fg.eval.evaluate` as a row-level parameter;
- touching dirty baseline files;
- cherry-picking T5 blueprint-cycle commits onto T11.1 (only content in scope).

## 1. Problem

The T5 branch `quickstart-database-view` cycle (8 commits `bf161c62..c77d0442`) produced a 342-LOC `database.md` quickstart page + cross-link edits to `index.md` / `persistence.md` / `assertions.md` / `namespace-map.md`.

That cycle was authored against T5 branch state in which `76f46ada feat(sdk): support attach-based Database views` did **not** exist. T5's database.md therefore explicitly teaches:

```python
# fg.read.find(User, view=view)          # not a parameter
# fg.eval.evaluate(rule, view=view)      # not a parameter
# FactGraph.attach(db, view=view, ...)   # not shipped
```

and the checklist bullet:

> Do not pass `view=` to read, evaluate, or attach APIs.

The third claim ("attach … not shipped") is **no longer true on T11.1**, where `76f46ada` shipped `FactGraph.attach(db, schema_classes=[...], view=view)` as a read-only view-scoped runtime.

Without reconciliation, future merges of T5 → T11.1 (or both → integration) will leave end-users with contradictory documentation: persistence.md says `view=` attach is shipped, database.md says it is deferred.

This cycle reconciles the doc content with the post-T11.1 shipped reality.

## 2. Inputs

| Source | Reason |
|---|---|
| T5 branch `docs/official/kernel/quickstart/database.md` | Source content for cherry-pick (with 3 amends). |
| T11.1 branch `docs/official/kernel/quickstart/persistence.md` lines 131-138 | Already teaches `attach(..., view=view)` as shipped; provides amend reference wording. |
| T11.1 branch `docs/official/kernel/quickstart/namespace-map.md` lines 69, 119-120 | Already teaches shipped `attach(db, schema_classes=[...], view=None)` and view-scoped consumption. |
| `src/factgraph/sdk/store.py` (T11.1, lines 887-918) | Shipped `attach` signature with `view=` kwarg. |
| `src/factgraph/core/store/database.py` | Shipped `Database.create_view(...)` 6-field shape. |

## 3. Proposed Shape

### 3.1 `database.md` (new file)

Cherry-pick the T5 branch content with three precise amends:

- **A1** Replace the "Not supported" example block (T5 lines ~224-226):
  - Before:
    ```python
    # fg.read.find(User, view=view)          # not a parameter
    # fg.eval.evaluate(rule, view=view)      # not a parameter
    # FactGraph.attach(db, view=view, ...)   # not shipped
    ```
  - After: keep the first two non-parameters; remove the attach line and add a positive cross-link to the new §"View-scoped attach" section.

- **A2** Rewrite the checklist bullet:
  - Before: `Do not pass view= to read, evaluate, or attach APIs.`
  - After: `view= is only an attach-time argument: FactGraph.attach(db, schema_classes=[...], view=view). It is not accepted as a read or evaluate row-level parameter.`

- **A3** Add a new §"View-scoped attach" section between "SDK views are different" and "Complete example":
  - Show `FactGraph.attach(db, schema_classes=[...], view=view)`.
  - Explain read-only behavior + view-scoped read+eval scoping.
  - Cross-link forward to persistence.md §"workspace persistence" closing paragraph (already teaches the same on T11.1).
  - Show that the view-attached runtime rejects mutation methods.

### 3.2 `index.md`

Insert database.md as item #5:

```diff
 4. [Assertion records and views](assertions.md)
+5. [Database and durable views](database.md)
-5. [Rules and inferences](rules-and-inferences.md)
+6. [Rules and inferences](rules-and-inferences.md)
... (renumber through #10)
```

### 3.3 `persistence.md`

Add a cross-link near lines 131-138 (the existing `db.create_view(...)` + `attach(..., view=view)` paragraph):

> See [Database and durable views](database.md) for the lower Database identity boundary, `Database.create/open/head/commit_assertions`, durable view object shape, and the view-scoped attach pattern.

### 3.4 `assertions.md`

Re-introduce the cross-link paragraph (removed by `76f46ada`) but with updated wording:

> Database-owned durable view objects are a separate surface created with `Database.create_view(...)`; they carry Database identity anchors and are consumed through `FactGraph.attach(db, schema_classes=[...], view=view)`. See [Database and durable views](database.md) for the full Database / durable view tutorial.

### 3.5 `namespace-map.md`

Near line 69 (attach row in the FactGraph-level surfaces table):

> See [Database and durable views](database.md) for the Database boundary and view-scoped attach pattern.

(Add as a short note row or sentence below the table — pick whichever fits the surrounding format.)

## 4. Expected Code / Docs Changes

Docs-only:

- `docs/official/kernel/quickstart/database.md` (new, ~340 LOC)
- `docs/official/kernel/quickstart/index.md` (+1 line, renumber)
- `docs/official/kernel/quickstart/persistence.md` (+1 cross-link line)
- `docs/official/kernel/quickstart/assertions.md` (+1 cross-link paragraph)
- `docs/official/kernel/quickstart/namespace-map.md` (+1 cross-link note)

Plus blueprint pair + INVENTORY (after archive).

Zero production files. Zero src changes. Zero test changes.

## 5. Tests / Verification

Smoke covering the database.md page end-to-end **with the new view-scoped attach branch**:

1. `Database.create(path, schema_ir=...)` + `db.head()`.
2. `FactGraph.attach(db, schema_classes=[...])` for write+read attached.
3. `fg.commit_assertions([AssertionInput(...)])`.
4. `view = db.create_view("name", [asrt_id])`.
5. `view_fg = FactGraph.attach(db, schema_classes=[...], view=view)` — verify read-only.
6. Verify mutation rejects on view-attached runtime.
7. `Database.open(path, schema_ir=...)` + reattach.

Plus `git diff --check` clean; only 5 files + blueprint pair touched; dirty baseline preserved at 6 M + 1 untracked.

## 6. Risks

| Risk | Mitigation |
|---|---|
| T5 database.md examples drift from current sdk import paths | Re-run all 7 smoke steps on T11.1 branch; fix anything that has moved. |
| §View-scoped attach section overlaps persistence.md's existing paragraph | Make database.md the canonical teaching site; persistence.md keeps its short paragraph + cross-link. No duplication of code examples. |
| Amend A2 checklist bullet might be misread as forbidding all view consumption | Be explicit that view= is shipped at attach-time, not at row-level read/eval. |
| Cross-link insertions reflow surrounding text and dirty more than expected | Insert as short sentences, no reflows. |

## 7. Implementation Plan

1. (this commit) Open scoped blueprint pair with reconciliation amends inventory.
2. Cherry-pick T5 `database.md` content (raw read from T5 branch) into T11.1 working tree.
3. Apply amends A1+A2+A3 to database.md.
4. Apply 4 cross-link edits to index.md / persistence.md / assertions.md / namespace-map.md.
5. Run 7-step end-to-end smoke (Database create → attach → commit → create_view → view-scoped attach → mutation rejects → open+reattach).
6. Self-review fresh-read pass.
7. Single feat commit.
8. Closure + archive.

## 8. Reviewer Focus

Self-review must verify:

- amend A1: no `# FactGraph.attach(db, view=view, ...)   # not shipped` line remains in database.md;
- amend A2: checklist bullet says `view=` is attach-time argument, not blanket "do not pass";
- amend A3: new §View-scoped attach section exists, teaches read-only behavior + mutation rejects;
- persistence.md still teaches `attach(..., view=view)` as shipped (no regression of T11.1 work);
- index.md sequence is 1-10 with database.md at #5;
- cross-link from assertions.md is precise (does not reintroduce removed wording verbatim if that wording would be stale);
- smoke 7/7 passes on T11.1 branch;
- 0 production file edits; 0 test edits; dirty baseline preserved.

## 9. Acceptance

- [ ] `docs/official/kernel/quickstart/database.md` exists, with A1+A2+A3 amends applied vs T5 source.
- [ ] `index.md` lists database.md as item #5; subsequent items renumbered.
- [ ] `persistence.md` gains a cross-link to database.md near the existing `attach(..., view=view)` paragraph.
- [ ] `assertions.md` gains a cross-link paragraph to database.md.
- [ ] `namespace-map.md` gains a cross-link to database.md near attach row.
- [ ] Smoke 7-step passes on T11.1 branch.
- [ ] Diff stays within 5 docs files + blueprint pair.
- [ ] Dirty baseline preserved at 6 M + 1 untracked.
- [ ] Sacred master at `562c74195df43e933bed92a3ff25de94dd8ce666` unchanged.

## 10. Outcome / Deviations

(Filled at closure.)
