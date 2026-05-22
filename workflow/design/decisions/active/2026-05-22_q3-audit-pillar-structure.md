# Q3 Decision: audit pillar structure

- Status: adopted
- Created: 2026-05-22
- Last Updated: 2026-05-22
- Authority: design constraint; locks the internal structure, naming disambiguation, sub-type taxonomy, trigger conditions, and cross-branch visibility convention of the `workflow/audit/` pillar before Q4 templates and the Phase 1.5 `audit/AGENTS.md` author work.
- Inputs:
  - [workflow/audit/active/2026-05-22_workflow-governance-vs-shipped.md](../../../audit/active/2026-05-22_workflow-governance-vs-shipped.md) §3.1 A6; §3.2 I10, I11, I13; §3.3 D6; §4 Q3
  - [Q1 decision](./2026-05-22_q1-docs-workflow-split.md) — split scope; `workflow/audit/` exists as a pillar
  - [Q2 decision](./2026-05-22_q2-design-pillar-structure.md) — ADR 4-state for decisions, since synthesis sub-type re-buckets per ADR-closed decision state
  - 2026-05-22 design conversation: user call-out of two-audit terminology overlap + preflight over-application risk
- Outputs / Downstream:
  - [Q4 decision](./2026-05-22_q4-template-centralization.md) — audit pillar templates encode Q3 §4.3 sub-type taxonomy
  - [Q5 decision](./2026-05-22_q5-cadence-as-primary-and-agents-hierarchy.md) — AGENTS hierarchy locks `workflow/audit/AGENTS.md` content per Q3
  - `workflow/audit/AGENTS.md` (Phase 1.5)
  - `workflow/templates/audit/{vs-shipped,preflight,synthesis}.md` (Phase 1.5)
  - Implementing blueprint Phase 2 (audit mv)
- Related:
  - [Q2 decision](./2026-05-22_q2-design-pillar-structure.md) — parallel pillar
  - `workflow/blueprints/AGENTS.md` (Phase 3 mv) — paired-vs-standalone cross-reference target
  - Slice 7C `docs/audit/2026-05-21_registry-final-removal-vs-shipped.md` (branch-isolated audit example per audit §3.3 D6)
- Branch: `v0.2.0-blueprint-workflow-governance-promotion-2026-05-22`

> **Status note**: this decision was initially drafted with `Status: proposed`. ADR 4-state semantics defined in Q2 §4.5 apply here (decisions ADR semantics drive synthesis re-bucketing). It was adopted in the Q1-Q5 batch commit `ae375ce5` (2026-05-22), and its header was retrofitted to the Q4 §4.3 7-field schema in the same commit. See §9 Decision Record for the transition log.

## 1. Inputs

