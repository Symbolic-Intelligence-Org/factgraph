# Task Blueprint: N10 Reference Index Cleanup

- Status: scoped
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: S (docs-only top-level index rebase)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Claude
- Reviewer: — (single-actor S-scope; cross-flip inverted per user authorization)
- Related audit: `workflow/blueprints/active/2026-05-27_n10-reference-index-cleanup.audit.md`
- Roadmap source: `workflow/design/design-points/active/post-t5-completion-roadmap.zh.md` (N10 entry)

## 0. Scope Locks

### In scope

Update only the top-level `docs/references/README.md` so it accurately routes a current reader to:

- the current implementation truth location (`src/factgraph/*/docs/` post-rename);
- the current blueprint state machine and archive (`workflow/blueprints/...`);
- the current historical archive (`workflow/heritage/blueprint_history/`);
- the current architecture principles (`workflow/foundations/architecture_principles.md`);
- the canonical home of design-point research notes (`workflow/design/design-points/{active,archive}/`), which is where the notes referenced inline by name now live;
- the previously unindexed `working/factgraph-namespace-test-proposals/` bundle;
- the previously unindexed `working/post-routemap-direction-selection-input/` bundle (added at amend; same class as `factgraph-namespace-test-proposals/`).

Refresh the "当前条目 (... wrap-up 后)" header date to 2026-05-27 to match the cleanup batch.

### Out of scope

- `docs/references/working/design-points/readme.md` is part of the preserved dirty baseline (4 M + 1 U). Do not edit.
- `docs/references/working/load-test-2026-04-11/` and other historical bundle sub-READMEs. These are time-frozen working notes; their `src/factpy_kernel/...` and `docs/blueprints/...` strings reflect the repository state at the bundle date and are preserved verbatim under `working/` non-authoritative semantics.
- Any production code, tests, examples, notebooks, SDK API, service, agent, or adapter file.
- `external/`, `bridges/`, `templates/` content — out of scope unless an inline link is verifiably broken.
- Adding new design-point notes, moving existing notes, or rewriting their content.
- Push. Push needs a separate single-shot authorization.

### Stop / amend triggers

Pause and amend if Step 4.6 inventory finds:

- a top-level README replacement would require editing the dirty-baseline `working/design-points/readme.md` to stay coherent;
- the design-point migration target (`workflow/design/design-points/`) does not actually exist or is in a partially-migrated state that would make the pointer misleading;
- a historical bundle README has a path string that is not time-frozen and would mislead a current reader (e.g., a "current implementation" line that was never a historical snapshot);
- the cleanup needs to add content beyond pointer/path corrections + one missing entry (would expand from S to M).

## 1. Problem

`docs/references/README.md` is the top-level routing file for `docs/references/`. It currently routes a reader to several locations that have either moved or been renamed:

- `src/factpy_kernel/*/docs/` — package rename to `factgraph` shipped in T11.3; canonical path is `src/factgraph/*/docs/`.
- `docs/blueprints/` and `docs/blueprint_history/` — moved into `workflow/blueprints/...` and `workflow/heritage/blueprint_history/` under the workflow consolidation.
- `docs/architecture_principles.md` — moved into `workflow/foundations/architecture_principles.md`.
- The `working/design-points/` subsection lists per-note inline links (`identity-primary-key-coordinate-semantics.md`, `possibility-probability-transmission.zh.md`, `post-track3-semantics-public-api.zh.md`, `rule-query-inference-head-semantics.zh.md`) at `./working/design-points/<note>`. None of those files exist at that path; the canonical content has migrated to `workflow/design/design-points/archive/`. Only `docs/references/working/design-points/readme.md` itself remains at the old location, and that file is in the preserved dirty baseline.
- `working/factgraph-namespace-test-proposals/` exists on disk with its own README but is not indexed by the top-level README.
- The "当前条目（2026-05-06 wrap-up 后）" anchor date reflects a 2026-05-06 batch that predates T1-T5, T11.1, T11.2.6, T11.2.7, T11.2.9, T11.3, T6, and T12.

A reader who follows the current README will arrive at non-existent paths for the design-point notes and will miss the canonical design-point home entirely.

