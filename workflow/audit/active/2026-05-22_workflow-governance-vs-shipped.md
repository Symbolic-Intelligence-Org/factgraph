# Audit: Workflow Governance vs Shipped Structure

- Status: skeleton (full triage filled per cadence Stage 1)
- Created: 2026-05-22
- Branch: `v0.2.0-blueprint-workflow-governance-promotion-2026-05-22` (from `12d488cc`)
- Source intent: cumulative governance proposals from the 2026-05-22 design conversation (see "Inputs" below)
- Authority: working triage document; informs but does not lock implementation. Implementation decisions follow only after Q1-Q5 closures and blueprint review.

## 1. Scope

This audit triages the gap between **proposed `workflow/` governance** (introduced in Step 0.1 as canonical structure + cadence promotion) and **shipped governance state across `docs/`, `memory/`, and Claude auto-memory**.

### Primary surface (read completely)

| Layer | Path | Role |
|---|---|---|
| Repo entry | [/AGENTS.md](/Users/zhenzhili/hnsm-backend/AGENTS.md) | 51 lines, file roles + required workflow + naming + legacy |
| Foundational | [/docs/architecture_principles.md](/Users/zhenzhili/hnsm-backend/docs/architecture_principles.md) | 79 lines, 6 stable principles + system boundaries |
| Foundational | [/docs/module_docs_convention.md](/Users/zhenzhili/hnsm-backend/docs/module_docs_convention.md) | module docs 6-item convention |
| Blueprint pillar | [/docs/blueprints/](/Users/zhenzhili/hnsm-backend/docs/blueprints/) | README (117 lines, 中文) + AGENTS (70 lines, 英文) + templates/ (4 files) + active/ (40) + archive/ (491) |
| Decision pillar | [/docs/decisions/](/Users/zhenzhili/hnsm-backend/docs/decisions/) | README (33 lines, index only) + 8 Q1-Q8 decision files (flat, no active/archive) |
| Audit pillar | [/docs/audit/](/Users/zhenzhili/hnsm-backend/docs/audit/) | 2 files on current branch (4+ in git history across other branches); no README; no governance |
| Reference pillar | [/docs/references/](/Users/zhenzhili/hnsm-backend/docs/references/) | README (80+ lines, manual index) + external/ (3) + bridges/ (2) + working/ (88+ with deep nesting) + templates/ (1) |
| Legacy archive | [/docs/blueprint_history/](/Users/zhenzhili/hnsm-backend/docs/blueprint_history/) | 24 files, marked legacy |
| Project memory | [/memory/](/Users/zhenzhili/hnsm-backend/memory/) | README + current.md (947 lines, **stale 2026-05-13**) + 4 topic checkpoints + session_handoffs/ (27 dated handoffs, latest 2026-05-13) |
| Claude auto-memory | `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/` | 79 files including MEMORY.md (32KB, **exceeds 24.4KB loader limit**), feedback_audit_to_archive_cadence.md (488 lines), 6 cadence companion files, 30+ project_*_implemented checkpoints |

### Out-of-scope (no audit action this slice)

- [/docs/SECURITY.md](/Users/zhenzhili/hnsm-backend/docs/SECURITY.md), [/docs/SECURITY_monorepo.md](/Users/zhenzhili/hnsm-backend/docs/SECURITY_monorepo.md) — security policy, stays in `docs/`
- [/docs/api/openapi.yaml](/Users/zhenzhili/hnsm-backend/docs/api/openapi.yaml) — API spec, stays in `docs/`
- [/docs/official/kernel/](/Users/zhenzhili/hnsm-backend/docs/official/kernel/) — public quickstart docs, stays in `docs/`
- [/src/factgraph/AGENTS.md](/Users/zhenzhili/hnsm-backend/src/factgraph/AGENTS.md) — module-specific, untouched
- `~/obsidian_workspace/` — external research workspace, integration deferred to future slice
- Project-root memory dormancy root cause (CLAUDE.md absence) — separate decision needed

## 2. Inputs

Sources of "design intent" for the proposed workflow:

- **Cadence source**: `feedback_audit_to_archive_cadence.md` (488 lines, auto-memory, now promoted to `workflow/CADENCE.md` @ commit `0199ab20`).
- **Existing governance**: repo `AGENTS.md` series + `docs/blueprints/README.md` (中文 9-step minimum) + `docs/blueprints/AGENTS.md` (英文 8-state machine).
- **User-proposed structure** (2026-05-22 conversation):
  - 2-pillar mental model: design + implementation + audit as anti-drift bridge.
  - 7 explicit restructure changes (docs→workflow rename scope, design-points naming, decisions ADR semantics, templates centralization, references dissolution, working/ skill convention, heritage/ for legacy).
  - 5 user review corrections: two-audit-concept naming, decisions ADR 4-state, soft-trigger flow (not forced linear chain), validator design, phased migration (stabilize first before 491-archive mv).
