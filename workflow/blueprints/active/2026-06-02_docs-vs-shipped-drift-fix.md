# Docs-vs-Shipped Drift Fix Blueprint: post-`80a60f66` strict re-audit findings

- Status: draft
- Created: 2026-06-02
- Last Updated: 2026-06-02
- Fork basis: **`80a60f66`** (current feature-line HEAD; contains the fg.entities docs alignment commit). **NOT forked from sacred master** — that baseline is pre-v0.2 and would pull the audit subject back into the old world.
- Related Modules:
  - `docs/official/kernel/quickstart/database.md` (P0 site)
  - `src/factgraph/sdk/docs/04_api_surface.en.md` (P1 + P2 sites)
- Related Code (read-only references for line citations):
  - `src/factgraph/sdk/store.py:117-119` — SDK `FrozenAssertionSet` (2 fields)
  - `src/factgraph/core/store/database.py:75-81` — Database `FrozenAssertionSet` (6 fields)
  - `src/factgraph/sdk/store.py:86` — `from ... import FrozenAssertionSet as DatabaseFrozenAssertionSet`
  - `src/factgraph/sdk/store.py:355-377` — `fg.assertion_views.create` return type
  - `src/factgraph/sdk/store.py:480-501` — `fg.assertions.field(Field)` public method
  - `src/factgraph/sdk/store.py:1326-1339` — `fg.audit._resolve_record_asrt_id` + `_claim_for_audit_target` (asrt_id string / object-with-`.asrt_id` resolution path shared by `explain` and `conflicts`)
  - `src/factgraph/sdk/store.py:1341-1371` — `fg.audit._conflict_cell_for_target` target normalization (handles `(entity, Field)` and `(entity, field_name)` tuple shapes in addition to inheriting the asrt_id-string / object-with-`.asrt_id` shapes via `_claim_for_audit_target`)
  - `src/factgraph/sdk/store.py:1373-1389` — `fg.audit.{explain,conflicts,diff_proof_frames}` signatures
  - `src/factgraph/sdk/store.py:2374-2461` — `fg.eval.evaluate` signature + reject set
  - `src/factgraph/sdk/store.py:2463-2502` — `fg.eval.explain` signature
- Related Docs (prior cadence precedents):
  - [`workflow/blueprints/archive/2026-06-01_quickstart-docs-sync.md`](../archive/2026-06-01_quickstart-docs-sync.md) — immediate predecessor; established audit-then-fix lightweight cadence template that this blueprint reuses
  - [`workflow/blueprints/archive/2026-06-01_release-surface-audit.md`](../archive/2026-06-01_release-surface-audit.md) — defined the release-surface projection that downstream consumes
- Audit Log:
  - [2026-06-02_docs-vs-shipped-drift-fix.audit.md](./2026-06-02_docs-vs-shipped-drift-fix.audit.md)

## 1. Problem

While answering a user namespace-exploration session (2026-06-02), strict Rule-1 fresh re-reads of `src/factgraph/sdk/store.py` revealed **11 docs-vs-shipped drift findings** (3 P0 factual errors, 3 P1 content errors, 4 P2/P3 style/numbering). The P0 cluster all reside in `docs/official/kernel/quickstart/database.md:357-358` and stem from a single root cause: documentation author conflated two same-named-but-different `FrozenAssertionSet` dataclasses across SDK vs Database layers. The P1 cluster all reside in `src/factgraph/sdk/docs/04_api_surface.en.md` and stem from incremental signature drift not picked up by the predecessor `quickstart-docs-sync` cycle (which scoped to quickstart-tier docs only, leaving `sdk/docs/` untouched).

These findings remained after the `80a60f66` fg.entities docs alignment commit (2026-06-02). They are independent of the Q-NAMING-F sub-slice currently in flight on a separate impl branch.

## 2. Goals