## 2. Inputs

| Source | Purpose |
|---|---|
| `docs/references/README.md` | Edit target. |
| `CLAUDE.md` | Authoritative path mapping for workflow governance / module docs convention / architecture principles location. |
| `workflow/design/design-points/active/` and `workflow/design/design-points/archive/` | Canonical home of design-point research notes; pointer target. |
| `workflow/design/design-points/README.md` | Canonical design-point lifecycle README; pointer target. |
| `docs/references/working/factgraph-namespace-test-proposals/README.md` | Sub-bundle README; entry text source for the new top-level row. |
| `docs/references/working/design-points/readme.md` | Dirty-baseline file. Read-only for this cycle. Inline links there will continue to point at the old path; that's a separate cleanup outside N10. |

## 3. Proposed Shape

### 3.1 Governance line rebase

Lines 16-18, 25 currently use pre-rename / pre-workflow paths. Rebase each to the current canonical path. Keep the boundary-statement structure unchanged (still three "本目录不是…" lines plus the workflow-rules item).

### 3.2 Design-points subsection rebase

Replace the inline per-note listing with a single concise pointer:

- explain that `working/design-points/` is the historical home of design-point research notes;
- direct readers to `workflow/design/design-points/{active,archive}/` for the canonical inventory;
- note that the `working/design-points/readme.md` file is still present (dirty-baseline non-authoritative working surface).

Do not delete the subsection header — keep it as a visible breadcrumb, with the pointer body.

### 3.3 Unindexed working/ bundle entries

Two `working/` sub-bundles exist on disk but are not in the top-level index. Add a subsection for each, pulling one-line descriptions from the bundle READMEs:

- `working/factgraph-namespace-test-proposals/` — review packet for the 2026-05-14 namespace-test-coverage blueprint.
- `working/post-routemap-direction-selection-input/` — 8-file post-routemap direction selection bundle (2026-05-07; produced A+B path).

Both subsections live under the `working/` heading, alongside the existing `working/load-test-2026-04-11/` and `working/rule-replay-line-redesign-input/` subsections.

### 3.4 Anchor date refresh

Update "（2026-05-06 wrap-up 后）" to "（2026-05-27 N10 cleanup 后）". Keep the "Index 完整覆盖" sentence accurate by re-reading the directory at implementation time.

### 3.5 Preservation discipline

- No changes to `external/` / `bridges/` / `templates/` entries.
- No changes to root-level `.md` entries (`agentic-document-extraction-research.md`, `cross-provider-entity-benchmark-report.md`, `cross-domain-compliance-framing.md`, `esa-positioning.md`, `product-readiness-audit-2026-04-09.md`, plus the two binaries).
- No changes to historical bundle sections (load-test-2026-04-11/, rule-replay-line-redesign-input/, post-routemap-direction-selection-input/).
- No changes to `working/design-points/readme.md` (dirty baseline).

## 4. Expected Changes

Single-file edit:

- `docs/references/README.md` — governance line rebase + design-points subsection rebase + new `factgraph-namespace-test-proposals/` row + anchor date refresh.

Plus the standard cycle artifacts (this blueprint + audit, archive moves, `workflow/blueprints/archive/INVENTORY.md` entry).

## 5. Step 4.6 Inventory Plan

To fill at scoped commit:

1. Confirm `docs/references/README.md` current line numbers for each stale path (re-read).
2. Confirm `workflow/design/design-points/` structure (active + archive + README presence).
3. Confirm `docs/references/working/factgraph-namespace-test-proposals/README.md` exists and capture its one-line description.
4. Confirm dirty baseline still 4 M + 1 U.
5. Confirm sacred master at `562c74195df43e933bed92a3ff25de94dd8ce666`.
6. Confirm no other inbound references to the about-to-change subsection titles exist that would silently rot (e.g., other docs linking to `docs/references/README.md#working-design-points`).

### 5.1 Scoped Inventory Results

