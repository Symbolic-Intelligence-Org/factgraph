# Quickstart Docs Code-vs-Shipped Sync Blueprint

- Status: scoped
- Created: 2026-06-01
- Last Updated: 2026-06-01
- Related Modules:
  - `docs/official/kernel/index.md` (top-level kernel docs entry)
  - `docs/official/kernel/quickstart/*.md` (11 quickstart docs)
- Related Docs:
  - [`workflow/audit/active/2026-06-01_quickstart-vs-shipped.md`](../../audit/active/2026-06-01_quickstart-vs-shipped.md) — paired audit doc with 33 findings
  - [`workflow/blueprints/archive/2026-06-01_release-surface-audit.md`](./2026-06-01_release-surface-audit.md) — predecessor; identified the projection scope this audit deepens
  - [`workflow/blueprints/archive/2026-06-01_baseline-drift-cleanup.md`](./2026-06-01_baseline-drift-cleanup.md) — cleared 189 → 0 baseline; this audit verifies docs match post-cleanup code
- Audit Log:
  - [2026-06-01_quickstart-docs-sync.audit.md](./2026-06-01_quickstart-docs-sync.audit.md)

## 1. Problem

After Q-NAMING 6-phase + Baseline Drift Cleanup + Release Surface Audit cycles all archived 2026-06-01, the user reported partial code-doc drift in `docs/official/kernel/quickstart/`. An initial lightweight check found 11 `build_application_rule` `when=` vs `where=` sites (fixed in `d12352e4` docs-sync slice). User then requested **strict full audit** of all quickstart docs vs shipped code.

7 parallel general-purpose agents + supplementary verification surfaced 33 actionable findings (18 DRIFT + 13 AMBIGUOUS + 2 BUG) catalogued in the paired vs-shipped audit doc.

## 2. Goals

- **G1**: Land all P0 fixes (2 user-runtime-error sites) — namespace-map.md `Query` claim, rules-and-inferences.md `AggregateAtom` claim
- **G2**: Land all P1 fixes (4 broken cross-references) — 3 missing assertions.md sections + 1 broken anchor in namespace-map.md
- **G3**: Land all P2 fixes (13 sites) — signature drift + project-name `factpy-kernel` → `factgraph` rename
- **G4**: Land all P3 fixes (13 prose polish sites) — ambiguous wording, missing kw-only markers, snippet context
- **G5**: Re-project factgraph feature branch with updated quickstart content (force-push amended)
- **G6**: Push origin governance branches + archive blueprint pair

## 3. Non-goals

- N1: NOT modifying `src/factgraph/` source code (docs-only sync)
- N2: NOT touching Q-PR1 5 sacred paths
- N3: NOT modifying `hnsm-backend/master` or `v0.1-oss-prep`
- N4: NOT touching `factgraph/main` or `factgraph/release/*`
- N5: NOT executing `scripts/release.sh`
- N6: NOT auditing module docs under `src/factgraph/*/docs/` (separate ownership per `src/factgraph/AGENTS.md`)
- N7: NOT auditing workflow / non-quickstart docs
- N8: NOT touching the dirty baseline (8 entries preserved)
- N9: NOT changing public API behavior (semantic-preserving doc fixes only)

## 4. Current Context

### §4.1 Branch + sacred state

- Branch `v0.2.0-blueprint-quickstart-vs-shipped-audit-2026-06-01` forked from `d12352e4` (docs-sync slice HEAD)
- Inherits all Q-NAMING + baseline cleanup + release-surface-audit contracts
- Sacred master `562c74195df43e933bed92a3ff25de94dd8ce666` unchanged
- Q-PR1 5 sacred paths 0-diff vs `4c472b50`
- Dirty baseline 8 entries preserved

### §4.2 Audit findings summary (per paired audit doc)