- **G1** — Fix all 3 P0 factual errors in `database.md:357-358` by replacing the misleading "same 6-field dataclass" framing with the correct "two same-named-but-different classes across SDK vs Database layers" framing. Single paragraph rewrite at implementation layer; preserve 3 separate findings in blueprint + preflight tables for factual-boundary integrity per user directive.
- **G2** — Fix P1.F4 in `04_api_surface.en.md:398` — `fg.audit.conflicts()` signature → `conflicts(target)`.
- **G3** — Fix P1.F5 in `04_api_surface.en.md` §2.5 table — add row for `field(Field) -> AssertionView` method (currently omitted).
- **G4** — Fix P1.F6 in `04_api_surface.en.md:362-363` — document all 7 deprecated/blocked kwargs `fg.eval.evaluate(...)` rejects, with the **hard-presence vs non-None distinction** preserved: `view=`, `policy=`, `semantics_profile=`, `mode=`, `temporal_view=` reject on key presence alone (even `key=None` raises); `registry=`, `engine_options=` reject only when the popped value is **non-None**.
- **G5** — Fix P2.F7 in `04_api_surface.en.md:358-359` — clarify `engine=` default value (signature default `None`; effective default `"native"` resolved internally).
- **G6** — All edits in a single Step 4.7 commit; cadence Step 4.8 closure + Step 4.9 archive.

## 3. Non-goals

- **N1** — NOT modifying `src/factgraph/` source code (docs-only fix slice).
- **N2** — NOT touching Q-PR1 5 sacred paths (`core/evidence/write_protocol.py`, `core/store/ledger.py`, `core/store/_builders.py`, `adapters/pyreason/`, `core/derivation/accept.py`). All targets are markdown documentation only.
- **N3** — NOT modifying sacred `master @ 562c74195df43e933bed92a3ff25de94dd8ce666`.
- **N4** — NOT modifying the current Q-NAMING-F impl branch (`v0.2.0-impl-build-application-rule-when-rename-2026-06-01`) — separate concern.
- **N5** — NOT executing `scripts/release.sh` (no release surface projection update; downstream consumers re-pick on their own schedule).
- **N6** — NOT touching the dirty baseline (8 entries: 4 M + 2 D + 2 untracked); they remain untouched through every commit.
- **N7** — NOT auditing or fixing module docs under `src/factgraph/*/docs/` beyond the two named files (sibling-module scope discipline).
- **N8** — NOT auditing workflow / blueprint / heritage docs.
- **N9** — NOT auditing prose-quality of unrelated `04_api_surface.en.md` sections (§2.1 / §2.2 / §2.3 / §2.4 / §2.7 / §2.8 / §2.9 / §2.13 / §2.14 / §2.15 are out of scope; only §2.5 / §2.6 / §2.12 are touched).
- **N10** — NOT changing any public API behavior (docs describe what code already does; semantic-preserving fixes only).
- **N11** — NOT renumbering `04_api_surface.en.md` §2.x sections to close the §2.10/§2.11 numbering hole — deferred (F9).
- **N12** — NOT adding a standalone `quickstart/package.md` doc — deferred (F11).
- **N13** — NOT changing `ingest` parameter name from `items` (doc) to `data` (code) — deferred (F10); user-visible behavior identical, edit costs more than benefits at this slice's risk surface.
- **N14** — NOT clarifying the `head=closed_head` rendering convention in §2.6 (F8) — deferred; existing wording is intelligible to readers familiar with the closed-head replay model.
- **N15** — NOT re-projecting any factgraph-line feature branch; this is hnsm-backend-internal docs work. Re-projection scheduled at a downstream consumer's discretion.

## 4. Current Context

### §4.1 Branch + sacred state

