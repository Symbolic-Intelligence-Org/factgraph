# Q1 Decision: docs / workflow split scope

- Status: proposed
- Created: 2026-05-22
- Branch: `v0.2.0-blueprint-workflow-governance-promotion-2026-05-22`
- Audit source: [workflow/audit/active/2026-05-22_workflow-governance-vs-shipped.md](../../../audit/active/2026-05-22_workflow-governance-vs-shipped.md) (§3.1 A1, A16; §3.3 D-series; §4 Q1)
- Authority: design constraint; locks the directory boundary between `docs/` and `workflow/` before any mv operation in the implementing blueprint.

> **Status note**: this decision is opened with `Status: proposed`. The ADR 4-state semantics (proposed / adopted / superseded / withdrawn) are themselves under decision in Q5. Once Q5 closes, a separate batch commit will flip Q1-Q4 from `proposed` to `adopted` to reflect formal lock. See §9 Decision Record below for the planned transition.

## 1. Inputs

- Audit §1 Scope — `docs/` is the current home for both workflow governance content (blueprints, decisions, audit, references, blueprint_history, architecture_principles, module_docs_convention) AND non-workflow content (SECURITY, api, official).
- Audit §3.1 A1 — "`workflow/` exists as governance root" classified `(d) genuinely new`.
- Audit §3.1 A16 — "`docs/` keeps non-workflow content" classified `(a) shipped covers via split`.
- Audit §3.3 D1 — `factpy_kernel` → `factgraph` namespace migration is partially stale in [/AGENTS.md](/Users/zhenzhili/hnsm-backend/AGENTS.md) (will be fixed during root-AGENTS update in the implementing blueprint).
- 2026-05-22 design conversation: user explicit lock of split-with-retention option (referred to as "Option (b)" in the conversation).
- Repo entry [/AGENTS.md](/Users/zhenzhili/hnsm-backend/AGENTS.md) lines 5-16 (document roles enumeration).

## 2. Scope

This decision locks:

- Which top-level directories receive the migrated workflow governance content (`workflow/`).
- Which directories retain the existing non-workflow content (`docs/`).
- The intent and boundary between the two.

## 3. Non-scope

- Internal structure of `workflow/` pillars (covered by Q2 design pillar, Q3 audit pillar, Q4 templates, Q5 cadence + AGENTS hierarchy).
- File-level mv ordering and phase plan (covered by the implementing blueprint §8).
- `~/obsidian_workspace/` integration replacing `references/external/` + `references/bridges/` (deferred to a future slice; explicitly out of scope this slice).
- `src/factgraph/AGENTS.md` and module-level docs under `src/factgraph/*/docs/` (untouched; remain authoritative module-level docs per existing convention).
- Project-root memory dormancy fix (deferred to a future slice; requires `CLAUDE.md` decision).

## 4. Decision

**Adopt the split-with-retention model**: introduce a new `workflow/` directory at the repository root for governance content, and **retain `docs/` for non-workflow content**.

### 4.1 `docs/` retention list (post-restructure)

The following items **stay** in `docs/`:

| Item | Reason |
|---|---|
| [docs/README.md](/Users/zhenzhili/hnsm-backend/docs/README.md) | Repository docs index; updated to point at `workflow/` for governance entries |
| [docs/SECURITY.md](/Users/zhenzhili/hnsm-backend/docs/SECURITY.md) | Local secret handling + kernel API key conventions; public-facing |
| [docs/SECURITY_monorepo.md](/Users/zhenzhili/hnsm-backend/docs/SECURITY_monorepo.md) | Security policy variant for monorepo context |
| [docs/api/openapi.yaml](/Users/zhenzhili/hnsm-backend/docs/api/openapi.yaml) | Service API spec; developer-facing technical artifact |
| [docs/official/kernel/](/Users/zhenzhili/hnsm-backend/docs/official/kernel/) | Public quickstart documentation; end-user-facing |

### 4.2 `workflow/` migration target list (post-restructure)

The following items **move into** `workflow/`:

| Source | Target | Pillar |
|---|---|---|
| `docs/architecture_principles.md` | `workflow/foundations/architecture_principles.md` | foundations |
| `docs/module_docs_convention.md` | `workflow/foundations/module_docs_convention.md` | foundations |
| `docs/blueprints/templates/*.md` | `workflow/templates/blueprints/*.md` | templates |
| `docs/blueprints/active/` + `docs/blueprints/archive/` + `docs/blueprints/README.md` + `docs/blueprints/AGENTS.md` | `workflow/blueprints/{active,archive}/` + `workflow/blueprints/README.md` + `workflow/blueprints/AGENTS.md` | blueprints |
| `docs/decisions/*.md` + `docs/decisions/README.md` | `workflow/design/decisions/active/*.md` + `workflow/design/decisions/README.md` | design/decisions |
| `docs/audit/*.md` | `workflow/audit/active/*.md` | audit |
| `docs/references/working/design-points/*.md` + nested files | `workflow/design/design-points/active/*.md` | design/design-points |
| `docs/blueprint_history/*` | `workflow/heritage/blueprint_history/*` | heritage |
| `memory/` (project-root entire tree) | `workflow/memory/` | memory |
| `docs/references/working/` CLOSED bundles (e.g., `rule-replay-line-redesign-input/`, `post-routemap-direction-selection-input/`) | `workflow/heritage/bundles/` | heritage |

### 4.3 `docs/references/` partial dissolution

`docs/references/working/` and `docs/references/templates/` are **dissolved in this slice**. `docs/references/external/` and `docs/references/bridges/` remain as **explicitly parked deferred subtrees** until the future obsidian-integration slice. The parent `docs/references/` directory therefore persists at slice end holding only those two parked subtrees plus an updated README; it is deleted only after the obsidian slice migrates the remaining content out.

| Item | Disposition this slice |
|---|---|
| `docs/references/working/design-points/` | Migrated to `workflow/design/design-points/active/` (per Q2) |
| `docs/references/working/` heterogeneous content (load-test bundle, pre-OSS market materials, .pptx, .json data, namespace-test proposals) | Case-by-case in implementing blueprint Phase 7; survivors go to `workflow/heritage/bundles/` or `workflow/working/` per user judgment |
| `docs/references/working/` parent dir | Deleted at end of Phase 7 once empty |
| `docs/references/templates/reference_note.md` | Deleted after Q4 confirms it is not needed for the centralized template inventory |
| `docs/references/templates/` parent dir | Deleted once empty |
| `docs/references/external/` | **Parked** — explicitly deferred subtree; not touched in this slice; awaits obsidian-integration slice |
| `docs/references/bridges/` | **Parked** — explicitly deferred subtree; not touched in this slice; awaits obsidian-integration slice |
| `docs/references/README.md` | Updated this slice to declare partial-dissolution state (`working/` + `templates/` gone; `external/` + `bridges/` deferred). Deleted only after the obsidian slice migrates `external/` + `bridges/` out. |
| `docs/references/` parent dir | Persists at slice end holding only `external/` + `bridges/` + updated `README.md`. Deleted only after obsidian slice. |

### 4.4 Root governance updates

- [/AGENTS.md](/Users/zhenzhili/hnsm-backend/AGENTS.md) is updated to point at `workflow/AGENTS.md` as the canonical governance entry, while retaining its role as repo-level meta-pointer.
- [docs/README.md](/Users/zhenzhili/hnsm-backend/docs/README.md) is updated to reflect that `docs/` now holds only non-workflow content and to redirect governance traffic to `workflow/`.

## 5. Rejected Alternatives

### Option (a): Full rename `docs/` → `workflow/`

- **Why rejected**: `docs/` contains `SECURITY.md`, `api/openapi.yaml`, and `official/kernel/` — none of which are governance/workflow content. Renaming the whole directory to `workflow/` would semantically misclassify them.
- Originally proposed by user 2026-05-22 conversation; user revised after I raised the scope ambiguity, locking Option (b) instead.

### Option (c): Three-way split (`workflow/` + `public/` + delete `docs/`)

- **Why rejected**: Moving `SECURITY.md` / `api/openapi.yaml` / `official/kernel/` into a new `public/` directory introduces a third top-level concept without clear benefit, and conflicts with established public/private boundary conventions used in the OSS projection scripts (`scripts/project_release_surface.sh`, `scripts/release_surface_allowlist.txt`).
- The release-surface allowlist gating already distinguishes public from internal content at projection time; no second physical split is needed.

### Option (d): Keep everything in `docs/`, add governance README pointer

- **Why rejected**: Does not solve the core diagnostic finding (cadence is dormant in auto-memory, `docs/` is shape-confused mixing 6 different content types). Mere README pointer does not provide the canonical home that lets agents and humans navigate by intent.