- **Lock-in statement** (user verbatim, now in `workflow/AGENTS.md` line 23): primary work mode for large-scope work is the cadence; tiny fixes may use lightweight exception path.

## 3. Triage Table

Following cadence Stage 1 5-state classification:

- **(a) shipped covers** — current state honors design intent
- **(b) small gap** — minor mv / rename / metadata sync
- **(c) shape conflict** — semantic or structural mismatch requires decision
- **(d) genuinely new** — no shipped equivalent
- **(e) deferred-aligned** — design defers + shipped honors

### 3.1 A-series: Architectural commitments

| # | Commitment | Shipped state | Class | Blocking Q |
|---|---|---|---|---|
| **A1** | `workflow/` exists as governance root | Does not exist | (d) | — |
| **A2** | `workflow/foundations/` holds `architecture_principles.md` + `module_docs_convention.md` | Both exist at `docs/` root | (b) | — |
| **A3** | `workflow/templates/` centralized inventory (9 templates: 4 blueprint + 2 design + 3 audit) | `docs/blueprints/templates/` has 4 files; `docs/references/templates/` has 1 file; 4 missing (decision, design-point, 3 audit sub-types) | (c) | **Q4** |
| **A4** | `workflow/design/design-points/{active,archive}/` | `docs/references/working/design-points/` exists (6 files, no active/archive split) | (b) | **Q2** |
| **A5** | `workflow/design/decisions/{active,archive}/` with ADR 4-state semantics | `docs/decisions/` has 8 files flat, no state machine, README is index-only | (c) | **Q2** |
| **A6** | `workflow/audit/{active,archive}/` with 3 sub-types (vs-shipped / preflight / synthesis) | `docs/audit/` has 2 visible files (4+ in git history), no README, no sub-type formalization | (b) | **Q3** |
| **A7** | `workflow/blueprints/` inherits `docs/blueprints/` (active + archive + AGENTS) | Full governance exists at `docs/blueprints/` | (a) — direct mv preserves state machine | — |
| **A8** | `workflow/memory/` inherits `memory/` | `memory/` exists at project root | (a) — direct mv preserves content | — |
| **A9** | `workflow/working/` gitignored temp work area + skill convention | Does not exist | (d) | — |
| **A10** | `workflow/heritage/` consolidates `blueprint_history/` + closed `references/working/` bundles | `docs/blueprint_history/` exists; CLOSED bundles in `docs/references/working/` are scattered | (b) | — |
| **A11** | `workflow/CADENCE.md` canonical (488 lines repo-ized from auto-memory) | Done in Step 0.1 @ `0199ab20` | (a) — already covers | — |
| **A12** | Per-pillar AGENTS.md (blueprints + design + audit) | Only `docs/blueprints/AGENTS.md` exists (70 lines) | (b) — design + audit AGENTS need authoring | **Q5** |
| **A13** | `workflow/AGENTS.md` umbrella with pillar map + lock-in + conflict priority | Done in Step 0.1 @ `0199ab20` | (a) — already covers | — |
| **A14** | 6 companion auto-memory rule files (preflight discipline, audit Rule 1/2, push gate, blueprint workflow, milestone refs, smaller batches) promoted to canonical | All 6 still in `~/.claude/.../memory/` | (e) — promotion deferred to later slices; pointer added in Step 0.1 | **Q5** |
| **A15** | Lock-in statement: cadence is primary for large-scope work, NOT mandatory for tiny fixes | Done in Step 0.1 @ `0199ab20` (verbatim user-provided text in `workflow/AGENTS.md` line 23) | (a) — already covers | — |
| **A16** | docs/ keeps non-workflow content (SECURITY, official, api, README) | Already correct in current `docs/` | (a) — already covers via split | **Q1** |
| **A17** | `references/external/` + `references/bridges/` migrate to `~/obsidian_workspace/` | external/ (3) + bridges/ (2) currently in `docs/references/` | (e) — deferred; integration mode unresolved | — |
| **A18** | `references/templates/` deleted (subsumed by centralized templates) | `docs/references/templates/reference_note.md` exists (1 file) | (b) — small mv + delete | **Q4** |

### 3.2 I-series: Invariants and protocols