- New blueprint branch `v0.2.0-blueprint-docs-vs-shipped-drift-fix-2026-06-02` created **from `80a60f66`** (current feature-line HEAD at Step 4.1 entry).
- 930 commits ahead of sacred master `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Q-PR1 5-path 0-diff vs `4c472b50`: ✅ verified at Step 4.1 entry (`git diff 4c472b50 HEAD -- <5 paths>` returns 0 lines).
- Dirty baseline 8 entries preserved (4 M + 2 D + 2 untracked).
- No push authorization issued; nothing pushed.

### §4.2 Audit findings summary (Step 4.1 entry; subject to Step 4.3 preflight refinement)

| ID | Severity | File | Location | Drift class |
|---|---|---|---|---|
| **F1** | 🔴 P0 | `quickstart/database.md` | L357 | (c) shape conflict: SDK `FrozenAssertionSet` 6-field claim vs 2-field reality |
| **F2** | 🔴 P0 | `quickstart/database.md` | L358 | (c) shape conflict: "same 6-field dataclass" claim — two different classes |
| **F3** | 🔴 P0 | `quickstart/database.md` | L357 | (c) shape conflict: claimed "SDK-owned anchors" fields don't exist on SDK class |
| **F4** | 🟡 P1 | `sdk/docs/04_api_surface.en.md` | L398 | (b) signature drift: `conflicts()` shown zero-arg, code is `conflicts(target)` |
| **F5** | 🟡 P1 | `sdk/docs/04_api_surface.en.md` | §2.5 table | (b) omitted method row: `field(Field) -> AssertionView` |
| **F6** | 🟡 P1 | `sdk/docs/04_api_surface.en.md` | L362-363 | (b) under-specified reject list (3 of 7 items shown);also lacks the **hard-presence vs non-None reject distinction** (5 keys reject on presence; 2 keys reject only on non-None value) |
| **F7** | 🟢 P2 | `sdk/docs/04_api_surface.en.md` | L358-359 | (b) signature precision: `engine='native'` shown as default, true default is `None` (resolved → `"native"`) |
| **F8** | 🟢 P3 | `sdk/docs/04_api_surface.en.md` | L359 | (b) `head=closed_head` looks like default, head is required |
| **F9** | 🟢 P3 | `sdk/docs/04_api_surface.en.md` | numbering | §2.10 / §2.11 holes from `648c0b6c` What-if removal |
| **F10** | 🟢 P3 | `sdk/docs/04_api_surface.en.md` | L280 | (b) `ingest(items, ...)` vs code formal `data` |
| **F11** | 🟢 P3 | `docs/official/kernel/quickstart/` | (no file) | structural: no standalone `package.md` quickstart |

**In-scope (LOCKED at Step 4.6)**: F1, F2, F3, F4, F5, F6, F7 — 7 findings.
**Deferred to §10 carry-forward**: F8, F9, F10, F11.

### §4.3 Predecessor cadence inheritance

- AD / B1 / B2 / C / E + baseline-cleanup + release-surface-audit + Q-NAMING-F (F is independent active impl) + quickstart-docs-sync (`b3c99f2f`) all preserved.
- This slice operates entirely within the docs layer; no source code or release surface allowlist changes. Inherited contracts pass through unchanged.

## 5. Proposed Shape

### §5.1 Single Step 4.7 docs commit

Following the precedent established by `b3c99f2f docs(quickstart): apply 33 audit findings (P0+P1+P2+P3)`:

- One commit on this blueprint branch: `docs(quickstart+sdk): fix 7 docs-vs-shipped drift findings (P0+P1+P2)`.
- 2 target files; estimated ~5-7 edit cells; net ~25 lines insertions / ~15 lines deletions.
- Audit-then-fix lightweight cadence (no separate impl branch needed since work is docs-only and audit-grounded).

### §5.2 F1+F2+F3 merged-paragraph fix (implementation-layer collapse only)

Per user directive at Step 4.1 entry: F1, F2, F3 may merge at implementation layer into a single rewritten paragraph at `database.md:355-362`. The paragraph will:

1. Acknowledge two `FrozenAssertionSet` classes exist with the same name across `factgraph.sdk` and `factgraph.core.store.database`.
2. Show SDK-layer 2-field schema (`name: str`, `asrt_ids: frozenset[str]`).
3. Show Database-layer 6-field schema (`name`, `db_id`, `base_tx_id`, `schema_digest`, `asrt_ids: tuple[str, ...]`, `view_digest`).
4. Explain why the SDK file uses `import ... as DatabaseFrozenAssertionSet` rename to disambiguate.
5. Keep the comparative-purposes section header (`## SDK views are different`) intact.