- Audit §3.1 A6 — "`workflow/audit/{active,archive}/` with 3 sub-types" classified `(b) small gap`; current `docs/audit/` has 2 visible files (4+ in git history across branches), no README, no governance.
- Audit §3.2 I10 — "3 audit sub-types formalized" classified `(b) small gap`; sub-types implicit in cadence but not formally typed in any AGENTS.
- Audit §3.2 I11 — "Two distinct audit concepts disambiguated" classified `(c) shape conflict`; paired blueprint audit log (`*.audit.md`) and standalone audit record (`workflow/audit/*.md`) currently share the word "audit" causing confusion.
- Audit §3.2 I13 — "Preflight trigger conditions formalized" classified `(d) genuinely new`; cadence currently assumes preflight always required for substrate slices, no formal optional/required boundary.
- Audit §3.3 D6 — "`docs/audit/` content branch-isolated" classified `(c) shape conflict`; Slice 7C audit files visible only on creating branch, not current branch. Audit forward-merge policy needed.
- Audit §4 Q3 — conversational locks: paired-vs-standalone naming, 3 sub-types formalized as separate templates, preflight trigger conditions enumeration, cross-branch visibility convention.
- 2026-05-22 design conversation: user review explicitly called out the two-audit terminology overlap and preflight over-application risk.
- `workflow/CADENCE.md` (Step 0.1 @ `0199ab20`) — Stage 1, Step 4.3, and post-Q synthesis already enumerate the 3 sub-types implicitly; Q3 formalizes them.
- [docs/blueprints/AGENTS.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/AGENTS.md) — 70-line state machine that pairs each blueprint with a sibling `*.audit.md` log (paired concept #1).
- [docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md](/Users/zhenzhili/hnsm-backend/docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md) — 976-line example of standalone vs-shipped audit (standalone concept #2).
- Q1 decision (split scope locks `workflow/audit/` placement under `workflow/`).
- Q2 decision (ADR 4-state semantics enable synthesis re-bucketing).

## 2. Scope

This decision locks:

- The internal structure of `workflow/audit/` (active/archive split; no further sub-pillars).
- The disambiguation between **paired blueprint audit log** (`*.audit.md` sibling to blueprint) and **standalone audit record** (file in `workflow/audit/`).
- The taxonomy of standalone audit sub-types (`vs-shipped`, `preflight`, `synthesis`).
- Filename conventions for each sub-type.
- Preflight trigger conditions (when standalone preflight is required vs optional).
- Synthesis trigger conditions (when post-Q synthesis is required vs optional).
- The audit lifecycle (active/archive transition tied to consuming slice).
- Cross-branch visibility convention (audit travels with its consuming slice's branch lineage).

## 3. Non-scope

- Template body structure for the 3 sub-types (covered by Q4).
- The 4-level AGENTS hierarchy and which AGENTS file codifies the rules authored here (covered by Q5; the relevant file is `workflow/audit/AGENTS.md` per Q5 plan).
- Cross-pillar trigger flow connecting audit → decisions → blueprint (covered by Q5 soft-trigger flow).
- vs-shipped trigger conditions (vs-shipped is implicitly required for any non-trivial audit-first slice; explicit trigger conditions for vs-shipped are not Q3-scoped and remain implicit in CADENCE Stage 1).
- Migration ordering of existing audit files (covered by the implementing blueprint's Phase 2 low-cardinality mv).
- Retrofit of existing audit files' header metadata (the implementing blueprint applies Status field per §4.7 below at mv time).

## 4. Decision

### 4.1 audit pillar layout

The `workflow/audit/` pillar has a flat `active/archive` split, with no sub-type subdirectories:

```
workflow/audit/
├── README.md          (introduces sub-types + lifecycle + trigger conditions)
├── AGENTS.md          (state machine + trigger rules + cross-branch visibility; authored in Phase 1.5)
├── active/            (audits whose consuming slice is in-flight)
└── archive/           (audits whose consuming slice's blueprint has archived)
```

All 3 standalone sub-types (vs-shipped / preflight / synthesis) live in the **same** `active/` or `archive/` directory. Sub-type is encoded in the filename, not in a subdirectory. Rationale: keeping a flat layout makes the consuming-slice-as-lifetime-anchor (§4.6) easier to apply uniformly across sub-types.

### 4.2 paired vs standalone — disambiguation

The word "audit" in this repo refers to two distinct things:

| Concept | Filename pattern | Location | Role |
|---|---|---|---|
| **Paired blueprint audit log** | `<basename>.audit.md` (sibling to blueprint) | `workflow/blueprints/{active,archive}/` | Per-blueprint event log; records draft / scoped / implementing / implemented / archive transitions and decision notes |
| **Standalone audit record** | `YYYY-MM-DD_<topic>-<subtype>.md` | `workflow/audit/{active,archive}/` | Cross-cutting drift triage, preflight safety check, or post-Q synthesis; informs but does not log blueprint stage transitions |

These are NOT interchangeable. They serve different roles, live in different directories, and have different lifecycle rules.

- `workflow/blueprints/AGENTS.md` codifies the **paired blueprint audit log** semantics (existing 70-line state machine, inherited unchanged via Phase 3 mv).
- `workflow/audit/AGENTS.md` codifies the **standalone audit record** semantics (Phase 1.5 author work).

`workflow/audit/AGENTS.md` must contain an explicit cross-reference to `workflow/blueprints/AGENTS.md` warning that the two are distinct concepts.

### 4.3 standalone sub-types

A standalone audit record is one of exactly three sub-types, identified by filename suffix:

| Sub-type | Filename suffix | Purpose | Stage in CADENCE |
|---|---|---|---|
| **`vs-shipped`** | `YYYY-MM-DD_<topic>-vs-shipped.md` | Compares a design doc against shipped runtime code completely (not grep snippets). Builds 5-state triage table + open question list. | Stage 1 (audit phase) |
| **`preflight`** | `YYYY-MM-DD_<topic>-preflight.md` | Re-reads blueprint-referenced shipped files at preflight-row-drafting time. Surfaces 5-bucket severity findings before scoped anchor. | Stage 4 Step 4.3 |
| **`synthesis`** | `YYYY-MM-DD_post-q-<topic>-synthesis.md` (or `YYYY-MM-DD_<topic>-synthesis.md` if no Q chain) | Re-buckets audit drift after Q decisions close. Outputs 5-bucket classification (blueprint-eligible / cross-doc blocked / no independent action / already aligned / deferred). | Stage 3 (post-Q synthesis) |

No other sub-types are recognized in this slice. Future sub-types (e.g., post-release-validation) would require a Q-delta-decision against Q3.

### 4.4 preflight trigger conditions

Standalone preflight audit is **required** when any of the following apply:

1. **Subtractive removal**: slice deletes a shipped public symbol, public method, public API field, or public route.
2. **Cross-module protocol change**: slice changes a DTO shape, ledger format, wire protocol, identity formula, or other contract that spans ≥2 modules.
3. **Namespace migration**: slice renames or restructures packages affecting downstream callers (e.g., `factpy_kernel` → `factgraph` historical migration).
4. **Historical-design compatibility**: slice must precisely match a historical design (e.g., compatibility shim, legacy export surface).
5. **Pre-release verification**: slice prepares an rc.N → release tag boundary or PyPI publication.

Standalone preflight is **optional** (may be skipped) when:

1. Pure additive feature within a single module (no public surface change, no cross-module DTO).
2. Bug fix in established API surface (signature preserved, observable behavior corrected).
3. Pure refactor with full test coverage and no observable behavior change.
4. Cleanup-style slice per the cleanup-slice-cadence section of `workflow/blueprints/AGENTS.md` (post-Phase 3 mv).
5. Tiny local fix per `workflow/CADENCE.md` Scope-and-Applicability section.

A slice that skips standalone preflight must record the skip rationale in its blueprint §6 boundaries-and-invariants OR §10 outcome. Skipping is not a deviation requiring a `Decision Record` row; it is a normal cadence variant.

If a slice has any doubt about whether preflight is required, the default is **required**. The cost of an unnecessary preflight is small (1 commit, ~30-60 minute drafting); the cost of a missed preflight surfacing as in-impl scope drift is large (potential blueprint walkback per Slice 6 (A-fallback) cadence).

### 4.5 synthesis trigger conditions

Standalone synthesis audit is **required** when:

1. ≥3 Q decisions close in a single audit's chain, **AND** audit findings span ≥2 of the 5 buckets (blueprint-eligible / cross-doc blocked / no independent action / already aligned / deferred).
2. Audit drift inventory spans multiple sibling docs or cross-doc seams that need to be partitioned into actionable vs blocked.

Standalone synthesis is **optional** when:

1. Single Q decision closes (Q1-only slice).
2. All audit findings are obviously blueprint-eligible (single-bucket triage).
3. Slice is cleanup-style with no Q-resolution chain.

The workflow-governance-promotion slice itself (this slice, 5 Q decisions, 4 buckets in audit §3.3 D-series + §6 cross-doc-seams) qualifies as required-synthesis per criterion 1.

### 4.6 audit lifecycle (active/archive)

Standalone audit files transition active → archive via the consuming slice:

- An audit file lives in `workflow/audit/active/` while **its consuming slice's blueprint is in `workflow/blueprints/active/`** (Status: `draft`, `scoped`, `implementing`, or `implemented`).
- The audit file moves to `workflow/audit/archive/` **in the same commit batch** as the consuming slice's blueprint archives (Step 4.9 of the cadence).
- An audit file may serve **multiple consuming slices** (e.g., a vs-shipped audit informing both an immediate slice and a follow-up). In that case, the audit moves to archive when the **last** consuming slice's blueprint archives.

This is the **same archive convention as blueprints** (per `workflow/blueprints/AGENTS.md` Phase 3-inherited rules), with the addition that audit files explicitly travel with their slices.

Optional `Status:` header field for drafting visibility:

| Status (optional) | Meaning |
|---|---|
| `skeleton` | Audit triage table started but not yet filled |
| `complete` | All rows filled, ready for downstream consumption |
| `superseded` | Replaced by newer audit (must cite successor); rare |

`Status:` is for drafting convenience; the canonical lifecycle signal is the directory (`active/` vs `archive/`), not the Status field.

### 4.7 cross-branch visibility convention

Standalone audit files are **slice-scoped artifacts**, not globally-visible reference documents. The following convention applies:

- An audit lives on the branch that creates it (typically the audit-only branch `v<version>-<topic>-audit-<date>` or the consuming blueprint branch `v<version>-blueprint-<topic>-<date>`).
- Within the consuming slice's lifetime, audits are branch-local. Cross-slice reference requires explicit branch checkout.
- At slice closure (blueprint archive — Step 4.9), the audit + decision + blueprint chain is **completed on the slice branch**. Archive itself does not integrate to `master` or any release branch.
- Integration into `master` or any release line is a **separate, explicit, user-authorized push or merge** governed by CADENCE Sacred-branch isolation rule. It is not triggered automatically by archive.
- "Globally visible" therefore means **authorized integration into a canonical branch** (typically `master` via PR or fast-forward push), not the archive commit itself.

Existing branch-isolated audits (e.g., Slice 7C `2026-05-21_registry-final-removal-vs-shipped.md` only on `v0.2.0-registry-final-removal-audit-2026-05-21`) are honored as-is; no retroactive forward-merge is required. Future slices apply this convention from inception.

### 4.8 audit file header convention

Every standalone audit file must include the following in its header:

```
- Status: <skeleton | complete | superseded>   (optional, drafting convenience)
- Created: YYYY-MM-DD
- Branch: <slice branch>
- Source intent: <pointer to design doc or conversation>
- Authority: working triage document; informs but does not lock implementation
- (For preflight only) Blueprint: <pointer to consuming blueprint>
- (For synthesis only) Source audit: <pointer to vs-shipped audit being re-bucketed>
- (For synthesis only) Closed Q decisions: <pointers to Q decision records>
```

The unified 7-field metadata template from Q4 (Status / Created / Last Updated / Authority / Inputs / Outputs / Related) is compatible with this convention; Q4 templates author the per-sub-type concrete templates.

## 5. Rejected Alternatives

### Option (a-sub-dirs): Sub-directories per sub-type (`workflow/audit/vs-shipped/`, `workflow/audit/preflight/`, `workflow/audit/synthesis/`)

- **Why rejected**: complicates the active/archive split (would need `vs-shipped/active`, `vs-shipped/archive`, etc., × 3 sub-types = 6 leaf dirs). Filename suffix achieves the same disambiguation with less directory churn. The flat layout also makes the consuming-slice-as-lifetime-anchor easier to enforce uniformly.

### Option (b-naming): Use `audit-log/` for paired blueprint audit and `audit/` for standalone

- **Why rejected**: would require renaming `*.audit.md` → `*.audit-log.md` across 491 archived blueprints, plus all existing references and the existing `workflow/blueprints/AGENTS.md` state machine. The naming churn cost is high and the disambiguation can be achieved entirely within `workflow/audit/AGENTS.md` cross-reference text.

### Option (c-preflight-always-required): Always require preflight for any non-trivial slice

- **Why rejected**: over-applies the cadence. Per user review correction, small-scope slices (additive feature, bug fix in established surface, pure refactor) do not need standalone preflight. Always-required would burden cleanup-style slices unnecessarily.

### Option (d-preflight-never-required): Make preflight always optional

- **Why rejected**: the user-locked trigger list in §4.4 captures cases where preflight has empirically caught critical issues (Slice 6 N-1 through N-5; Slice 7A N-1; Slice 7C P1-1/P1-2). Making preflight always-optional would re-introduce the in-impl scope drift risk that Step 4.3 was designed to prevent.

### Option (e-cross-branch-merge-on-finalize): Auto-forward-merge each audit to master once `Status: complete`

- **Why rejected**: violates `workflow/CADENCE.md` Sacred-branch isolation rule (never auto-push, never auto-merge sacred). Forward-merge happens through the normal slice closure mechanism, which already provides the appropriate explicit-user-authorization gate.

### Option (f-status-required): Require `Status:` field on every audit file

- **Why rejected**: directory placement (`active/` vs `archive/`) already carries the canonical lifecycle signal. Requiring `Status:` doubles the metadata for no semantic gain. The current convention (Status optional, directory authoritative) preserves drafting convenience without ambiguity.

## 6. Supporting Evidence

- Audit §3.1 A6 — confirms `workflow/audit/` is a small structural gap above current `docs/audit/`.
- Audit §3.2 I10, I11 — confirms 3-sub-type formalization and two-concept disambiguation are needed but absent.
- Audit §3.2 I13 — confirms preflight trigger conditions are genuinely new (no prior formalization).
- Audit §3.3 D6 — confirms cross-branch visibility is a real concern, not theoretical.
- [docs/blueprints/AGENTS.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/AGENTS.md) line 17 — "Audit files record decision events, scope changes, and implementation checkpoints in chronological order" describes paired audit role.
- [docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md](/Users/zhenzhili/hnsm-backend/docs/audit/2026-05-20_database-view-design-vs-shipped-runtime.md) — 976-line standalone vs-shipped audit example.
- [docs/audit/2026-05-20_post-q-db-view-synthesis.md](/Users/zhenzhili/hnsm-backend/docs/audit/2026-05-20_post-q-db-view-synthesis.md) — 190-line standalone synthesis audit example.
- Slice 7C preflight trigger validation: subtractive removal slice (criterion 1) correctly required preflight; preflight caught 3 N-findings preventing scope drift.
- Slice 7A preflight trigger validation: cross-module protocol slice (criterion 2) correctly required preflight; preflight caught N-1 (test rename) and PF-2 (deprecation scope) before impl.
- 2026-05-22 user review: explicitly called out two-audit terminology overlap and preflight over-application risk; this decision locks the user-corrected framing.

## 7. Consequences

### 7.1 Downstream unblocking

- A6, I10, I11, I13, D6 in audit triage are formally closed.
- Q4 (templates) can author 3 distinct sub-type templates with concrete per-sub-type metadata requirements.
- Q5 (cadence as primary + AGENTS hierarchy) can codify these rules in `workflow/audit/AGENTS.md` (Phase 1.5).
- The implementing blueprint's preflight stage (Step 4.3) is qualified-by-trigger-conditions, allowing cleanup-style and small-scope slices to skip without cadence violation.

### 7.2 Required follow-up actions in the implementing blueprint

- **Phase 1.5 (AGENTS authoring)**: `workflow/audit/AGENTS.md` codifies §4.2-4.7 verbatim or with semantic equivalence; must include explicit cross-reference to `workflow/blueprints/AGENTS.md` for paired-vs-standalone distinction.
- **Phase 2 (low-cardinality mv) — existing audit retrofit**:
  - 2 existing files in `docs/audit/` (the 2026-05-20 DB/view audit + synthesis) migrate to `workflow/audit/active/` and become `archive/` candidates depending on DB/view slice closure state at the time of the implementing blueprint's archive.
  - Header retrofit: ensure each migrated file has Source intent / Authority / Inputs fields per §4.8; backfill if absent.
- **Phase 4 (validator)**: validator enforces:
  - Filename suffix is one of `-vs-shipped`, `-preflight`, `-synthesis` for standalone files in `workflow/audit/`.
  - Each `preflight` file references a consuming blueprint.
  - Each `synthesis` file references a source vs-shipped audit + ≥1 closed Q decision.
  - Audit files in `active/` are accompanied by a consuming blueprint in `workflow/blueprints/active/` (warning if orphaned).

### 7.3 Cross-pillar interaction

- This Q3 decision is the prerequisite for Q5's `workflow/audit/AGENTS.md` author specification.
- The synthesis sub-type depends on Q2's ADR 4-state semantics — synthesis re-buckets only after decisions reach `adopted` (or `superseded` / `withdrawn`) state.
- The preflight sub-type interacts with the cleanup-slice-cadence (post-Phase 3 mv); both must be referenced from the implementing blueprint's §4 lock table.

### 7.4 No retroactive enforcement

Existing audit files (the 2 in `docs/audit/` + the 4 in Slice 7C branches per audit §3.3 D6) are not retroactively re-classified. They migrate via Phase 2 with current content; the Phase 4 validator may flag missing header fields as warnings, not errors, for existing files. New audits created post-Phase 2 follow §4.8 from inception.

## 8. Acceptance Criteria

Post-implementing-blueprint, the audit pillar must satisfy:

1. `workflow/audit/{active,archive}/` exist; no sub-type subdirectories.
2. `workflow/audit/AGENTS.md` exists, codifies §4.2-4.7 verbatim or with semantic equivalence, and explicitly cross-references `workflow/blueprints/AGENTS.md` for paired-vs-standalone distinction.
3. `workflow/audit/README.md` exists and introduces sub-types + lifecycle + trigger conditions without re-introducing state machine ambiguity (deference to `AGENTS.md`).
4. The 2 existing migrated audits + the 3 new standalone audit records authored/planned in this slice (vs-shipped + synthesis + preflight) all have correct filename suffix and header convention per §4.8. (Paired blueprint `*.audit.md` siblings are NOT counted here; they live under `workflow/blueprints/` and are governed by `workflow/blueprints/AGENTS.md`.)
5. Validator (Phase 4) passes:
   - Filename suffix whitelist (`-vs-shipped` | `-preflight` | `-synthesis`).
   - Required-field presence per §4.8.
   - Active/archive placement aligned with consuming-slice state.
6. **Preflight requirement honored**: no slice is marked as *requiring* standalone preflight unless it matches a §4.4 required trigger condition. **Voluntary preflight permitted**: a slice may produce a standalone preflight even when not required by §4.4, provided the voluntary rationale is recorded in its blueprint §6 boundaries-and-invariants or §10 outcome. Validated by reviewer practice; not automatable.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-22 | proposed | Decision drafted | Q3 of 5; formalizes audit pillar that has been operating informally since 2026-05-20 |
| 2026-05-22 | adopted | Status flip + header retrofit via Q1-Q5 batch commit | Header retrofitted to Q4 §4.3 7-field schema: added `Last Updated` / `Outputs / Downstream` / `Related`; recast `Audit source` and peer `Depends on` (Q1, Q2) as `Inputs:` bullets; `Branch` preserved as extension. |

This decision will not trigger audit file convention enforcement until the implementing blueprint reaches `Status: scoped`.
