# Docs-vs-Shipped Drift Fix Blueprint: Audit Log

- Blueprint: [2026-06-02_docs-vs-shipped-drift-fix.md](./2026-06-02_docs-vs-shipped-drift-fix.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-02 | draft | Blueprint pair created (Step 4.1) | Fork basis hard-coded as `80a60f66` (current feature-line HEAD; includes `80a60f66 docs(quickstart+module): align fg.entities coverage across quickstart and v2→v3 table` from 2026-06-02). Sacred master `562c74195df43e933bed92a3ff25de94dd8ce666` NOT used as fork basis per user directive 2026-06-02 — master is pre-v0.2 baseline, would pull audit subject back into old world. New branch `v0.2.0-blueprint-docs-vs-shipped-drift-fix-2026-06-02` created from `80a60f66`. Scope (LOCKED at Step 4.6 target): 7 findings — F1+F2+F3 (database.md `FrozenAssertionSet` 2-class disambiguation, merged at implementation layer into one paragraph rewrite per user directive; blueprint + preflight tables preserve 3 separate findings to keep factual boundary visible) + F4 (`conflicts(target)` signature) + F5 (`field(Field)` method row in §2.5) + F6 (`evaluate` reject list 3→7 items) + F7 (engine= default precision). Deferred 4 findings: F8 (head=closed_head wording) + F9 (§2.10/§2.11 numbering holes) + F10 (`ingest items` vs code `data` param name) + F11 (no standalone quickstart/package.md). Cadence: audit-then-fix lightweight pattern inherited from predecessor `2026-06-01_quickstart-docs-sync` archive. Step 4.7 budget = single docs commit, 2 target files (`docs/official/kernel/quickstart/database.md` + `src/factgraph/sdk/docs/04_api_surface.en.md`), estimated ~5-7 edit cells. Sacred Q-PR1 5-path 0-diff vs `4c472b50` verified at Step 4.1 entry (`git diff 4c472b50 HEAD -- <5 paths>` returns 0 lines). Dirty baseline 8 entries preserved (4 M + 2 D + 2 untracked). No push authorization; nothing pushed. Status: `draft` (will advance to `scoped` at Step 4.6). |

## Decision Notes

### 2026-06-02 — Fork basis hard-locked to `80a60f66`, not master

- **User directive at Step 4.1 entry**: do NOT fork from sacred master `562c74195df4...` — that branch is pre-v0.2 baseline and would force the audit subject to be re-evaluated against an old world. Hard-lock fork basis to the feature-line HEAD that contains the latest validated docs work (`80a60f66`).
- **Pre-flight verification** at Step 4.1 entry: `git merge-base --is-ancestor 80a60f66 HEAD` → PASS; in fact `HEAD == 80a60f66` at branch creation.
- **Branch creation**: `git checkout -b v0.2.0-blueprint-docs-vs-shipped-drift-fix-2026-06-02 80a60f66`.
- **Implication**: this blueprint inherits all of AD / B1 / B2 / C / E + baseline-cleanup + release-surface-audit + quickstart-docs-sync + the recent fg.entities docs alignment. Sacred master is unchanged through the entire cadence.

### 2026-06-02 — F1/F2/F3 merge at implementation layer, preserve as 3 findings in blueprint+preflight

- **User directive at Step 4.1 entry**: F1-F3 all live in the same paragraph (`database.md:357-358`), so the Step 4.7 edit can collapse them into one rewritten paragraph. BUT the blueprint + preflight tables must keep 3 separate finding rows — this prevents factual-boundary loss when this slice is later re-audited or cross-referenced.
- **Resolution recorded in blueprint**: §4.2 keeps F1 / F2 / F3 as separate table rows; §5.2 documents the implementation-layer merge with the 5 elements the rewritten paragraph must convey; §7 Acceptance lists "F1+F2+F3 merged fix" as one checkbox per implementation-layer reality.

### 2026-06-02 — Why audit-then-fix lightweight cadence (not full 9-stage spawn-per-finding)

- **Rule 1 fresh re-reads** of `sdk/store.py` were done during the precursor namespace-exploration session 2026-06-02; line citations are already attached to each finding. The audit findings table IS the scope freeze artifact (combined with Step 4.3 preflight artifact).
- **All 7 in-scope findings are (b)/(c)-class drift** per CADENCE 5-state classification — no new design decisions required, no public API behavior change.
- **Precedent**: 2026-06-01 `quickstart-docs-sync` cycle (`b3c99f2f`) successfully applied 33 findings in a single commit using this same lightweight pattern. The current 7-finding scope is even tighter — single commit is appropriate.
- **Step 4.3 preflight artifact** distinguishes this blueprint from a typo/comment-only edit exception path: the preflight artifact preserves line-citation evidence even after Step 4.7 edits remove the original drift text.

### 2026-06-02 — Why F8-F11 deferred (not promoted to in-scope)

- **F8 (`head=closed_head` rendering)**: existing wording is intelligible to readers familiar with the closed-head replay model (taught earlier in the same doc + in `assertions.md`). Reframing risks breaking the doc's narrative flow for marginal gain.
- **F9 (§2.10 / §2.11 numbering holes)**: cosmetic. Renumbering §2.12 → §2.10 etc. risks breaking cross-references (anchors) outside this blueprint's scope. Defer until a §2.x renumbering blueprint is opened (probably bundled with other section-restructure work).
- **F10 (`ingest(items, ...)` vs code `data` formal name)**: positional parameter; user-invisible. Rename costs more than benefit at this slice's risk surface.
- **F11 (no standalone `quickstart/package.md`)**: requires non-trivial new content authoring (use cases, examples, error patterns). Out of audit-then-fix lightweight cadence scope. Probably wants its own draft blueprint with content design.

### 2026-06-02 — Why this blueprint does NOT touch Q-NAMING-F

- Q-NAMING-F sub-slice is currently in flight on a separate impl branch (`v0.2.0-impl-build-application-rule-when-rename-2026-06-01` covers a related but distinct concern). N4 carve-out keeps these branches isolated.
- F findings (F1-F11) emerged from `fg.assertion_views` + `fg.assertions` + `fg.audit` + `fg.eval` namespace audits — none overlap Q-NAMING-F's `SemanticsProfile` / `EngineProfile` rename surface.
- Q-NAMING-F can advance independently. Once both archive cleanly, downstream consumers re-project both docs HEAD + impl HEAD on their own schedule.