**Blueprint + preflight table preserve 3 separate F1/F2/F3 findings** to keep factual boundary visible during review and to enable future re-audit cross-referencing.

### §5.3 F4 / F5 / F6 / F7 in `04_api_surface.en.md`

- **§2.5 Assertions table (L344-348)**: add row `field(field: Field) -> AssertionView` between `by_ids` and `where`.
- **§2.6 Eval table (L358-359)**: replace `engine='native'` → `engine=None` in signature rendering; add parenthetical "(resolved to `'native'` if not provided; permitted: `native`/`souffle`/`problog`/`pyreason`)" inline or as following sentence.
- **§2.6 Eval rejection sentence (L362-363)**: replace "Public `evaluate(...)` rejects `engine_options=`, `registry=`, `mode=`, and candidate compatibility flags." with a 7-item enumeration that preserves the two reject mechanisms distinct: (a) hard-presence reject (5 keys: `view=`, `policy=`, `semantics_profile=`, `mode=`, `temporal_view=`) — even `key=None` raises; (b) non-None reject (2 keys: `registry=`, `engine_options=`) — popped with `None` default, only non-None values raise. Source: `sdk/store.py:2375-2395`.
- **§2.12 Audit table (L397-399)**: change `conflicts()` → `conflicts(target)`; replace the vague "entity field cell" hint with the **4 accepted target shapes** from `_resolve_record_asrt_id` (1326-1339) + `_conflict_cell_for_target` (1341-1371):
  1. assertion id string
  2. object exposing `.asrt_id` (e.g. `AssertionRecord`)
  3. `(entity, Field)` tuple where `entity` is a ref string or object with `.ref`
  4. `(entity, field_name: str)` tuple where `entity` is a ref string or object with `.ref`
  Shapes 1+2 are inherited via `_claim_for_audit_target`; shapes 3+4 are the tuple-branch additions specific to `conflicts`. Note: `fg.audit.explain(target)` accepts only shapes 1+2 (no tuple branch); §2.12 sub-text or footnote should call this out so users do not assume the tuple shapes work for `explain`.

### §5.4 Cadence step plan (parallel to §5.1)

| Step | Action | Output |
|---|---|---|
| 4.1 | Blueprint draft + audit log row 1 (this commit) | `status: draft` |
| 4.2 | Self fast-pass (Rule 1 re-read line citations §4.2 table) | audit row 2 |
| 4.3 | Preflight artifact at `workflow/audit/active/2026-06-02_docs-vs-shipped-drift-fix-preflight.md` with line-citation table per F1-F7 | preflight branch artifact |
| 4.4 | Apply preflight findings back to blueprint if any | audit row 3 |
| 4.5 | Self review final | audit row 4 |
| 4.6 | **Scope freeze** (`draft → scoped`) | audit row 5 |
| 4.6.5 | Pre-impl grep (verify F1-F7 footprint unchanged) | audit row 6 |
| 4.7 | **Single docs commit** (~5-7 edit cells, 2 files) | feat commit |
| 4.8 | Closure (`scoped → implemented` + §10 Outcome + Deferred carry-forward) | audit row 7 |
| 4.9 | Archive (`git mv` blueprint pair + INVENTORY.md row) | audit row 8 |

## 6. Boundaries And Invariants

- **Q-PR1 sacred 5 paths**: 0-diff vs `4c472b50` preserved through every commit.
- **Sacred master `562c74195df43e933bed92a3ff25de94dd8ce666`**: never modified.
- **Dirty baseline 8 entries**: preserved through every commit.
- **No src/ touch**: all fixes in `docs/official/kernel/quickstart/database.md` and `src/factgraph/sdk/docs/04_api_surface.en.md` (the second path is module docs not source code — `*.md` only).
- **Inherited contracts**: AD / B1 / B2 / C / E + baseline cleanup + release surface audit + Q-NAMING-F (independent active impl) + quickstart-docs-sync — all preserved.
- **Semantic preservation**: doc fixes describe what code already does; no public API behavior change.
- **No release.sh execution**: this slice does not refresh the release surface projection.
- **No push**: nothing leaves the local branch without explicit user authorization.

