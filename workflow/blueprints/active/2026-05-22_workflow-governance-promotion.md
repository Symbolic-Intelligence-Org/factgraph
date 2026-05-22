# Task Blueprint: Workflow Governance Promotion

- Status: draft
- Created: 2026-05-22
- Last Updated: 2026-05-22
- Authority: task constraint; governs the implementation of the `workflow/` governance restructure per the adopted Q1-Q5 decisions and the post-Q synthesis phase plan.
- Inputs:
  - [Post-Q synthesis](../../audit/active/2026-05-22_post-q-workflow-governance-synthesis.md) (commit `d83602e2` + tightenings `efe3c198`, `085d6988`, `c6646114`) — §3 recommended phase order is the source of this blueprint's §8
  - [Stage 1 audit](../../audit/active/2026-05-22_workflow-governance-vs-shipped.md) (commit `79548b0d`) — drift inventory + scope boundaries
  - Q1-Q5 adopted decisions (batch commit `ae375ce5`):
    - [Q1 decision](../../design/decisions/active/2026-05-22_q1-docs-workflow-split.md) — docs/workflow split scope
    - [Q2 decision](../../design/decisions/active/2026-05-22_q2-design-pillar-structure.md) — design pillar + ADR 4-state
    - [Q3 decision](../../design/decisions/active/2026-05-22_q3-audit-pillar-structure.md) — audit pillar + 3 sub-types + cross-branch visibility
    - [Q4 decision](../../design/decisions/active/2026-05-22_q4-template-centralization.md) — template centralization + 7-field metadata schema
    - [Q5 decision](../../design/decisions/active/2026-05-22_q5-cadence-as-primary-and-agents-hierarchy.md) — cadence-as-primary-mode + AGENTS hierarchy + companion deferral plan
  - [workflow/CADENCE.md](../../CADENCE.md) (Step 0.1 commit `0199ab20`) — canonical methodology
  - [workflow/AGENTS.md](../../AGENTS.md) (Step 0.1 commit `0199ab20`) — umbrella governance + lock-in statement
- Outputs / Downstream:
  - 8-phase implementation lineage (Phase 1.5 → Phase 8 per §8 below); Phase 5 is conditional and defaults to defer
  - Sibling [audit log](./2026-05-22_workflow-governance-promotion.audit.md)
  - Closure §10 outcome on slice completion
  - Archive to `workflow/blueprints/archive/2026-05-22_workflow-governance-promotion.md` (Step 4.9)
- Related:
  - `feedback_refactor_execution_traps.md` (auto-memory) — git-history-preserving mv guidance for Phase 2-7
  - `feedback_audit_to_archive_cadence.md` (auto-memory) — original source of `workflow/CADENCE.md`; remains as session-priming pointer per Q5 §4.1
  - Future obsidian-integration slice (handles parked `docs/references/external/` + `docs/references/bridges/` per Q1 §4.3)
  - Future memory-content-cleanup slice (handles `workflow/memory/current.md` refresh + MEMORY.md size + missing session_handoffs)
  - Future per-discipline companion-promotion slices (audit-discipline / release-discipline / blueprint-discipline) per Q5 §4.7
- Related Modules:
  - `workflow/` (newly populated; all pillars)
  - `docs/` (partial reduction: workflow content removed; non-workflow retained)
  - `memory/` (mv to `workflow/memory/`; content cleanup out of scope)
  - `/AGENTS.md` (path refresh + factpy_kernel → factgraph stale-path fix per audit §3.3 D1)
  - `docs/README.md` (workflow entries removed, redirect to `workflow/README.md`)
  - `.gitignore` (already updated in Step 0.1 for `workflow/working/`)
  - `src/factgraph/AGENTS.md` (NOT edited; cross-ref only per N-3 protective preservation)
- Audit Log: [2026-05-22_workflow-governance-promotion.audit.md](./2026-05-22_workflow-governance-promotion.audit.md)
- Branch: `v0.2.0-blueprint-workflow-governance-promotion-2026-05-22`

## 1. Problem

The repository's governance content is structurally scattered across three locations with different authority semantics and lifecycle conventions:

1. `docs/` mixes **workflow governance** (blueprints, decisions, audit, references, blueprint_history, foundational principles, module conventions) with **non-workflow content** (SECURITY policies, OpenAPI spec, public-facing kernel docs). This shape conflict produces multiple downstream pathologies:
   - `docs/decisions/` (9 files) lacks a state machine, README workflow, or template.
   - `docs/audit/` (2 visible files; 4+ in branch-isolated git history) has no README, no governance, no formalized sub-type taxonomy.
   - `docs/references/working/` is a junk-drawer (6+ heterogeneous content classes: design-points, market materials, load-test bundles, CLOSED routemap, .pptx + .json artifacts).
   - Templates are split between `docs/blueprints/templates/` (4 files) and `docs/references/templates/` (1 file), with 4 missing templates (decision, design-point, 3 audit sub-types).
   - `docs/blueprints/README.md` lists 5 states; `docs/blueprints/AGENTS.md` lists 8 — internal inconsistency.

2. Project-root `memory/` (8 files + 27 session_handoffs) is **dormant**: declared canonical by its own README + by `/AGENTS.md`, but in practice Claude sessions consult auto-memory (`~/.claude/.../memory/`) instead. The dormancy diagnostic surfaced during the 2026-05-22 design conversation that triggered this slice.

