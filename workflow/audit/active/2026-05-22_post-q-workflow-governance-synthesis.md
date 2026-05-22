# Synthesis: Workflow Governance Post-Q Bucketing

- Status: complete
- Created: 2026-05-22
- Last Updated: 2026-05-22
- Authority: working triage document; informs but does not lock implementation. Final scope decisions live in the implementing blueprint per CADENCE Stage 3.
- Inputs:
  - [workflow/audit/active/2026-05-22_workflow-governance-vs-shipped.md](./2026-05-22_workflow-governance-vs-shipped.md) (§3.3 D-series, §6 cross-doc seams, §7 recommendations)
  - [Q1 decision](../../design/decisions/active/2026-05-22_q1-docs-workflow-split.md) (adopted)
  - [Q2 decision](../../design/decisions/active/2026-05-22_q2-design-pillar-structure.md) (adopted)
  - [Q3 decision](../../design/decisions/active/2026-05-22_q3-audit-pillar-structure.md) (adopted)
  - [Q4 decision](../../design/decisions/active/2026-05-22_q4-template-centralization.md) (adopted)
  - [Q5 decision](../../design/decisions/active/2026-05-22_q5-cadence-as-primary-and-agents-hierarchy.md) (adopted)
  - Step 0.1 commit `0199ab20` — `workflow/` skeleton + `CADENCE.md` + `AGENTS.md` (already in place)
  - Q1-Q5 batch flip commit `ae375ce5` (2026-05-22) — Status flips + Q1-Q4 7-field retrofit
- Outputs / Downstream:
  - Implementing blueprint at `workflow/blueprints/active/2026-05-22_workflow-governance-promotion.md` (Step 0.4; §4 lock table cites Q1-Q5; §8 phase plan derives from §3 recommended phase order below)
- Related:
  - [workflow/CADENCE.md](../../CADENCE.md) §Stage 3 — defines this synthesis sub-type
  - [Q3 §4.3 + §4.5](../../design/decisions/active/2026-05-22_q3-audit-pillar-structure.md) — synthesis sub-type definition and trigger conditions; this slice qualifies as required-synthesis per Q3 §4.5 (5 Q closures + ≥2 buckets)
- Source audit: [workflow/audit/active/2026-05-22_workflow-governance-vs-shipped.md](./2026-05-22_workflow-governance-vs-shipped.md)
- Closed Q decisions: Q1, Q2, Q3, Q4, Q5 (all adopted in batch commit `ae375ce5`)
- Branch: `v0.2.0-blueprint-workflow-governance-promotion-2026-05-22`

## 1. Scope of synthesis

This synthesis re-buckets the audit's drift inventory (§3.3 D-series), out-of-scope items (§6 cross-doc seams), and recommendations (§7) into the canonical 5-bucket classification defined by CADENCE Stage 3, now that Q1-Q5 are all `adopted`:

- **blueprint-eligible** — gated only by closed Qs; ready for implementing blueprint §8 phase plan.
- **cross-doc blocked** — requires sibling-doc redraft or independent slice; Q closure necessary but not sufficient.
- **no independent action** — projection / release-gate / conditional row; folds into parent blueprint rather than getting its own.
- **already aligned** — shipped state (post Step 0.1 + Step 0.2 batch) already honors design intent.
- **deferred / v2+** — design defers + shipped does not implement; no action this slice.

This synthesis is **not implementation authorization**. It only determines bucket eligibility. The implementing blueprint (Step 0.4) decides phase batching and scope-freeze.

## 2. 5-bucket classification

### 2.1 blueprint-eligible

Drift rows that are gated only by Q1-Q5 (now adopted) and are ready to be addressed by the implementing blueprint:

| Audit row | Topic | Implementing blueprint phase |
|---|---|---|
| §3.3 D1 | `factpy_kernel` → `factgraph` stale path in `/AGENTS.md` lines 14, 27 | Phase 8 (root governance update) |
| §3.3 D2 | `docs/blueprints/README.md` 5-state vs `AGENTS.md` 8-state inconsistency | Phase 3 (blueprints mv) + README extension on mv |
| §3.3 D3 | Templates split between `docs/blueprints/templates/` + `docs/references/templates/` | Phase 3 (templates mv to `workflow/templates/blueprints/`) + Phase 1.5 (author 5 new templates) |
| §3.3 D7 | `docs/references/working/` heterogeneous content | Phase 6 (design-points mv) + Phase 7 (case-by-case for non-design-point items) |
| §3.3 D8 | `rule-replay-line-redesign-input/` CLOSED bundle still in `working/` | Phase 6 (mv to `workflow/heritage/bundles/`) |
| §3.3 D9 | `post-routemap-direction-selection-input/` captured but still in `working/` | Phase 6 (mv to heritage) |
| §3.3 D10 | `load-test-2026-04-11/` purpose-bound bundle | Phase 7 (user judgment: heritage or delete) |
| §3.1 A1, A16 | `workflow/` exists + `docs/` keeps non-workflow | Phase 1 (skeleton — done Step 0.1) + Phase 8 (docs/README.md + /AGENTS.md updates) |
| §3.1 A2 | `workflow/foundations/` holds `architecture_principles.md` + `module_docs_convention.md` | Phase 2 (low-cardinality mv) |
| §3.1 A4, A5 | `workflow/design/{design-points,decisions}/` with active/archive | Phase 2 (decisions mv) + Phase 6 (design-points mv with authority header strengthening per Q2 §4.4) |
| §3.1 A6 | `workflow/audit/{active,archive}/` with 3 sub-types | Phase 2 (audit mv) + Phase 1.5 (`audit/AGENTS.md` author per Q3 §4.2-4.8) |
| §3.1 A7 | `workflow/blueprints/` inherits `docs/blueprints/` | Phase 3 (templates + state machine extend + Q4/Q3 cross-refs added) |
| §3.1 A8 | `workflow/memory/` inherits `memory/` | Phase 3.5 (memory mv; content cleanup deferred) |
| §3.1 A9 | `workflow/working/` gitignored | Phase 1 (skeleton + gitignore — done Step 0.1) |
| §3.1 A10 | `workflow/heritage/` consolidates legacy | Phase 6 (mv `blueprint_history/`) + Phase 7 (mv CLOSED bundles) |
| §3.1 A12, A13, A15 | Per-pillar AGENTS + umbrella + lock-in | Phase 1.5 (author `design/AGENTS.md` + `audit/AGENTS.md`; extend `blueprints/AGENTS.md` per Q5 §4.4) + Phase 3 (inherit `blueprints/AGENTS.md`) |
| §3.1 A18 | `docs/references/templates/` deleted | Phase 7 (after Q4 confirms subsumption — already done) |
| §3.2 I9 | ADR 4-state decision semantics | Phase 1.5 (`design/AGENTS.md` codifies per Q2 §4.5) |
| §3.2 I10, I11, I13 | 3 audit sub-types + two-concept naming + preflight trigger conditions | Phase 1.5 (`audit/AGENTS.md` codifies per Q3 §4.2-4.4 + §4.8) |
| §3.2 I12 | Design-point authority boundary | Phase 1.5 + Phase 6 mv (strengthen `workflow/design/design-points/README.md` per Q2 §4.4) |
| §3.2 I14 | 7-field unified metadata header | Phase 1.5 (templates encode) + Phase 4 (validator enforces) |
| §7 rec | 8-phase implementation plan + Phase 4 validator | Phase 8 plan + Phase 4 validator design |

**Total blueprint-eligible**: 22 audit triage items, mapped to 8 implementation phases (Phase 1, 1.5, 2, 3, 3.5, 4, 6, 7, 8).

### 2.2 cross-doc blocked

Items that require independent sibling-doc work or future slices; Q1-Q5 closure does **not** unblock them:

| Item | Source | Why blocked |
|---|---|---|
| `~/obsidian_workspace/` integration replacing `docs/references/external/` + `docs/references/bridges/` | Audit §6 + Q1 §4.3 deferred | Requires dedicated integration slice deciding read-only / read-write / harvest cadence; out of scope here |
| CLAUDE.md creation for project-root memory activation | Audit §6 + Q5 §4.7 companion deferral | Requires its own decision (CLAUDE.md content + path priority vs auto-memory); out of scope here |
| Cross-doc S1-S6 + I10/A10 from prior DB/view audit | Audit §6 | Independent slice required (pre-existing deferred per prior session memory) |

### 2.3 no independent action

Items that fold into the implementing blueprint or a different parent slice; no standalone action surface:

| Item | Source | Folded into |
|---|---|---|
| `memory/current.md` stale refresh (9-day gap) | Audit §3.3 D4 | Memory content cleanup slice (separate; out of scope per audit §6) |
| `~/.claude/.../memory/MEMORY.md` size limit (32KB > 24.4KB) | Audit §3.3 D5 | Memory content cleanup slice |
| `project_lifecycle_assets_remaining_after_rc3.md` outdated forward-looking list | Audit §3.3 D11 | Memory content cleanup slice |
| Missing 9 days of session_handoffs (2026-05-14 → 2026-05-22) | Audit §1 primary surface note | Memory content cleanup slice |
| 6 companion auto-memory files canonical promotion | Q5 §4.7 + audit §3.1 A14 | Future per-discipline promotion slices (audit-discipline, release-discipline, blueprint-discipline) |

### 2.4 already aligned

