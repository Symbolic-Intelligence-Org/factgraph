# Q4 Decision: template centralization

- Status: adopted
- Created: 2026-05-22
- Last Updated: 2026-05-22
- Authority: design constraint; locks the centralized template location, the 9-template inventory, the unified metadata schema, and the template authoritative role before Phase 1.5 (template authoring) and Phase 3 (existing template mv) of the implementing blueprint.
- Inputs:
  - [workflow/audit/active/2026-05-22_workflow-governance-vs-shipped.md](../../../audit/active/2026-05-22_workflow-governance-vs-shipped.md) §3.1 A3, A18; §3.2 I14; §3.3 D3; §4 Q4
  - [Q1 decision](./2026-05-22_q1-docs-workflow-split.md) — split scope; `workflow/templates/` placed under `workflow/`
  - [Q2 decision](./2026-05-22_q2-design-pillar-structure.md) — design pillar templates encode Q2 ADR + design-point conventions
  - [Q3 decision](./2026-05-22_q3-audit-pillar-structure.md) — audit pillar templates encode Q3 sub-type taxonomy
  - 2026-05-22 design conversation: user proposed unified 7-field metadata schema + per-pillar pointer rule
- Outputs / Downstream:
  - [Q5 decision](./2026-05-22_q5-cadence-as-primary-and-agents-hierarchy.md) — AGENTS hierarchy adopts Q4 §4.4 per-pillar pointer rule
  - `workflow/templates/README.md` (Phase 1.5) — codifies the 7-field schema + customization policy
  - 5 new templates (Phase 1.5: design-point, decision, vs-shipped, preflight, synthesis)
  - 4 mv'd templates (Phase 3: blueprint task + audit + legacy + legacy.audit)
  - Q1-Q5 batch flip commit (this commit) — performs Q1-Q4 retrofit per §7.3
  - Phase 4 validator (stratified per §7.2)
- Related:
  - [Q2 decision](./2026-05-22_q2-design-pillar-structure.md) — decision + design-point templates depend on Q2 semantics
  - [Q3 decision](./2026-05-22_q3-audit-pillar-structure.md) — audit sub-type templates depend on Q3 taxonomy
  - `feedback_refactor_execution_traps.md` (auto-memory) — git-history-preserving mv guidance for Phase 3
- Branch: `v0.2.0-blueprint-workflow-governance-promotion-2026-05-22`

> **Status note**: this decision is opened with `Status: proposed`. ADR 4-state semantics defined in Q2 §4.5 apply here. Q1-Q5 batch status flip will apply after Q5 closes.

## 1. Inputs

- Audit §3.1 A3 — "`workflow/templates/` centralized inventory (9 templates: 4 blueprint + 2 design + 3 audit)" classified `(c) shape conflict`; current templates split between `docs/blueprints/templates/` (4 files) and `docs/references/templates/` (1 file), with 4 missing (decision, design-point, 3 audit sub-types).
- Audit §3.1 A18 — "`references/templates/` deleted (subsumed by centralized templates)" classified `(b) small mv + delete`.
- Audit §3.2 I14 — "Template unified metadata header (7-field)" classified `(d) genuinely new`; no template currently enforces this.
- Audit §3.3 D3 — "Templates split between 2 locations" reaffirms the consolidation need.
- Audit §4 Q4 — conversational locks: all 9 templates centralized at `workflow/templates/<pillar>/`; inventory of 4+2+3; unified 7-field metadata header; `docs/references/templates/reference_note.md` deleted after Q4 confirms subsumption.
- 2026-05-22 design conversation: user explicitly proposed the 7-field metadata schema (Status / Created / Last Updated / Authority / Inputs / Outputs / Downstream / Related) and noted that template centralization should not force agents to do global search per use (which led to the per-pillar pointer rule below).
- Existing [docs/blueprints/templates/task_blueprint.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/templates/task_blueprint.md) (71 lines), [docs/blueprints/templates/task_blueprint.audit.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/templates/task_blueprint.audit.md) (19 lines), [docs/blueprints/templates/legacy_reconstructed_archive.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/templates/legacy_reconstructed_archive.md) (75 lines), [docs/blueprints/templates/legacy_reconstructed_archive.audit.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/templates/legacy_reconstructed_archive.audit.md) (29 lines) — the 4 existing blueprint templates to be migrated.
- Existing [docs/references/templates/reference_note.md](/Users/zhenzhili/hnsm-backend/docs/references/templates/reference_note.md) — the single existing reference-note template (fate locked in §4.6).
- Q1 decision (`workflow/templates/` placed under `workflow/`).
- Q2 decision (design-point and decision templates use Q2 state machines and authority boundaries).
- Q3 decision (audit templates use Q3 sub-type filename convention and trigger conditions).