| # | Invariant | Shipped state | Class | Blocking Q |
|---|---|---|---|---|
| **I1** | Sacred-branch isolation (`master`, `v0.1-oss-prep`) | Practiced + documented in cadence | (a) — covered via `workflow/CADENCE.md` | — |
| **I2** | Unrelated dirty file preservation | Practiced + documented in cadence | (a) | — |
| **I3** | "可以推进" mutual authorization | Practiced + documented in cadence | (a) | — |
| **I4** | Per-commit verification ritual | Practiced + documented in cadence | (a) | — |
| **I5** | Single small commits | Practiced + documented in cadence | (a) | — |
| **I6** | 9-stage audit-to-archive cadence | Documented in `workflow/CADENCE.md` (Step 0.1) | (a) | — |
| **I7** | 5-bucket preflight severity classification | Documented in cadence | (a) | — |
| **I8** | 8-state blueprint state machine | `docs/blueprints/AGENTS.md` defines this | (a) | — |
| **I9** | ADR 4-state decision semantics (proposed / adopted / superseded / withdrawn) | Not defined anywhere; current `docs/decisions/` uses informal "closed" | (d) | **Q2** |
| **I10** | 3 audit sub-types formalized (vs-shipped / preflight / synthesis) | Implicit in cadence (referenced by stage); not formally typed in any AGENTS | (b) | **Q3** |
| **I11** | Two distinct "audit" concepts disambiguated: paired blueprint audit log (`*.audit.md`) vs standalone audit record | Conflated terminology in current cadence + `docs/blueprints/AGENTS.md` | (c) | **Q3** |
| **I12** | design-point authority boundary explicit ("non-authoritative reference; becomes constraint only via decision / blueprint / module docs / architecture-principles") | `docs/references/working/design-points/readme.md` partially addresses; strengthen in new `design/AGENTS.md` | (b) | **Q2** |
| **I13** | Preflight trigger conditions formalized (when required vs optional) | Cadence assumes always for substrate slices; no formal condition list | (d) | **Q3** |
| **I14** | Template unified metadata header (7-field: Status / Created / Last Updated / Authority / Inputs / Outputs / Related) | No template currently enforces this | (d) | **Q4** |
| **I15** | Cross-pillar flow is soft-trigger (blueprint hard gate; design / audit / decisions trigger-based prerequisites) | Cadence text implies sequence but does not lock it; user review explicitly rejected linear chain framing | (c) | **Q5** |

### 3.3 D-series: Discrepancies between current and proposed structure

| # | Discrepancy | Current state | Proposed state | Class |
|---|---|---|---|---|
| **D1** | `factpy_kernel` → `factgraph` namespace migration not reflected in repo `AGENTS.md` line 14, line 27 | `src/factpy_kernel/*/docs/` referenced as "current implementation truth" | `src/factgraph/*/docs/` (actual namespace) | (b) — stale path |
| **D2** | `docs/blueprints/README.md` lists 5 blueprint states; `docs/blueprints/AGENTS.md` lists 8 | README missing blocked/abandoned/superseded | Aligned 8-state across both | (b) — README update on Phase 2 mv |
| **D3** | Templates split between 2 locations (`docs/blueprints/templates/` + `docs/references/templates/`) | 5 templates across 2 dirs, missing 4 | All 9 centralized in `workflow/templates/<pillar>/` | (c) — covered by **Q4** |
| **D4** | `memory/current.md` claims "最后更新: 2026-05-13" — stale 9 days | rc.3-era snapshot, missing slice 1-7C + post-7C docs + factgraph projection events | Either rewrite or supersede via new project memory | (e) — content cleanup deferred to memory consolidation slice |
| **D5** | `~/.claude/.../memory/MEMORY.md` (32KB) exceeds 24.4KB loader limit → tail silently truncated | Late entries may not load in new sessions | Shorten index entries (≤200 chars), move detail to topic files | (e) — deferred to memory consolidation |
| **D6** | `docs/audit/` content branch-isolated (visible files vary by branch) | Slice 7C audit + preflight only on `v0.2.0-registry-final-removal-audit-2026-05-21` branch, not on current docs branch | Audit forward-merge policy needed | (c) — covered by **Q3** preflight trigger conditions |
| **D7** | `docs/references/working/` heterogeneous (6+ content classes: pre-OSS market materials, design-points, load-test bundles, closed routemap input, namespace-test proposals, .pptx binary, .json data) | Mixed in single subdir without sub-organization | Migrate design-points to `design/`, CLOSED bundles to `heritage/bundles/`, market materials to `heritage/`, external/bridges to obsidian | (c) — case-by-case in Phase 7 |
| **D8** | `docs/references/working/rule-replay-line-redesign-input/` marked "CLOSED @ 6b32972" but still in active references | Permanent staging | Move to `workflow/heritage/bundles/` | (b) — Phase 6 |
| **D9** | `docs/references/working/post-routemap-direction-selection-input/` marked "captured by all 12 archived blueprints" but still in working | Same as D8 | Move to heritage | (b) — Phase 6 |
| **D10** | `docs/references/working/load-test-2026-04-11/` is a complete bundle (>15 files), purpose-bound, may have lasting reference value | Sits in working without status | Decision: archive or delete in Phase 7 | (e) — covered by user judgment in Phase 7 (Q6 conversational lock: keep if useful, delete if not) |
| **D11** | `project_lifecycle_assets_remaining_after_rc3.md` (memory file) lists 7 "Not Complete" items; some have since been done (Schema Mutation slices 1+2), others heavily affected (Item 3 Explain via DB/view audit) | Forward-looking todo from 2026-05-13 | Supersede via new post-Slice-7C lifecycle/assets memo (deferred content slice) | (e) — deferred to memory consolidation |
| **D12** | 491 files in `docs/blueprints/archive/` use relative links (`../../audit`, `../../decisions`, `../../references`) | All relative resolve under current `docs/` structure | mv to `workflow/blueprints/archive/` will break ~5 link patterns per file → ~2500 link updates | (c) — covered by **Phase 5 conditional** (gate via Phase 4 validator + link checker) |