Items where the **current state already honors the design intent** as of this slice's progress so far (Step 0.1 + Step 0.2 closed):

| Item | Source | Why already aligned |
|---|---|---|
| `workflow/CADENCE.md` canonical promotion | Audit §3.1 A11 | Done in Step 0.1 (`0199ab20`); Q5 §4.1 ratifies |
| `workflow/AGENTS.md` umbrella with verbatim lock-in statement | Audit §3.1 A13, A15 | Done in Step 0.1 (`0199ab20`); Q5 §4.2 ratifies |
| Cross-pillar soft-trigger flow | Audit §3.2 I15 | Q5 §4.5 codifies; no enforcement action needed beyond Phase 1.5 AGENTS authoring |
| Conflict priority (CADENCE > per-pillar AGENTS > README) | Audit §3.1 A12 partial | Already in `workflow/AGENTS.md` (Step 0.1); Q5 §4.6 ratifies |
| `workflow/blueprints/AGENTS.md` 8-state machine | Audit §3.2 I8 + §3.4 N1 | Existing in `docs/blueprints/AGENTS.md`; inherited verbatim via Phase 3 mv |
| `docs/blueprints/templates/` 4 templates (task + audit + legacy pair) | Audit §3.4 N3 | Substantive content preserved via Phase 3 mv |
| Audit cross-branch visibility convention (slice-scoped, not auto-merge) | Audit §3.3 D6 | Q3 §4.7 codifies; existing branch-isolated Slice 7C audits honored as-is |
| Sacred branches `master @ 562c7419...` + `v0.1-oss-prep` | Audit §3.4 N5 | Not touched during entire 2026-05-20/22 lineage; cadence Sacred-branch isolation rule preserved |
| 6 existing design-point essays substantive content | Audit §3.4 N4 | Preserved verbatim via Phase 6 mv (only header authority statement strengthens) |

### 2.5 deferred / v2+

Items where the design intent explicitly defers them and shipped state does not implement them; no action this slice or the implementing blueprint:

| Item | Source | Deferral rationale |
|---|---|---|
| Phase 5 conditional 491-archive mv | Audit §3.3 D12 + §7 rec | Decided at Phase 4 validator pass; may be done in same slice OR deferred to a future "archive-mv" slice. Per implementing blueprint §8 (Step 0.4) the default is **defer pending Phase 4 validator outcome** |
| Auto-memory companion file deletion / housekeeping | Q5 §4.7 + §7.4 | Auto-memory is Claude session-priming infrastructure; not subject to workflow/ governance lifecycle. No deletion of `feedback_audit_to_archive_cadence.md` etc. is gated by this slice |
| `docs/references/external/` + `docs/references/bridges/` deletion | Q1 §4.3 | Awaits future obsidian-integration slice; both subtrees remain parked in `docs/references/` until then |
| Skill convention for `workflow/working/` (per-skill templates / cleanup hooks) | Inherent to working/ design | Not specified by Q1-Q5; future slice may define skill conventions if needed |

## 3. Recommended blueprint phase order (with dependency analysis)

The implementing blueprint (Step 0.4) §8 should derive its phase plan from the blueprint-eligible bucket (§2.1) plus the §7 recommendations from the source audit. Recommended order:

```
Phase 1  — Skeleton (DONE in Step 0.1; carried forward as bootstrap evidence)
Phase 1.5 — AGENTS authoring + 5 new templates + workflow/templates/README.md
                   ↓ (gates Phase 2 mv via cleaned target structure)
Phase 2  — Low-cardinality mv (architecture_principles + module_docs_convention →
                   foundations/; docs/decisions/ → design/decisions/active/;
                   docs/audit/ → audit/active/; docs/references/working/design-points/
                   → design/design-points/active/)
                   ↓
Phase 3  — Blueprint templates mv (docs/blueprints/templates/ →
                   workflow/templates/blueprints/) + blueprints/AGENTS.md
                   extension + paired-vs-standalone cross-ref
                   ↓
Phase 3.5 — memory/ mv (memory/ → workflow/memory/; content cleanup deferred)
                   ↓
Phase 4  — Validator script + link integrity check (gates Phase 5)
                   ↓
Phase 5  — (CONDITIONAL) 491-archive mv: docs/blueprints/{active,archive}/ →
                   workflow/blueprints/{active,archive}/. Default: DEFER pending
                   Phase 4 outcome; if validator confirms 0 cross-link breakage
                   then proceed; otherwise create dedicated archive-mv slice
                   ↓
Phase 6  — Heritage mv (blueprint_history/ → workflow/heritage/blueprint_history/;
                   working/ CLOSED bundles → workflow/heritage/bundles/)
                   ↓
Phase 7  — references/working/ case-by-case (delete or mv to heritage/working);
                   docs/references/templates/ delete
                   ↓
Phase 8  — Root governance update (/AGENTS.md path refresh + docs/README.md
                   redirect; closes D1 stale factpy_kernel reference)
```