## 6. Supporting Evidence

- Audit §1 explicit out-of-scope list for `docs/SECURITY.md`, `docs/api/`, `docs/official/`.
- Audit §3.1 A16 classified `(a) shipped covers via split`, indicating shipped state already supports this division.
- [/AGENTS.md](/Users/zhenzhili/hnsm-backend/AGENTS.md) lines 5-16 enumerate distinct document role categories that map onto the proposed split:
  - `architecture_principles.md` → workflow/foundations
  - `references/` → workflow/heritage + design-points (per dissolution)
  - `blueprints/active/` → workflow/blueprints/active
  - `memory/` → workflow/memory
  - `blueprint_history/` → workflow/heritage/blueprint_history
- The existing `docs/blueprints/AGENTS.md` 8-state machine is preserved verbatim through direct mv (Phase 3 of implementing blueprint), validating that workflow content has a coherent governance subtree to migrate.

## 7. Consequences

### 7.1 Downstream unblocking

- A1, A16 in audit triage are formally closed by this decision.
- Q2, Q3, Q4, Q5 can proceed without scope ambiguity about which directory their decisions land in.
- The implementing blueprint §8 phase plan has a clear mv target list.

### 7.2 Required follow-up actions in the implementing blueprint

- [/AGENTS.md](/Users/zhenzhili/hnsm-backend/AGENTS.md) update (root pointer to `workflow/AGENTS.md`); this also resolves stale `factpy_kernel` references identified in audit D1.
- [docs/README.md](/Users/zhenzhili/hnsm-backend/docs/README.md) update (remove workflow entries, redirect to `workflow/`).
- [memory/README.md](/Users/zhenzhili/hnsm-backend/memory/README.md) becomes `workflow/memory/README.md` (path-only update, content unchanged in this slice).
- Validator (per implementing blueprint Phase 4) must confirm `docs/` retains exactly the 5 items listed in §4.1 and `workflow/` contains exactly the items listed in §4.2.

### 7.3 Decoupled from this decision

- `~/obsidian_workspace/` integration affecting `references/external/` + `references/bridges/` is independently decoupled — those two subdirectories remain in their current `docs/references/` location with a "deferred" marker, and will be migrated to obsidian during a future slice. The dissolution of `docs/references/` therefore completes **except** for those two subdirectories, which are intentionally left in place.

### 7.4 Persistence

This split is meant to be **permanent**. Once `workflow/` exists with full pillar tree, future governance content goes there by default; future non-workflow content (new security policies, new public docs) goes to `docs/`. No third top-level for governance is planned.

## 8. Acceptance Criteria

Post-implementing-blueprint, the repo state must satisfy:

1. `docs/` top-level contents — two-stage acceptance:
   - **End of this slice** (acceptance gate for the workflow-governance-promotion blueprint): `README.md`, `SECURITY.md`, `SECURITY_monorepo.md`, `api/`, `official/`, plus a partially-dissolved `references/` directory containing only `external/` + `bridges/` + an updated `README.md` declaring the partial-dissolution state.
   - **End of future obsidian-integration slice** (out of scope here; recorded for traceability): exactly 5 items — `README.md`, `SECURITY.md`, `SECURITY_monorepo.md`, `api/`, `official/`. `docs/references/` no longer exists.
2. `workflow/` contains all 8 pillars per `workflow/AGENTS.md` pillar map with each pillar populated per Q2-Q5 decisions.
3. [/AGENTS.md](/Users/zhenzhili/hnsm-backend/AGENTS.md) points readers at `workflow/AGENTS.md` for governance.
4. [docs/README.md](/Users/zhenzhili/hnsm-backend/docs/README.md) has no entries for `blueprints/`, `decisions/`, `audit/`, `references/working/design-points/`, `blueprint_history/`, or workflow-related architecture/module-docs documents (those entries now live in `workflow/README.md`).
5. Validator confirms 0 broken links within `workflow/` (Phase 4 gate).

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-22 | proposed | Decision drafted | Per cadence Stage 2, Q1 load-bearing priority; first of 5 Q docs for this slice |
| TBD | adopted | Status flip via Q5 closure batch | Will be applied in a single batch commit after Q5 closes the ADR semantics for the decisions pillar |

This decision will not be acted upon (no mv operations) until **all five Q decisions are closed and the implementing blueprint reaches `Status: scoped`**.