## 7. Acceptance

- [ ] **F1+F2+F3 merged fix**: `quickstart/database.md:355-362` paragraph rewritten with 2-class disambiguation
- [ ] **F4**: `04_api_surface.en.md:398` `conflicts(target)` signature + **4 accepted target shapes enumerated** (asrt_id string / object with `.asrt_id` / `(entity, Field)` tuple / `(entity, field_name)` tuple) + footnote that `fg.audit.explain(target)` accepts only shapes 1+2 (no tuple branch)
- [ ] **F5**: `04_api_surface.en.md` §2.5 table includes `field(Field) -> AssertionView` row
- [ ] **F6**: `04_api_surface.en.md` L362-363 documents all 7 rejected kwargs **with the hard-presence (5 keys) vs non-None (2 keys) reject mechanism distinction preserved**
- [ ] **F7**: `04_api_surface.en.md` L358-359 engine default precision corrected
- [ ] Post-fix grep for `6 fields` in `quickstart/database.md` returns 0 hits
- [ ] Post-fix grep for `conflicts()` (zero-arg) in `04_api_surface.en.md` returns 0 hits
- [ ] Post-fix grep `field(Field)` in `04_api_surface.en.md` §2.5 table returns ≥1 hit
- [ ] Q-PR1 5 sacred paths 0-diff vs `4c472b50` preserved at Step 4.7 HEAD
- [ ] Sacred master unchanged
- [ ] Dirty baseline 8 entries preserved
- [ ] No release.sh execution
- [ ] No src/ touch
- [ ] F8-F11 documented in §10 carry-forward (no action this slice)

## 8. Implementation Plan

1. **Step 4.2**: Self fast-pass review of this blueprint — verify §4.2 table line citations match source.
2. **Step 4.3**: Write preflight artifact `workflow/audit/active/2026-06-02_docs-vs-shipped-drift-fix-preflight.md` containing line-citation table per F1-F7 (each finding: file:line, current text, expected text, code reference).
3. **Step 4.4**: Apply preflight refinements back to blueprint if any drift found.
4. **Step 4.5**: Self final review.
5. **Step 4.6**: Scope freeze (`draft → scoped`).
6. **Step 4.6.5**: Pre-impl grep — confirm F1-F7 footprints unchanged from preflight.
7. **Step 4.7**: Single docs commit `docs(quickstart+sdk): fix 7 docs-vs-shipped drift findings (P0+P1+P2)`.
8. **Step 4.8**: Closure (`scoped → implemented`) + populate §10 Outcome + deferred carry-forward.
9. **Step 4.9**: `git mv` blueprint pair into `workflow/blueprints/archive/` + update `INVENTORY.md`.

## 9. Docs To Update

- This blueprint's audit log (`2026-06-02_docs-vs-shipped-drift-fix.audit.md`)
- `docs/official/kernel/quickstart/database.md` (F1+F2+F3 merged paragraph)
- `src/factgraph/sdk/docs/04_api_surface.en.md` (F4 + F5 + F6 + F7 across §2.5 / §2.6 / §2.12)
- `workflow/blueprints/archive/INVENTORY.md` (Step 4.9 archive row)

## 10. Outcome / Deviations

### Deferred to carry-forward (Step 4.1 declared; not addressed this slice)

| ID | Severity | Reason for deferral |
|---|---|---|
| F8 | P3 | `head=closed_head` rendering convention works for readers familiar with closed-head replay; explicit reframing has low value vs maintenance risk. |
| F9 | P3 | §2.10 / §2.11 numbering holes are cosmetic; renumbering risks breaking cross-references outside this scope. |
| F10 | P3 | `ingest` param name `items` vs `data` is positional and user-invisible; rename costs more than benefit. |
| F11 | P3 | Standalone `quickstart/package.md` requires non-trivial new content authoring; out of audit-then-fix lightweight cadence scope. |

(Step 4.7 / 4.8 / 4.9 fields populated in later cadence steps.)