Dependencies that must be honored:

- **Phase 1.5 before Phase 2**: AGENTS files must exist before content lands in active/, otherwise the validator (Phase 4) cannot enforce 7-field schema or pillar-specific state machines.
- **Phase 4 before Phase 5**: validator must pass on the smaller (non-archive) workflow content first; 491-archive risk is too high to commit without prior validator confidence.
- **Phase 8 last**: root-level pointer update should follow all internal restructure to avoid pointing readers at a half-migrated tree.

The implementing blueprint may further subdivide phases or batch adjacent ones based on commit-size considerations.

## 4. Cadence reminders for the implementing blueprint

Drawn from cadence + Q decisions, applicable to the implementing blueprint:

- **§4 lock table must cite Q1-Q5** by adopted commit `ae375ce5`.
- **§6 boundaries-and-invariants** must include the N-3 protective preservation lock (per CADENCE) for symbols that look like targets but are semantically distinct (e.g., do not delete `docs/SECURITY.md` while migrating `docs/blueprints/`).
- **§8 implementation plan** must derive from §3 above; deviations require explicit deviation log in §10.
- **Preflight is REQUIRED** per Q3 §4.4 trigger conditions (this slice = namespace migration / cross-module + Phase 5 high-risk archive mv).
- **3-commit impl pattern** applies to large mv batches (Phase 2 + Phase 6 are candidates per CADENCE 3-commit pattern).
- **Pre-impl grep amendment** (Step 4.6.5) is critical for Phase 7 case-by-case mv and Phase 8 root-update; both touch cross-cutting paths.
- **No deviation from Q1-Q5 locked decisions** without explicit user revision request (Q-delta-decision pattern from Slice 7C).
- **Sacred-branch isolation** + **dirty-file preservation** + **single-purpose commits** + **"可以推进" mutual authorization** per CADENCE top-level rules.

## 5. Audit trail of Stage 2 closure

For traceability, the 14-commit lineage of Step 0.1 + Step 0.2 culminating in this synthesis:

| # | Commit | Stage | Topic |
|---|---|---|---|
| 1 | `0199ab20` | 0.1 | Scaffold `workflow/` skeleton + `CADENCE.md` + `AGENTS.md` |
| 2 | `79548b0d` | 0.2 audit | Stage 1 audit — workflow governance vs shipped |
| 3 | `73201ffa` | 0.2 Q1 draft | docs/workflow split scope |
| 4 | `c9cc5bda` | 0.2 Q1 tightening | references parking boundary |
| 5 | `96530303` | 0.2 Q2 draft | design pillar structure |
| 6 | `eccba79c` | 0.2 Q2 tightening | retrofit scope wording |
| 7 | `78be5739` | 0.2 Q3 draft | audit pillar structure |
| 8 | `0cc7e0b2` | 0.2 Q3 tightening | audit lifecycle wording |
| 9 | `675226e8` | 0.2 Q4 draft | template centralization |
| 10 | `38847afe` | 0.2 Q4 tightening | metadata validation boundary |
| 11 | `77451df8` | 0.2 Q5 draft | cadence as primary + AGENTS hierarchy |
| 12 | `15d60498` | 0.2 Q5 tightening | AGENTS hierarchy wording |
| 13 | `ae375ce5` | 0.2 batch flip | adopt Q1-Q5 + retrofit Q1-Q4 to 7-field |
| 14 | `4f705f6e` | 0.2 post-adoption tightening | status notes + footers to past tense |

Step 0.3 (this synthesis) adds commit 15. Step 0.4 (blueprint + sibling audit log) will add commit 16.

The implementing blueprint may cite this synthesis as `workflow/audit/active/2026-05-22_post-q-workflow-governance-synthesis.md` in its §4 lock table and §8 phase plan inputs.

## 6. Acceptance for this synthesis

This synthesis is **complete** when:

- All audit §3.3 D-series + §6 cross-doc seams + §7 recommendations are classified into exactly one of the 5 buckets above (verified by hand-check).
- Recommended phase order is consistent with Q1-Q5 decision dependencies (verified above in §3).
- Cadence reminders capture all Q1-Q5 derived constraints (verified above in §4).
- Audit trail is current as of the most recent commit (verified above in §5; this synthesis itself becomes commit 15 upon landing).

Per Q3 §4.6 audit lifecycle, this file remains in `workflow/audit/active/` while the implementing blueprint is `Status: draft → scoped → implementing → implemented`. It moves to `workflow/audit/archive/` in the same commit batch as the implementing blueprint's Step 4.9 archive.