| Priority | Count | Class |
|---|---|---|
| P0 (user-runtime-error) | 2 | (c) shape conflict |
| P1 (broken cross-ref) | 4 | (c) shape conflict + (b) small gap |
| P2 (signature/wording drift) | 13 | (b) small gap |
| P3 (prose polish) | 13 | (b) small gap |

## 5. Proposed Shape

### §5.1 Single fix commit per priority tier (audit-then-fix lightweight cadence)

Following the docs-only post-archive sync pattern established 2026-06-01 in `d12352e4`:

1. Single commit `docs(quickstart): apply 33 audit findings (P0+P1+P2+P3)` on this blueprint branch
2. Re-project factgraph feature branch with updated quickstart content
3. Closure + archive

### §5.2 Why not full 9-stage CADENCE per fix?

This is docs-only work with audit-grounded findings. The audit doc IS the scope freeze. Step 4.7 implementation is the single fix commit. Per CLAUDE.md exception path:

> "For any non-trivial feature, refactor, protocol change, cross-module change, or architecture-facing task, create or reuse a task blueprint before editing code."

The audit doc + this blueprint qualify as "task blueprint". Single sustaining commit + closure is appropriate.

## 6. Boundaries And Invariants

- **Q-PR1 sacred 5 paths**: 0-diff vs `4c472b50` preserved through every commit
- **Sacred master**: never modified
- **Dirty baseline**: 8 entries preserved
- **No src/ touch**: all fixes are in `docs/official/kernel/`
- **Inherited contracts**: AD/C/E/B1/B2/F + baseline cleanup + release-surface-audit N-rows all preserved
- **Semantic preservation**: doc fixes must NOT change public API behavior or contracts — they describe what code already does
- **factgraph re-projection**: same overlay strategy as `ec85b287`/`ca916dee` — preserve 11 publish-infra files from factgraph/main, replace src/tests/, add docs/SECURITY.md + .github/workflows/factgraph-tests.yml from staging, copy docs/official/* from hnsm-backend

## 7. Acceptance

- [ ] All 2 P0 fixes landed (PF-R1 + PF-R2)
- [ ] All 4 P1 fixes landed (PF-R3 + PF-R4); 2 new sections added to assertions.md
- [ ] All 13 P2 fixes landed (PF-R5..PF-R9)
- [ ] All 13 P3 fixes landed (PF-r1..PF-r13)
- [ ] Post-fix grep for `factpy-kernel` in `docs/official/` returns 0 hits
- [ ] Post-fix grep for `when=` immediately following `build_application_rule(` returns 0 hits
- [ ] Post-fix grep for `AggregateAtom` in `rules-and-inferences.md:84` paragraph returns 0 hits
- [ ] All cross-doc anchors verified resolvable
- [ ] factgraph feature branch force-pushed with updated quickstart
- [ ] Q-PR1 sacred 5 paths 0-diff vs `4c472b50` preserved
- [ ] Sacred master unchanged
- [ ] Dirty baseline 8 entries preserved
- [ ] No `release.sh` execution
- [ ] AD/C/E/B1/B2/F + baseline cleanup + release-surface-audit inherited contracts preserved

## 8. Implementation Plan

1. **Audit doc** at `workflow/audit/active/2026-06-01_quickstart-vs-shipped.md` — DONE
2. **Single fix commit** on this branch applying all 33 findings
3. **Re-project factgraph feature branch** via worktree overlay + force-push (4th force-push iteration)
4. **Step 4.8 closure**: Status `scoped` → `implemented` + Outcome summary
5. **Step 4.9 archive**: `git mv` blueprint + audit doc pair + update `INVENTORY.md`
6. **Push origin branches** per user authorization

## 9. Docs To Update

- This blueprint's audit log (`2026-06-01_quickstart-docs-sync.audit.md`)
- All 12 quickstart docs per §3 audit findings
- `workflow/blueprints/archive/INVENTORY.md` (Step 4.9)

## 10. Outcome / Deviations

(Step 4.8 closure outcome to be filled post-Step 4.7 fix commit + factgraph re-projection.)