3. Claude auto-memory (`~/.claude/.../memory/`) holds the **load-bearing cadence** (`feedback_audit_to_archive_cadence.md`, 488 lines, validated end-to-end across 2026-05-20/22's 9-slice DB/view audit lineage) plus 6 companion rules. None of this is team-visible or git-tracked; future Claude sessions cannot rely on its persistence; human collaborators cannot read it.

The 2026-05-22 design conversation also surfaced the user's stated preference: **the cadence is the work mode we want preserved long-term**. Step 0.1 (`0199ab20`) introduced `workflow/` as canonical governance and promoted the cadence to `workflow/CADENCE.md`. This blueprint completes the structural restructure so the entire workflow operates from the new canonical tree.

## 2. Goals

- **G1**: Land the `workflow/` 8-pillar tree per Q1 §4.2, Q5 §4.3 with content from `docs/` + project-root `memory/` migrated in (no content rewrites; mv-only this slice).
- **G2**: Author 3 per-pillar AGENTS files (`design/AGENTS.md`, `audit/AGENTS.md`, `blueprints/AGENTS.md` extension on Phase 3 mv) per Q2 / Q3 / Q5 specifications.
- **G3**: Centralize all 9 templates at `workflow/templates/<pillar>/` per Q4 §4.1-4.2: 4 existing blueprint templates mv'd (Phase 3) + 5 new templates authored (Phase 1.5).
- **G4**: Establish the unified 7-field metadata header (Q4 §4.3) as enforced contract for new and active workflow content, with stratified validator coverage per Q4 §7.2.
- **G5**: Update root-level `/AGENTS.md` + `docs/README.md` (Phase 8) to reflect the split scope and resolve the audit §3.3 D1 stale `factpy_kernel` reference.
- **G6**: Partially dissolve `docs/references/` per Q1 §4.3: dissolve `working/` (mv design-points + case-by-case for others) + `templates/` (delete); leave `external/` + `bridges/` parked for the future obsidian-integration slice.
- **G7**: Consolidate legacy archive: mv `docs/blueprint_history/` + CLOSED `references/working/` bundles into `workflow/heritage/`.

## 3. Non-goals

- **NG1**: Content cleanup of `workflow/memory/*` post-mv (current.md refresh / MEMORY.md size optimization / 9 missing session_handoffs backfill / project_lifecycle_assets_remaining_after_rc3.md fate). Phase 3.5 is **mv-only**. Memory content cleanup is a separate future slice.
- **NG2**: CLAUDE.md creation for project-root memory activation. Separate future slice.
- **NG3**: Obsidian-workspace integration replacing `docs/references/external/` + `docs/references/bridges/`. Separate future slice; both subtrees remain **parked** at their current paths until then per Q1 §4.3.
- **NG4**: 6 companion auto-memory files canonical promotion. Deferred to future per-discipline slices per Q5 §4.7.
- **NG5**: Cross-doc S1-S6 + I10/A10 from the prior 2026-05-20 DB/view audit. Out of scope per audit §6.
- **NG6**: Retroactive 7-field schema retrofit on 491 archived blueprints in `docs/blueprints/archive/`. Per Q4 §7.4 they are exempt or warning-only.
- **NG7**: Skill convention authoring for `workflow/working/`. Per audit §3.1 A9 the gitignored slot exists; specific skill packaging is out of scope.
- **NG8**: Unconditional 491-archive mv (Phase 5). Default: **defer pending Phase 4 validator outcome** per synthesis §2.5.

## 4. Current Context

### 4.1 Q lock table

| Q | Status | Adopted in | Locks |
|---|---|---|---|
| Q1 | adopted | `ae375ce5` (2026-05-22) | docs/workflow split + workflow's 8-pillar layout + references partial dissolution |
| Q2 | adopted | `ae375ce5` (2026-05-22) | design pillar structure + design-points 3-condition archive + ADR 4-state + design-point authority boundary |
| Q3 | adopted | `ae375ce5` (2026-05-22) | audit pillar structure + 3 sub-types + paired-vs-standalone naming + preflight trigger conditions + cross-branch visibility |
| Q4 | adopted | `ae375ce5` (2026-05-22) | template centralization + 9-template inventory + 7-field metadata schema + per-pillar pointer rule |
| Q5 | adopted | `ae375ce5` (2026-05-22) | cadence-as-primary lock-in + 2-level 4-file AGENTS hierarchy + companion deferral plan + soft-trigger cross-pillar flow |

### 4.2 Step 0.1 + 0.2 + 0.3 progress carried forward

- `workflow/` skeleton (24 directories) exists (`0199ab20`).
- `workflow/CADENCE.md` (517 lines, canonical) exists (`0199ab20`).
- `workflow/AGENTS.md` (93 lines, umbrella + lock-in) exists (`0199ab20`).
- 5 Q decisions adopted in batch flip with Q1-Q4 retrofitted to 7-field schema (`ae375ce5` + `4f705f6e` post-adoption tightening).
- Stage 1 audit + post-Q synthesis exist as standalone audit records in `workflow/audit/active/`.

### 4.3 Pre-existing constraints

- Sacred branches `master @ 562c74195df...` and `v0.1-oss-prep` are not touched.
- Unrelated dirty file set (`docs/references/working/design-points/readme.md`, `examples/01_sdk_check_diagnose.ipynb`, `examples/02_overlay_why_not_frontier.ipynb`, `examples/archive/01_sdk_basics.ipynb`, plus untracked `rainbird-ai sdk code/`) is preserved throughout the slice.
- This slice operates on the blueprint branch `v0.2.0-blueprint-workflow-governance-promotion-2026-05-22` (current).
- Step 4.3 preflight will be opened on a separate branch `v0.2.0-workflow-governance-promotion-preflight-2026-05-22` per CADENCE Step 4.3 + Q3 §4.4 trigger conditions (this slice qualifies as namespace migration + high-risk migration).
- Step 4.7 implementation will fork from the scoped anchor onto `v0.2.0-impl-workflow-governance-promotion-2026-05-22`.

## 5. Proposed Shape

Post-implementation tree (target state):

```
~/hnsm-backend/
├── docs/                                       (reduced, non-workflow only)
│   ├── README.md                                (updated: workflow entries removed; redirect to workflow/README.md)
│   ├── SECURITY.md / SECURITY_monorepo.md       (untouched)
│   ├── api/openapi.yaml                         (untouched)
│   ├── official/kernel/                         (untouched; public docs)
│   └── references/                              (partially dissolved per Q1 §4.3)
│       ├── external/                            (PARKED for future obsidian slice)
│       ├── bridges/                             (PARKED for future obsidian slice)
│       └── README.md                            (updated: declares partial-dissolution state)
│
└── workflow/                                    (canonical governance)
    ├── README.md / AGENTS.md / CADENCE.md       (Step 0.1 done; final tightenings during Phase 1.5/3 as needed)
    ├── foundations/
    │   ├── architecture_principles.md            (Phase 2 mv from docs/)
    │   └── module_docs_convention.md             (Phase 2 mv from docs/)
    ├── templates/
    │   ├── README.md                             (Phase 1.5 author per Q4)
    │   ├── blueprints/                           (Phase 3 mv from docs/blueprints/templates/)
    │   │   ├── task_blueprint.md
    │   │   ├── task_blueprint.audit.md
    │   │   ├── legacy_reconstructed_archive.md
    │   │   └── legacy_reconstructed_archive.audit.md
    │   ├── design/                               (Phase 1.5 author)
    │   │   ├── design-point.md
    │   │   └── decision.md
    │   └── audit/                                (Phase 1.5 author)
    │       ├── vs-shipped.md
    │       ├── preflight.md
    │       └── synthesis.md
    ├── design/
    │   ├── README.md / AGENTS.md                 (Phase 1.5 author per Q2 + Q5 + Q4 pointer)
    │   ├── design-points/{active,archive}/        (Phase 2 mv from docs/references/working/design-points/; existing essays land in active/)
    │   └── decisions/
    │       ├── active/                          (Phase 2 mv from docs/decisions/ + this slice's Q1-Q5 already here)
    │       └── archive/
    ├── audit/
    │   ├── README.md / AGENTS.md                 (Phase 1.5 author per Q3 + Q5 + Q4 pointer)
    │   ├── active/                              (Phase 2 mv from docs/audit/ + this slice's audit + synthesis already here)
    │   └── archive/
    ├── blueprints/
    │   ├── README.md (Phase 3 mv + 5-state vs 8-state alignment per audit D2)
    │   ├── AGENTS.md (Phase 3 mv + Q4 §4.4 templates pointer + Q3 §4.2 paired-vs-standalone cross-ref)
    │   ├── templates/  → REMOVED (mv'd to workflow/templates/blueprints/)
    │   ├── active/                              (Phase 5 conditional mv from docs/blueprints/active/, default defer)
    │   └── archive/                             (Phase 5 conditional mv from docs/blueprints/archive/, default defer)
    ├── memory/                                   (Phase 3.5 mv from /memory/; content cleanup deferred per NG1)
    │   ├── README.md
    │   ├── current.md
    │   ├── session_handoffs/
    │   └── *.md (project_*_implemented checkpoints)
    ├── working/                                  (Step 0.1 created `.gitkeep` only; gitignored contents; skill convention deferred per NG7)
    │   └── README.md (Phase 1.5 light author; tracked via .gitignore allowlist exception added in Step 0.1)
    └── heritage/
        ├── README.md                             (Phase 6 author light)
        ├── blueprint_history/                    (Phase 6 mv from docs/blueprint_history/)
        └── bundles/                              (Phase 6 mv from docs/references/working/ CLOSED bundles)
```

## 6. Boundaries And Invariants

### 6.1 N-3 protective preservation locks

Following the Slice 7C N-3 pattern, the following symbols/paths are **explicitly preserved unchanged** despite name similarity or proximity to migration targets:

| Preserved item | Why locked |
|---|---|
| `docs/SECURITY.md`, `docs/SECURITY_monorepo.md` | Security policy; non-workflow per Q1 §4.1 retention list |
| `docs/api/openapi.yaml` | Technical API spec; non-workflow per Q1 §4.1 |
| `docs/official/kernel/` (entire subtree) | Public quickstart docs; non-workflow per Q1 §4.1 |
| `docs/references/external/`, `docs/references/bridges/` | Parked subtrees per Q1 §4.3; await obsidian slice |
| `src/factgraph/AGENTS.md` and `src/factgraph/*/docs/` | Module-level governance; cross-ref only |
| `master @ 562c74195df...`, `v0.1-oss-prep` | Sacred branches per CADENCE |
| 491 archived blueprints in `docs/blueprints/archive/` (if Phase 5 mv'd) | Exempt from 7-field retrofit per Q4 §7.4 |
| 6 companion auto-memory files | Canonical promotion deferred per Q5 §4.7 |
| Unrelated dirty file set (5 items at session start) | Preserved throughout per CADENCE |

Post-impl verification will confirm zero diff on these targets.

### 6.2 Scope discipline (cross-Q lock honoring)

- Q1 §4 split-with-retention: `docs/` retains exactly the §4.1 list at slice end (plus parked `references/external/` + `references/bridges/`); no other content stays in `docs/`.
- Q2 §4.5 + §4.6 ADR semantics: only `superseded` / `withdrawn` decisions go to `archive/`; `adopted` decisions stay in `active/` as current constraints.
- Q3 §4.4 preflight required (this slice = namespace migration + high-risk migration + cross-module).
- Q4 §4.3 unified 7-field schema verbatim for all new/active workflow content; pillar-specific extensions allowed only beyond the 7-field floor.
- Q5 §4.3 4-file AGENTS hierarchy: no AGENTS in foundations / templates / memory / working / heritage.
- Q5 §4.5 soft-trigger flow: blueprint is the hard gate; not all phases need separate audit / decision artifacts.

### 6.3 Per-phase commit discipline

- Each phase = 1 commit by default. Phase 2 (large mv) + Phase 5 (491-archive if done) + Phase 6 (heritage mv) may use the 3-commit pattern (feat main + fix P1 + docs cleanup) if Step 4.7 review surfaces P1 findings.
- `git mv` (not delete+add) for all file moves to preserve git history per `feedback_refactor_execution_traps.md`.
- Each commit must pass per-commit verification ritual (branch + sacred + dirty + stage-specific check) per CADENCE.

### 6.4 Compatibility window

- `/AGENTS.md` continues to work post-restructure but with refreshed pointers to `workflow/` paths (Phase 8).
- `docs/blueprints/...` paths remain valid until Phase 5 mv decision; if Phase 5 deferred, old paths continue indefinitely (compat-soft).
- `workflow/CADENCE.md` provenance line continues to point at the auto-memory source file regardless of whether that file is later deleted from auto-memory.

## 7. Acceptance

- [ ] All 22 blueprint-eligible audit items from synthesis §2.1 are **addressed or explicitly deferred with rationale** (verified by hand-check during closure). Items deferred (e.g., to a follow-up archive-mv slice or to a memory-content-cleanup slice) must each have a §10 deviation entry recording the deferral reason.
- [ ] Phase 5 (491-archive mv) outcome explicitly recorded in §10 — one of: **defer** (default, with rationale tied to Phase 4 validator outcome) / **done in-slice** (with archive-mv commit hashes) / **split into a dedicated follow-up archive-mv slice**.
- [ ] All 9 sub-acceptance criteria from Q1 §8, Q2 §8, Q3 §8, Q4 §8, Q5 §8 are individually satisfied (validator + reviewer practice).
- [ ] `workflow/` 8-pillar tree fully populated per §5.
- [ ] 3 per-pillar AGENTS files exist (blueprints + design + audit); no AGENTS in foundations / templates / memory / working / heritage per Q5 §4.3.
- [ ] All 9 templates exist in `workflow/templates/<pillar>/` per Q4 §4.2.
- [ ] All new/active workflow files include the 7-field metadata header verbatim per Q4 §4.3.
- [ ] Phase 4 validator passes (stratified per Q4 §7.2):
  - error-level on active subdirs; warning on legacy archived blueprints; per-pillar AGENTS templates pointer present.
- [ ] `/AGENTS.md` and `docs/README.md` updated to point at `workflow/` (Phase 8); stale `factpy_kernel` reference in `/AGENTS.md` resolved.
- [ ] Module docs (none in this slice's scope) — N/A.
- [ ] `docs/README.md` updated to remove workflow entries (Phase 8).
- [ ] Sacred branches unchanged at slice end.
- [ ] Unrelated dirty file set preserved at slice end.
- [ ] Phase 5 outcome decision recorded in §10 (defer / done in-slice / split into follow-up slice).

## 8. Implementation Plan

Phases derived from synthesis §3. Phase 1 is already done (Step 0.1); Phase 1.5 onwards is in this blueprint's implementation scope.

### Phase 1.5 — AGENTS authoring + 5 new templates + templates/README.md

1. Write `workflow/templates/README.md` codifying Q4 §4.3 schema, §4.4 per-pillar pointer rule, §4.5 customization policy.
2. Author `workflow/templates/design/design-point.md` per Q2 §4.4 authority header + Q4 §4.3 7-field header.
3. Author `workflow/templates/design/decision.md` per Q2 §4.5 ADR 4-state + Q4 §4.3 7-field header.
4. Author `workflow/templates/audit/vs-shipped.md` per Q3 §4.3 + §4.8 + Q4 §4.3 7-field header.
5. Author `workflow/templates/audit/preflight.md` per Q3 §4.3 + §4.4 trigger conditions + §4.8 + Q4 §4.3 7-field header.
6. Author `workflow/templates/audit/synthesis.md` per Q3 §4.3 + §4.5 trigger conditions + §4.8 + Q4 §4.3 7-field header.
7. Author `workflow/design/AGENTS.md` codifying Q2 §4.3-4.7 + Q4 §4.4 template pointer block.
8. Author `workflow/audit/AGENTS.md` codifying Q3 §4.2-4.8 + Q4 §4.4 template pointer block + explicit paired-vs-standalone cross-reference to `workflow/blueprints/AGENTS.md`.
9. Author `workflow/design/README.md` + `workflow/design/design-points/README.md` + `workflow/design/decisions/README.md` + `workflow/audit/README.md` + `workflow/foundations/README.md` + `workflow/heritage/README.md` + `workflow/working/README.md` (light; defer to AGENTS for state machines). Note: `workflow/working/README.md` is tracked via the `.gitignore` allowlist exception added in Step 0.1.

Recommended commit batching: 1 commit for templates (steps 1-6) + 1 commit for AGENTS files (steps 7-8) + 1 commit for pillar READMEs (step 9). 3 commits.

### Phase 2 — Low-cardinality mv

1. `git mv docs/architecture_principles.md workflow/foundations/architecture_principles.md`
2. `git mv docs/module_docs_convention.md workflow/foundations/module_docs_convention.md`
3. `git mv docs/decisions/*.md workflow/design/decisions/active/` (8 existing DB/view decisions; assign `Status: adopted` per Q4 §7.3; optional 7-field retrofit per §7.4 — recommended)
4. Delete `docs/decisions/README.md` (superseded by Phase 1.5 step 9's freshly-authored `workflow/design/decisions/README.md`). Any substantive content not yet captured in Q5 / `design/AGENTS.md` / `design/decisions/README.md` must be absorbed into the Phase 1.5 fresh README before deletion. Do **NOT** `git mv` the legacy README into the pillar — that would create a dual-README at the pillar level (the Phase 1.5 fresh one + the legacy one) and reintroduce the dual-source-of-truth ambiguity PF-Rec1 flagged.
5. `git mv docs/audit/*.md workflow/audit/active/` (2 existing audits; backfill 7-field header per Q4 §7.4 warning-level)
6. `git mv` each of the **12 essay `.md` files** in `docs/references/working/design-points/` into `workflow/design/design-points/active/`. Per PF-R1 (preflight `c43ab22b`), the actual count is 12 essays + 1 readme (not "6 essays" as the pre-amendment draft claimed). Concrete essay list to mv: `database-view-fg-layered-architecture.zh.md`, `evidence-tree-rainbird-style-v1.zh.md`, `factgraph-lifecycle-and-assets.zh.md`, `identity-primary-key-coordinate-semantics.md`, `identity-primary-key-coordinate-semantics.zh.md`, `possibility-probability-transmission.zh.md`, `post-track3-semantics-public-api.zh.md`, `query-view-and-inference-handles.zh.md`, `read-write-snapshot-assertion-selection.zh.md`, `rule-expression-and-proof-attempt.zh.md`, `rule-policy-function-tree-and-syntax.zh.md`, `rule-query-inference-head-semantics.zh.md`. The legacy `docs/references/working/design-points/readme.md` (lowercase, pillar-level) is **NOT mv'd as the new pillar README** — its content is absorbed into the Phase 1.5 fresh `workflow/design/design-points/README.md` (uppercase) and the legacy lowercase file is then deleted in this Phase or in Phase 7 cleanup. Per PF-Rec1, this avoids creating a dual-README at the pillar level.

Update internal cross-links broken by mv (relative path adjustments).

Recommended commit batching: 1 commit per logical group (foundations + decisions + audit + design-points = 4 commits) OR a single batch commit if links integrity is verifiable. Default: 2-3 commits using 3-commit pattern.

### Phase 3 — Blueprint templates mv + AGENTS extension

1. `git mv docs/blueprints/templates/* workflow/templates/blueprints/` (4 template files)
2. `git mv docs/blueprints/AGENTS.md workflow/blueprints/AGENTS.md`
3. Extend `workflow/blueprints/AGENTS.md` with Q4 §4.4 template pointer section + Q3 §4.2 paired-vs-standalone cross-reference.
4. `git mv docs/blueprints/README.md workflow/blueprints/README.md` (then resolve audit §3.3 D2 5-state vs 8-state inconsistency by aligning README to AGENTS 8-state per D2)

NOTE: Phase 3 does NOT mv `docs/blueprints/active/` or `docs/blueprints/archive/` directories themselves; that decision is Phase 5.

Recommended commit batching: 1 commit (small surgical changes).

### Phase 3.5 — `memory/` mv

1. `git mv memory/* workflow/memory/` (8 files + 27 session_handoffs/)
2. Update `workflow/memory/README.md` paths (it currently references `/memory/...` absolute paths via Markdown link; should keep relative paths or update absolute paths to `/workflow/memory/...`).
3. Update any `/AGENTS.md` or `docs/README.md` reference to `memory/` (will be done in Phase 8 root governance update).

Recommended commit batching: 1 commit.

### Phase 4 — Validator + link check

1. Write `scripts/validate_workflow.py` (or `.sh`) implementing the Q4 §7.2 stratified rules:
   - error-level: 7-field header presence in active subdirs across all pillars
   - error-level: pillar AGENTS templates pointer present
   - warning-level: archive content header check (per pillar policy in Q4 §7.2)
   - warning-level: file naming conventions (`YYYY-MM-DD_*.md`)
   - warning-level: link integrity (broken relative refs in `workflow/`)
2. Run validator; collect findings.
3. Fix any active-content errors immediately (separate commit per 3-commit pattern if material).
4. Record warning counts in §10 Outcome for slice-completion narrative.
5. **Decision gate**: if validator passes 0 errors across `workflow/active/*` subdirs, Phase 5 is unblocked. Otherwise, Phase 5 must be deferred.

Recommended commit batching: 1 commit for validator script + 1 commit per material fix if any. Default: 1-2 commits.

### Phase 5 — (CONDITIONAL) 491-archive mv

**Default: DEFER.** Decision gate from Phase 4. If proceeding:

⚠️ **Important**: `workflow/blueprints/active/` and `workflow/blueprints/archive/` **already exist** at Phase 5 entry (the current blueprint pair lives in `active/`, and `archive/` was scaffold-created in Step 0.1 with `.gitkeep`). Do **NOT** `git mv` the source directories whole — the target directories are not empty. Instead, mv contents/pairs into the existing target directories:

1. For each blueprint pair `<basename>.md` + `<basename>.audit.md` in `docs/blueprints/active/` (40 pairs), execute paired `git mv` into `workflow/blueprints/active/`. Tool: shell loop or script-driven; preserves git history per `feedback_refactor_execution_traps.md`.
2. For each file in `docs/blueprints/archive/` (491 files), `git mv` into `workflow/blueprints/archive/`. Same per-file/per-pair pattern.
3. Remove the source `.gitkeep` from `workflow/blueprints/archive/` once real content lands (or remove the target `.gitkeep` early if cleaner; the .gitkeep was placeholder only).
4. Bulk relative-link rewrites (estimated ~2500 link updates across 491 archived files) — script-driven; warning-only on stale historical refs per Q4 §7.4.
5. Re-run Phase 4 validator on full corpus (must remain 0 errors on active; warnings on archive acceptable).
6. Empty `docs/blueprints/active/` and `docs/blueprints/archive/` once all content has moved; remove the empty source directories.
7. Record archive-mv commit hashes in §10.

If deferred:
- `docs/blueprints/active/` + `docs/blueprints/archive/` continue at current paths.
- A future dedicated slice can do the archive mv with its own preflight + validator.

Recommended commit batching: 1-3 commits depending on link rewriting tooling.

### Phase 6 — Heritage mv

1. `git mv docs/blueprint_history/ workflow/heritage/blueprint_history/`
2. `git mv docs/references/working/rule-replay-line-redesign-input/ workflow/heritage/bundles/rule-replay-line-redesign-input/` (per audit §3.3 D8 "CLOSED @ 6b32972")
3. `git mv docs/references/working/post-routemap-direction-selection-input/ workflow/heritage/bundles/post-routemap-direction-selection-input/` (per audit §3.3 D9 "captured by all 12 archived blueprints")
4. Write `workflow/heritage/README.md` (light) introducing the legacy archive area.

Recommended commit batching: 1 commit.

### Phase 7 — `docs/references/working/` case-by-case + `docs/references/templates/` delete

For each remaining `docs/references/working/` content:
- **`cross-domain-compliance-framing.md`** (pre-OSS market material): user judgment — mv to `workflow/heritage/bundles/` or delete.
- **`esa-positioning.md`** (market material): same as above.
- **`product-readiness-audit-2026-04-09.md`** (expired audit): mv to `workflow/heritage/bundles/` or delete.
- **`extraction_benchmark_report.json`** (data file): mv to `workflow/heritage/bundles/` or delete.
- **`factpy_esa_demo.pptx`** (binary): mv to `workflow/heritage/bundles/` or delete.
- **`factgraph-namespace-test-proposals/`** (subdir, status unknown at preflight time): **before classification**, perform reconnaissance read at Step 4.7 Phase 7 time — `ls -la` the subdir + read any `README.md` it contains — to determine status. Per PF-Rec2 (preflight `c43ab22b`). Classification rules: CLOSED bundle → `workflow/heritage/bundles/`; in-flight active test proposals → `workflow/working/` or keep separate; clearly unused → delete. Default fallback if reconnaissance is inconclusive: mv to `workflow/heritage/bundles/` and preserve. Avoids blind AskUserQuestion at Phase 7 implementation time.
- **`load-test-2026-04-11/`** (load test bundle): mv to `workflow/heritage/bundles/` or delete.

Then:
- `rm docs/references/templates/reference_note.md`
- `rmdir docs/references/templates/` if empty
- `rmdir docs/references/working/` once all content migrated
- Update `docs/references/README.md` to declare the partial-dissolution state (per Q1 §4.3)

Recommended commit batching: 1-2 commits (1 for case-by-case mv + 1 for deletions + README update). Use AskUserQuestion per file if classification is ambiguous (especially `load-test-2026-04-11/` and `factgraph-namespace-test-proposals/`).

### Phase 8 — Root governance update

1. Update `/AGENTS.md`:
   - Replace `src/factpy_kernel/` references with `src/factgraph/` (closes audit §3.3 D1)
   - Add pointer to `workflow/AGENTS.md` as canonical workflow governance entry
   - Adjust file role descriptions to reflect `docs/` retention list + `workflow/` pillars
2. Update `docs/README.md`:
   - Remove entries for blueprints/, decisions/, audit/, references/working/design-points/, blueprint_history/, architecture_principles, module_docs_convention
   - Add redirect to `workflow/README.md` for governance content
   - Keep entries for the retained items (SECURITY, official, api)
3. Final pass: grep cross-tree for any remaining stale references to `docs/blueprints/templates/`, `docs/audit/`, `docs/decisions/`, `memory/` — update or warn.

Recommended commit batching: 1 commit.

### Phase total

- Phase 1.5: 3 commits
- Phase 2: 2-3 commits
- Phase 3: 1 commit
- Phase 3.5: 1 commit
- Phase 4: 1-2 commits
- Phase 5: 1-3 commits (if done) or 0 (if deferred)
- Phase 6: 1 commit
- Phase 7: 1-2 commits
- Phase 8: 1 commit

**Total estimate**: 12-17 commits across Phase 1.5 → 8 implementation, plus this blueprint's draft / preflight / amendment / scoped / pre-impl-grep / closure / archive commits (~6 more).

**Grand total estimate**: ~18-23 commits added on the impl branch + the blueprint branch combined, atop the existing 18 from Step 0.1 / 0.2 / 0.3.

## 9. Docs To Update

Module docs (none in this slice's scope; modular code is untouched).

Repository docs to update:

- `/AGENTS.md` — Phase 8 (refresh pointers + factpy_kernel → factgraph)
- `docs/README.md` — Phase 8 (workflow entries removed + redirect)
- `docs/references/README.md` — Phase 7 (declare partial-dissolution state)
- `workflow/README.md` — final pass at slice completion (verify pillar table aligned with landed state)
- `workflow/blueprints/README.md` — Phase 3 (Phase 3 mv + D2 5-state vs 8-state alignment)
- `workflow/audit/README.md` — Phase 1.5 (author)
- `workflow/design/README.md` — Phase 1.5 (author)
- `workflow/design/design-points/README.md` — Phase 1.5 (author per Q2 §4.4 authority strengthening)
- `workflow/design/decisions/README.md` — Phase 1.5 (author per Q2 §4.5 ADR semantics) or absorb from Phase 2 mv of `docs/decisions/README.md`
- `workflow/heritage/README.md` — Phase 6 (light author)
- `workflow/templates/README.md` — Phase 1.5 (author per Q4)
- `workflow/working/README.md` — Phase 1.5 (light author; Step 0.1 created only `.gitkeep`; the README is permitted by the `.gitignore` allowlist exception already added in Step 0.1)
- `workflow/memory/README.md` — Phase 3.5 (path-only update; content cleanup deferred)

Auto-memory:

- `~/.claude/.../memory/MEMORY.md` — add a pointer entry for `workflow/CADENCE.md` and the workflow-governance-promotion slice (out of immediate scope; can be done at slice closure as a separate memory consolidation note rather than in-impl).

## 10. Outcome / Deviations

(To be filled at Step 4.8 closure)

Empty until closure. The closure will record:

- Final landed structure
- Per-phase commits + line counts
- Per-Q acceptance gate outcomes
- Phase 5 outcome decision (defer / done / split into follow-up slice)
- Per-PF preflight findings alignment
- Carry-forward items (e.g., synthesis self-narrative commit-count drift per A-option authorization)
- Acknowledged unrelated baseline conditions
- Any deviations from Q1-Q5 locked decisions (none expected; would require explicit revision)
- Archive intent (move to `workflow/blueprints/archive/` on Step 4.9)