## 2. Scope

This decision locks:

- The single canonical location for all workflow templates (`workflow/templates/`).
- The per-pillar subdirectory layout (`blueprints/`, `design/`, `audit/`).
- The 9-template inventory (filenames, pillar, provenance).
- The unified 7-field metadata schema all templates must include.
- The authoritative role of templates (only approved starting points; manual drafting discouraged) and the customization policy (sections may extend; 7-field header is verbatim).
- The per-pillar pointer rule (each pillar's AGENTS.md must list the templates it consumes, so template discovery is local to the pillar).
- The fate of the existing `docs/references/templates/reference_note.md`.

## 3. Non-scope

- The actual body content of each new template (covered by Phase 1.5 of the implementing blueprint — the templates will be authored there, with this decision as the structural lock).
- Retroactive 7-field-header migration for the 491 existing archived blueprints (out of scope; Q4 enforces forward-going compliance only).
- Validator implementation details for the 7-field schema check (covered by Phase 4 of the implementing blueprint).
- Naming convention for non-template metadata fields specific to one pillar (e.g., blueprints' `Related Modules`, decisions' `Branch`, audits' `Source intent`) — these are pillar-specific extensions allowed beyond the unified 7 fields per §4.3.

## 4. Decision

### 4.1 centralization location

All workflow templates live at exactly one canonical location:

```
workflow/templates/
├── README.md                          (introduces template inventory + usage rules + 7-field schema)
├── blueprints/
│   ├── task_blueprint.md
│   ├── task_blueprint.audit.md
│   ├── legacy_reconstructed_archive.md
│   └── legacy_reconstructed_archive.audit.md
├── design/
│   ├── design-point.md
│   └── decision.md
└── audit/
    ├── vs-shipped.md
    ├── preflight.md
    └── synthesis.md
```

No additional template lives outside this tree. The previous `docs/blueprints/templates/` directory is dissolved (Phase 3 mv); `docs/references/templates/` directory is deleted (Phase 7, per §4.6).

### 4.2 9-template inventory

| # | Pillar | Template purpose | Filename | Provenance |
|---|---|---|---|---|
| 1 | blueprints | Task blueprint (main implementation plan) | `task_blueprint.md` | Existing; Phase 3 mv from `docs/blueprints/templates/` |
| 2 | blueprints | Task blueprint audit log (sibling) | `task_blueprint.audit.md` | Existing; Phase 3 mv |
| 3 | blueprints | Legacy reconstructed archive | `legacy_reconstructed_archive.md` | Existing; Phase 3 mv |
| 4 | blueprints | Legacy reconstructed audit log | `legacy_reconstructed_archive.audit.md` | Existing; Phase 3 mv |
| 5 | design | Design-point essay | `design-point.md` | **New**; Phase 1.5 author per Q2 §4.4 authority header |
| 6 | design | Decision record (ADR) | `decision.md` | **New**; Phase 1.5 author per Q2 §4.5 ADR 4-state |
| 7 | audit | Vs-shipped audit record | `vs-shipped.md` | **New**; Phase 1.5 author per Q3 §4.3 |
| 8 | audit | Preflight audit record | `preflight.md` | **New**; Phase 1.5 author per Q3 §4.3 + §4.4 trigger conditions |
| 9 | audit | Post-Q synthesis record | `synthesis.md` | **New**; Phase 1.5 author per Q3 §4.3 + §4.5 trigger conditions |

5 new templates + 4 mv'd existing templates = 9 total.

### 4.3 unified 7-field metadata header

Every workflow document created from a template (i.e., every blueprint, **paired blueprint audit log**, decision, design-point, and standalone audit) must include the following 7-field block as the first content section after the H1 title:

```yaml
- Status: <pillar-specific allowed value>
- Created: YYYY-MM-DD
- Last Updated: YYYY-MM-DD
- Authority: <pillar-specific authority statement>
- Inputs:
  - <pointer to triggering audit / decision / design-point / external source>
- Outputs / Downstream:
  - <pointer to consuming document(s)>
- Related:
  - <cross-references not in input/output chain>
```

**Per-field semantics**:

| Field | Required | Description |
|---|---|---|
| `Status` | Yes | Pillar-specific lifecycle state. **The `Status` field is always present; the value varies by pillar.** Blueprints: one of 8 states per `blueprints/AGENTS.md`. Decisions: one of 4 ADR states per Q2 §4.5. Design-points: `n/a` (active/archive directory signals lifecycle), or a free-form drafting marker such as `working` / `mature`. Audits: `n/a`, or one of `skeleton` / `complete` / `superseded` per Q3 §4.6. Paired blueprint audit logs: mirror the sibling blueprint's `Status` value. |
| `Created` | Yes | `YYYY-MM-DD` of first commit. Never updated. |
| `Last Updated` | Yes | `YYYY-MM-DD` of most recent substantive content commit. Refreshed when the file's meaning changes; not for typo-fix commits. |
| `Authority` | Yes | One-line statement of what role this document plays. Pillar-specific: blueprints "task constraint", decisions "design constraint", design-points "candidate design / non-authoritative reference", audits "working triage document". |
| `Inputs` | Yes | Bullet list of upstream sources that triggered or informed this document. May include audit pointers, decision references, design-point essays, external standards, or user-conversation pointers. |
| `Outputs / Downstream` | Yes | Bullet list of downstream documents that consume this. May be empty bullet list with explicit `- (none yet)` if the document has no downstream consumers at creation time. |
| `Related` | Yes | Bullet list of cross-references not in the input/output chain (sibling slices, parallel decisions, etc.). May be empty `- (none)`. |

**Paired blueprint audit log convention**: paired blueprint audit logs (`<basename>.audit.md` siblings to blueprints) carry the same 7-field header as their sibling blueprints, with pillar-specific values:

- `Status:` mirrors the sibling blueprint's value (e.g., `draft`, `scoped`, `implementing`, `implemented`, `archived`).
- `Authority: paired blueprint audit log` (denotes the document's role as event log for its sibling blueprint).
- `Inputs:` points to the sibling blueprint (`- [<basename>.md](./<basename>.md)`).
- `Outputs / Downstream:` typically `- (none)` (paired audit logs are passive event records, not consumed downstream).
- `Related:` cross-references to related slices, prior audit logs, or relevant memory entries.

**Pillar-specific extensions allowed**: each pillar may add fields **beyond** the 7-field minimum (not as substitutes). Examples:

- Blueprints commonly add: `Related Modules:`, `Audit Log:` (pointer to sibling `.audit.md`).
- Decisions commonly add: `Branch:`, `Depends on:` (peer decision dependencies).
- Audits commonly add: `Source intent:` (link to design doc being audited), `Blueprint:` (for preflight), `Source audit:` + `Closed Q decisions:` (for synthesis).

Pillar-specific extensions are documented in each pillar's AGENTS.md (Phase 1.5).

### 4.4 per-pillar pointer rule

Centralized templates **must not** require agents to do global search for "what template to use" each time. Every pillar's `AGENTS.md` (Phase 1.5) and `README.md` must include a "Templates" section explicitly pointing to the centralized templates that pillar consumes:

Example for `workflow/blueprints/AGENTS.md`:

```markdown
## Templates

Authoritative starting points live in `workflow/templates/blueprints/`:

- `task_blueprint.md` — standard task blueprint (state machine: 8-state)
- `task_blueprint.audit.md` — sibling audit log (paired)
- `legacy_reconstructed_archive.md` — reconstructed archive
- `legacy_reconstructed_archive.audit.md` — reconstructed audit log

Manual drafting (not from template) is discouraged; see `workflow/templates/README.md` for the customization policy.
```

Similar pointer blocks in `workflow/design/AGENTS.md` (lists `design-point.md` + `decision.md`) and `workflow/audit/AGENTS.md` (lists `vs-shipped.md` + `preflight.md` + `synthesis.md`).

The pointer block is **mandatory** in each pillar's AGENTS.md; absent pointers fail the Phase 4 validator (warning, not error).

### 4.5 template authoritative role + customization policy

Templates are the **only approved starting point** for new documents in their pillar. Manual drafting from scratch is discouraged and must be justified in the document's `Authority:` field or the blueprint creating it.

Customization rules:

- **Allowed**: adding sections beyond the template structure (e.g., a blueprint may add a §11 "Migration notes" if needed for a specific slice).
- **Allowed**: reordering sections within the same hierarchical level if the pillar's AGENTS.md permits (default: blueprints have fixed §1-§9 order per `task_blueprint.md`; decisions have fixed §1-§9 order; audits may reorder freely).
- **Allowed**: omitting clearly-marked optional sections (templates indicate `(optional)` in the section heading where applicable).
- **NOT allowed**: modifying the 7-field metadata header schema, omitting required fields, or substituting alternative field names. The 7-field block is **verbatim**.
- **NOT allowed**: silently dropping `Inputs:`, `Outputs / Downstream:`, or `Related:` when they would be empty. Use explicit `- (none)` or `- (none yet)` instead.

Rationale: templates encode hard-won cadence lessons (5-bucket severity in preflight, ADR semantics in decisions, 7-bullet ProofFrame structure in blueprints, etc.). Free-form drafting loses those lessons in drift.

### 4.6 `docs/references/templates/reference_note.md` fate

The single existing reference-note template at `docs/references/templates/reference_note.md` is **subsumed and deleted**, not migrated. Rationale:

- It is a generic reference-note starter, not a workflow-pillar template.
- None of the 9 Q4 templates fills the same role; reference notes for external research material (audit §1 out-of-scope category) will live in `~/obsidian_workspace/` per Q1 §4.3 (deferred to obsidian-integration slice).
- Design-point essays now have a dedicated template (`workflow/templates/design/design-point.md`) that supersedes the previous practice of using `reference_note.md` as a design-point starter.

The deletion happens at end of Phase 7 (references dissolution), simultaneously with `docs/references/templates/` directory removal per Q1 §4.3.

## 5. Rejected Alternatives

### Option (a-distributed): Per-pillar `templates/` subdirectories (no centralization)

- **Why rejected**: creates 4+ separate `templates/` directories (`workflow/blueprints/templates/`, `workflow/design/design-points/templates/`, `workflow/design/decisions/templates/`, `workflow/audit/templates/`). Slower discovery and harder to enforce the 7-field metadata schema consistency across pillars.

### Option (b-flat): Single flat `workflow/templates/` (no per-pillar subdirectories)

- **Why rejected**: 9 templates in one flat directory is harder to scan, and the pillar association is lost from the directory structure (would need filename prefixes like `blueprint-task.md` / `design-decision.md` / `audit-vs-shipped.md`). The pillar-subdir layout preserves the structural mapping.

### Option (c-customizable-header): Allow per-document customization of the 7-field metadata header

- **Why rejected**: defeats the purpose of unified metadata. Validator (Phase 4) cannot enforce a header schema if customization is unbounded. The 7-field minimum is the floor; pillar-specific extensions can add fields above the floor (§4.3) without weakening the floor.

### Option (d-optional-templates): Templates are optional / drafters may write from scratch

- **Why rejected**: hard-won cadence lessons get lost when drafters skip templates. The Q-delta-decision pattern (Slice 7C), 3-commit impl pattern (Slice 6 + 7C), N-3 protective preservation lock (Slice 7C), 5-bucket severity (Slice 6 onward) — all encoded in template structure. Voluntary use would re-introduce drift the templates were designed to prevent.

### Option (e-keep-reference-note): Retain `docs/references/templates/reference_note.md` as a 10th template

- **Why rejected**: it is not a workflow-pillar artifact. The 9 designated slots cover all in-scope workflow pillars; external research material does not need a project template since it lives in obsidian (per Q1 §4.3). Adding it would either confuse the inventory (10th template with no consistent pillar) or force creating a new "reference" pillar (out of scope for this slice).

### Option (f-yaml-frontmatter): Use machine-parseable YAML frontmatter (`---\n...\n---`) instead of bullet-list 7-field header

- **Why rejected**: existing repo convention uses bullet-list headers throughout (see all Q1-Q3 decisions, audit doc, CADENCE.md). Switching to YAML frontmatter would require retroactively updating all existing docs. The bullet-list form is already adequate for the validator (regex-parseable) and human-readable.

## 6. Supporting Evidence

- Audit §3.1 A3 — confirms two-location split is a shape conflict needing resolution.
- Audit §3.1 A18 — confirms `docs/references/templates/reference_note.md` is a small-mv-plus-delete item, not a content blocker.
- Audit §3.2 I14 — confirms 7-field unified metadata is genuinely new (no current template enforces it).
- Audit §3.3 D3 — confirms 4 missing templates (decision, design-point, 3 audit sub-types) drive the centralization-and-author motion.
- [docs/blueprints/templates/task_blueprint.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/templates/task_blueprint.md) — existing 71-line template; its structure already aligns with the 8-state blueprint state machine.
- 2026-05-22 design conversation: user explicit lock of "all 9 templates centralized" + 7-field metadata header.
- Slice 6 / 7C 3-commit impl pattern, Q-delta-decision pattern, N-3 lock — examples of cadence lessons that templates need to encode to prevent regression in future slices.

## 7. Consequences

### 7.1 Downstream unblocking

- A3, A18, D3, I14 in audit triage are formally closed.
- Q5 (cadence as primary + AGENTS hierarchy) can codify per-pillar template pointer blocks in the AGENTS.md files it specifies.
- Phase 1.5 (AGENTS authoring) of the implementing blueprint has a concrete deliverable list: write 5 new templates + author 4 AGENTS.md files with template pointer blocks + write `workflow/templates/README.md`.
- Phase 3 (templates mv) of the implementing blueprint has a clear source/target map: 4 files from `docs/blueprints/templates/` → `workflow/templates/blueprints/`.

### 7.2 Required follow-up actions in the implementing blueprint

- **Phase 1.5 (AGENTS + templates authoring)**:
  - Write 5 new templates: `workflow/templates/design/design-point.md`, `workflow/templates/design/decision.md`, `workflow/templates/audit/vs-shipped.md`, `workflow/templates/audit/preflight.md`, `workflow/templates/audit/synthesis.md`. Each includes the 7-field metadata header verbatim + pillar-specific extensions per §4.3.
  - Write `workflow/templates/README.md` codifying the inventory + 7-field schema + customization policy + per-pillar pointer rule from §4.4.
  - Each of `workflow/blueprints/AGENTS.md`, `workflow/design/AGENTS.md`, `workflow/audit/AGENTS.md` includes a "Templates" pointer section per §4.4 example.
- **Phase 3 (templates mv)**: `git mv docs/blueprints/templates/*` → `workflow/templates/blueprints/` (4 files; preserves git history per `feedback_refactor_execution_traps.md`).
- **Phase 4 (validator)** — stratified by directory and provenance:
  - **Error-level 7-field check** for files in active subdirectories: `workflow/blueprints/active/`, `workflow/design/decisions/active/`, `workflow/design/design-points/active/`, `workflow/audit/active/`. Missing fields = error.
  - **Archive subdirectory treatment** is per-pillar to honor §7.4 retrofit boundary:
    - `workflow/blueprints/archive/` — historical archived blueprints (including the 491 if Phase 5 mv'd) are **exempt or warning-only**, not error-level. Historical rationale documents do not retrofit.
    - `workflow/design/decisions/archive/` — error-level (only superseded / withdrawn ADR-states arrive here, all authored under the 7-field schema from Q5 batch flip onward).
    - `workflow/design/design-points/archive/` — error-level (Phase 6 mv retrofits the strengthened authority header per Q2 §4.4, which carries the 7-field block forward).
    - `workflow/audit/archive/` — warning-level for audits migrated from Phase 2; error-level for audits authored post-schema-lock.
  - **Existing DB/view decisions migrated in Phase 2** (the 8 Q1-Q8 files) — severity follows the Phase 2 retrofit choice (per §7.4): error-level if retrofit applied; warning-level if Phase 2 skipped optional retrofit (skip must be acknowledged in blueprint §10).
  - **Per-pillar AGENTS.md "Templates" pointer**: error-level if missing.
  - **Non-template files** (e.g., `README.md`, `AGENTS.md`) are exempt from the 7-field header check; warning-level for missing optional metadata if any.
- **Phase 7 (references dissolution)**: delete `docs/references/templates/reference_note.md` + parent `docs/references/templates/` directory.

### 7.3 Q1-Q5 retrofit obligation

Q1, Q2, Q3 (and Q4 itself) were drafted before Q4 locked the 7-field schema. Their current headers use a 5-6 field convention (Status / Created / Branch / Audit source / Authority / Depends on) that **does not match** the locked 7-field schema (missing `Last Updated`, `Outputs / Downstream`, `Related`).

The Q5 batch flip commit (`proposed` → `adopted` for all 5 Q decisions) is the canonical retrofit moment:

- Add `Last Updated`, `Outputs / Downstream`, `Related` fields to Q1-Q4.
- Recast `Audit source` and `Depends on` as bullets under `Inputs:` (or `Related:` for peer dependencies).
- Q5 itself complies with the 7-field schema from its first draft.

This retrofit is acknowledged here so it cannot be missed during Q5 batch flip. The blueprint §10 closure will record this as a deviation-with-justification entry (drafting Q1-Q3 before Q4 locked the schema was unavoidable given the load-bearing Q-ordering).

### 7.4 Existing artifact retrofit boundary

The Q4 7-field schema applies to **new** documents created post-Phase 2 mv. Existing artifacts that pre-date the schema:

- The 491 archived blueprints in `docs/blueprints/archive/` (Phase 5 conditional mv) — **NOT retrofitted**; cost-prohibitive and unnecessary (historical rationale only).
- The 8 existing DB/view decisions in `docs/decisions/` — header retrofit during Phase 2 mv is **optional**; Phase 2 commit may include a one-line retrofit per file or skip (recorded in blueprint §10).
- The 6 existing design-points in `docs/references/working/design-points/` — header retrofit during Phase 6 mv is **required** (essays are smaller and the strengthened authority header per Q2 §4.4 is itself the retrofit trigger).

### 7.5 Validator schema dependency

The Phase 4 validator depends on this Q4 schema being locked. Validator implementation (out of scope for Q4) will encode the 7-field header presence check + `Status:` whitelist per pillar (using Q2/Q3 state machines).

## 8. Acceptance Criteria

Post-implementing-blueprint, the templates pillar must satisfy:

1. `workflow/templates/{blueprints,design,audit}/` exist and contain exactly the 9 templates listed in §4.2.
2. `workflow/templates/README.md` exists, codifies the 7-field schema verbatim, the customization policy from §4.5, and the per-pillar pointer rule from §4.4.
3. Each of `workflow/blueprints/AGENTS.md`, `workflow/design/AGENTS.md`, `workflow/audit/AGENTS.md` contains a "Templates" pointer section listing the templates that pillar consumes.
4. `docs/blueprints/templates/` directory is deleted (Phase 3 mv outcome).
5. `docs/references/templates/reference_note.md` is deleted (Phase 7 outcome).
6. Q1-Q5 decisions of this slice have been retrofitted to the 7-field schema during the Q5 batch flip commit (planned; not a Q4 acceptance gate but a tracked retrofit obligation per §7.3).
7. Validator (Phase 4) passes:
   - Every new file in `workflow/{blueprints,design/decisions,design/design-points,audit}/{active,archive}/` has the 7-field metadata header verbatim.
   - Each pillar's AGENTS.md has a "Templates" pointer section.
   - Status field uses pillar-specific whitelist (blueprints 8-state per `blueprints/AGENTS.md`; decisions 4-ADR per Q2 §4.5; audits optional 3-state per Q3 §4.6).

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-22 | proposed | Decision drafted | Q4 of 5; centralizes templates and locks unified 7-field metadata schema |
| 2026-05-22 | adopted | Status flip + header retrofit via Q1-Q5 batch commit | Header retrofitted to Q4 §4.3 7-field schema (own schema): added `Last Updated` / `Outputs / Downstream` / `Related`; recast `Audit source` and peer `Depends on` (Q1, Q2, Q3) as `Inputs:` bullets; `Branch` preserved as extension. |

This decision will not be acted upon (no template authoring or `references/templates/` deletion) until **all five Q decisions are closed and the implementing blueprint reaches `Status: scoped`**.