| # | Item | Result |
|---|---|---|
| 1 | Stale path lines in `docs/references/README.md` | Line 16 `src/factpy_kernel/*/docs/`; line 17 `docs/blueprints/`; line 18 `docs/blueprint_history/` + `docs/blueprints/archive/`; line 25 `docs/architecture_principles.md`. Line 28 anchor date `2026-05-06`. |
| 2 | `workflow/design/design-points/` structure | `README.md` present. `active/` holds 6 notes (database-view, evidence-tree-v1, match-api-design, post-t5-completion-roadmap, rule-expression-and-proof-attempt, rule-expression-and-proof-track-plan). `archive/` holds 9 migrated notes including the four previously listed inline in `docs/references/README.md` (identity-primary-key-coordinate-semantics{,.zh}, possibility-probability-transmission.zh, post-track3-semantics-public-api.zh, rule-query-inference-head-semantics.zh) plus five others (read-write-snapshot-assertion-selection.zh, rule-policy-function-tree-and-syntax.zh, factgraph-lifecycle-and-assets.zh, query-view-and-inference-handles.zh). |
| 3 | `factgraph-namespace-test-proposals` description | Review packet of proposed test changes for the 2026-05-14 namespace-test-coverage blueprint; contains stale/conflict/missing analysis notes plus three Python test files; not part of root `tests/`, not discovered by unittest, not release-gate truth. |
| 3a | `post-routemap-direction-selection-input` description (added at amend) | 2026-05-07 strategic input bundle (8 files: inventory, implicit gaps, 9 candidates, recommendation A+B, walker/builder design sketches, migration path); non-authoritative working reference equivalent to `rule-replay-line-redesign-input/`; produced the A+B paths that became `project_a_b_v0.1_surface_published.md`. |
| 4 | Dirty baseline | 4 modified (`docs/references/working/design-points/readme.md`, three example notebooks) + 1 untracked (`"rainbird-ai sdk code/"`). Preserved. |
| 5 | Sacred master | `562c74195df43e933bed92a3ff25de94dd8ce666`. Confirmed. |
| 6 | Inbound references to about-to-change anchors | `rg -l 'docs/references/README.md#' . --type md` returns only the N10 blueprint pair itself. No external/historical doc anchors into the design-points subsection header. Safe to keep header text or rename; this cycle keeps the header text unchanged out of conservatism. |

## 6. Verification

- `git diff --check` clean.
- `git diff docs/references/README.md` is the only non-blueprint diff in the implementation commit.
- Dirty baseline stays at 4 M + 1 U.
- Sacred master stays at `562c74195df43e933bed92a3ff25de94dd8ce666`.
- All replaced path strings can be `rg`-grepped in the new README and resolve to live targets (i.e., no broken inline link introduced by the rebase).
- No new file created outside `workflow/blueprints/active/` (and later `workflow/blueprints/archive/`).

## 7. Risks

| Risk | Mitigation |
|---|---|
| Rebased subsection silently breaks an inbound link from elsewhere in the repo | Step 4.6 grep for inbound anchor references; if present, leave the subsection header text unchanged. |
| Replacing per-note listing loses a useful breadcrumb to a reader who only knows the old path | Keep the subsection header and add an explicit "moved to …" pointer line rather than deleting the subsection. |
| `working/design-points/readme.md` continues to list non-existent inline files | Out of scope (dirty baseline). Recorded as follow-up for a future cycle that owns the dirty-baseline file. |
| Anchor date refresh implies the listing is now complete | Implementation must re-verify "Index 完整覆盖" before claiming so in the date line. |

## 8. Acceptance

- [ ] Step 4.6 inventory recorded in §5.1.
- [ ] Governance lines 16-18, 25 use current canonical paths.
- [ ] Design-points subsection routes to canonical `workflow/design/design-points/`.
- [ ] `factgraph-namespace-test-proposals/` indexed.
- [ ] `post-routemap-direction-selection-input/` indexed (amend addition).
- [ ] Anchor date refreshed.
- [ ] `workflow/blueprints/archive/INVENTORY.md` updated when this blueprint archives.
- [ ] No production behavior changes.
- [ ] Dirty baseline and sacred master preserved.

## 9. Outcome / Deviations

To fill at closure.

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