### 3.4 N-series: Non-discrepancies (verified shipped honors design)

| # | Item | Verification |
|---|---|---|
| **N1** | `docs/blueprints/AGENTS.md` 8-state machine | Matches cadence preference; no change needed |
| **N2** | `docs/blueprints/README.md` 中文 9-step minimum checklist | Substantive, useful, keep verbatim on Phase 3 mv |
| **N3** | `docs/blueprints/templates/task_blueprint.md` (71 lines) + `task_blueprint.audit.md` (19 lines) + 2 legacy templates | Existing blueprints use these; no semantic change needed in mv |
| **N4** | `docs/references/working/design-points/` 6 active essays | Substantive content, mv preserves authorship; new active/archive structure does not invalidate existing |
| **N5** | Sacred branches `master @ 562c74195df...` + `v0.1-oss-prep` (last touched per release branch invariants memory) | Not touched during entire 2026-05-20/22 slice lineage |

## 4. Open Questions (block downstream blueprint)

Five load-bearing questions surface from the triage; each needs its own decision document (Stage 2). All five were extensively pre-locked through the 2026-05-22 design conversation; the decision docs codify those locks as formal artifacts.

### Q1: docs / workflow split scope

**Block**: A1, A16. Determines exactly what stays in `docs/` and what migrates to `workflow/`.

**Conversational lock**: Option (b) — split. `docs/` keeps non-workflow content (SECURITY, official, api, README); new `workflow/` takes governance (foundations, templates, design, audit, blueprints, memory, working, heritage).

### Q2: design pillar structure

**Block**: A4, A5, I9, I12.

**Conversational locks**:

- `design-points/` name preserved (not "research" or other rename).
- design-point 3-condition archive criteria.
- decisions ADR 4-state machine (proposed / adopted / superseded / withdrawn); only superseded + withdrawn → archive; adopted stays in active as current constraint.
- design-point authority boundary statement (not current truth; becomes constraint only via adoption).

### Q3: audit pillar structure

**Block**: A6, I10, I11, I13, D6.

**Conversational locks**:

- Two-concept naming: paired blueprint audit log (`*.audit.md`) vs standalone audit record (vs-shipped / preflight / synthesis).
- 3 sub-types formalized as separate templates.
- Preflight trigger conditions: high-risk migration / cross-module protocol / historical design contrast / pre-release verification (others optional).
- Cross-branch visibility convention (audit forward-merge policy).

### Q4: Template centralization + 9-template inventory + unified metadata

**Block**: A3, A18, D3, I14.

**Conversational locks**:

- All 9 templates centralized at `workflow/templates/<pillar>/`.
- Inventory: 4 blueprint (task + audit + legacy + legacy.audit) + 2 design (design-point + decision) + 3 audit (vs-shipped + preflight + synthesis).
- Unified 7-field metadata header (Status / Created / Last Updated / Authority / Inputs / Outputs/Downstream / Related).
- `docs/references/templates/` deleted after content absorbed.

### Q5: Cadence-as-primary-mode + AGENTS hierarchy + companion promotion plan

**Block**: A11, A12, A13, A14, A15, I15.

**Conversational locks**:

- CADENCE.md is canonical (already done in Step 0.1).
- Lock-in statement verbatim (already done in Step 0.1).
- 4-level AGENTS hierarchy: workflow umbrella + 3 per-pillar (blueprints inherited from docs, design + audit new).
- 6 companion auto-memory files: defer canonical promotion to later slices; promotion plan documented; auto-memory remains authoritative for Claude session behavior until promoted.
- Cross-pillar flow is soft-trigger, not forced linear chain. Blueprint is hard gate. Design / audit / decisions are trigger-based prerequisites.

## 5. Frictions

Five frictions identified through diagnostic conversation:

1. **Cadence was auto-memory-only** → addressed in Step 0.1 via `workflow/CADENCE.md` promotion.
2. **Path references in cadence stale** (referenced `docs/audit/...` etc.) → addressed in Step 0.1 via repo-ization.
3. **Templates split between 2 locations** (`docs/blueprints/templates/` + `docs/references/templates/`) → addressed by Q4 + Phase 3 mv.
4. **491 files in `docs/blueprints/archive/` use relative links** that will break if mv'd → addressed by Phase 4 validator + Phase 5 conditional mv (decide-at-time).
5. **Dormant project-root memory + active auto-memory split**, plus stale `memory/current.md` and missing 9-day session_handoffs → out of scope this slice; CLAUDE.md decision + memory content cleanup are independent follow-up workstreams.

## 6. Cross-doc seams (out of scope this slice)

- **S1-S6 + I10/A10** from prior DB/view audit — formal cross-doc seam unblock independent of this slice (already deferred per session memory).
- **`~/obsidian_workspace/` integration** — replaces `references/external/` + `references/bridges/`; integration mode (read-only / read-write / harvest cadence) unresolved; defer to dedicated slice after `workflow/` internal restructure is stable.
- **CLAUDE.md creation** — needed for project-root memory activation; defer to dedicated slice.
- **Memory content cleanup** (refresh `current.md` + 5+ new checkpoint files + 9 missing session_handoffs + `project_lifecycle_assets_remaining_after_rc3.md` fate) — defer to memory consolidation slice.
- **Auto-memory MEMORY.md size optimization** (32KB > 24.4KB loader limit) — defer to memory consolidation slice.

## 7. Recommendations for blueprint

After Q1-Q5 closure, the implementing blueprint should:

- Define an **8-phase implementation plan** with Phase 5 (491-archive mv) **conditional, gated by Phase 4 validator pass**.
- **Phase 1.5 AGENTS authoring** must precede Phase 2 low-cardinality mv to prevent agent instruction conflicts (per user review correction).
- **Phase 4 validator** (lightweight Python) must check at minimum: blueprint/audit pairing, Status enum white-listing, template path resolution, active/archive naming legality, link integrity within `workflow/`.
- Each phase must produce 1 commit unless 3-commit pattern is justified (per cadence single-small-commits rule).
- **No deviation from Q1-Q5 locked decisions** without explicit user revision request.

The blueprint should be drafted on this same branch (`v0.2.0-blueprint-workflow-governance-promotion-2026-05-22`) immediately after Q1-Q5 closure and synthesis.

## 8. Audit method notes

- All 5-state classifications above were assigned with **shipped-code-as-ground-truth** verification: every cited file path was confirmed to exist via direct file inspection during the 2026-05-22 diagnostic conversation.
- Multi-Q decision pattern (single-branch consolidation) is being applied here as documented deviation; will be carried forward in closure §10 of the implementing blueprint per the Q-delta-decision lock pattern from Slice 7C.
- The cadence promotion itself (Step 0.1 commit `0199ab20`) was made before this audit doc, which technically inverts the cadence Stage 1 → Step 4.1 sequence. Rationale: Step 0.1 was a foundational scaffold needed before any cadence artifact could land at the new canonical paths; this scaffold-first deviation is documented here and will reappear in the closure §10 deviations.

## 9. Audit completeness checklist

- [x] All 6 governance-relevant directories triaged (blueprints / decisions / audit / references / blueprint_history / memory)
- [x] All 3 governance-relevant root files triaged (AGENTS.md / architecture_principles.md / module_docs_convention.md)
- [x] Claude auto-memory state inventoried (size limit + companion file list)
- [x] All 5 user-conversation locked decisions surfaced as Q1-Q5
- [x] All identified frictions enumerated
- [x] Out-of-scope items explicitly listed
- [x] Recommendations for blueprint phase plan provided

Audit Stage 1 complete. Stage 2 Q-resolution may proceed (Q1 first per cadence load-bearing priority).
