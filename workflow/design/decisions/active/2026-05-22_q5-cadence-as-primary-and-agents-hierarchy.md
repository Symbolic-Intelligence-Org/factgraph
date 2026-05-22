# Q5 Decision: cadence as primary mode and AGENTS hierarchy

- Status: adopted
- Created: 2026-05-22
- Last Updated: 2026-05-22
- Authority: design constraint; ratifies the CADENCE.md promotion + lock-in statement done in Step 0.1, locks the two-level four-file AGENTS hierarchy, the cross-pillar soft-trigger flow, and the companion-rules deferred-promotion plan
- Inputs:
  - [workflow/audit/active/2026-05-22_workflow-governance-vs-shipped.md](../../../audit/active/2026-05-22_workflow-governance-vs-shipped.md) (§3.1 A11, A12, A13, A14, A15; §3.2 I15; §4 Q5)
  - [workflow/CADENCE.md](../../../CADENCE.md) (Step 0.1 @ `0199ab20`) — already canonical
  - [workflow/AGENTS.md](../../../AGENTS.md) (Step 0.1 @ `0199ab20`) — already contains the verbatim lock-in statement
  - [Q1 decision](./2026-05-22_q1-docs-workflow-split.md) — split scope locks `workflow/AGENTS.md` placement
  - [Q2 decision](./2026-05-22_q2-design-pillar-structure.md) — design pillar AGENTS specification
  - [Q3 decision](./2026-05-22_q3-audit-pillar-structure.md) — audit pillar AGENTS specification
  - [Q4 decision](./2026-05-22_q4-template-centralization.md) — per-pillar template pointer rule + 7-field metadata schema
  - 2026-05-22 design conversation: user-provided verbatim lock-in statement; two-level four-file AGENTS hierarchy proposal; companion-files promotion deferred; cross-pillar flow soft-trigger correction
- Outputs / Downstream:
  - `workflow/design/AGENTS.md` (Phase 1.5; new) — codifies Q2 §4.3-4.7 state machines
  - `workflow/audit/AGENTS.md` (Phase 1.5; new) — codifies Q3 §4.2-4.7 rules
  - `workflow/blueprints/AGENTS.md` (Phase 3 mv; inherited from `docs/blueprints/AGENTS.md`) — adds Q4 §4.4 template pointer block + Q3 paired-vs-standalone cross-reference
  - Implementing blueprint §4 lock table + §8 phase plan
  - Q1-Q5 batch flip commit (post-Q5 closure) — also retrofits Q1-Q4 headers to Q4 §4.3 7-field schema
- Related:
  - 6 companion auto-memory files (deferred canonical promotion; cross-ref in §4.6)
  - `feedback_audit_to_archive_cadence.md` (auto-memory source for `workflow/CADENCE.md`; may persist as Claude session-priming pointer)
- Branch: `v0.2.0-blueprint-workflow-governance-promotion-2026-05-22`
- Depends on: Q1, Q2, Q3, Q4

> **Status note**: this is the final Q decision of this slice's Stage 2. It was adopted in the Q1-Q5 batch commit `ae375ce5` (2026-05-22) per Q4 §7.3. Q5 was authored under the Q4 §4.3 7-field schema from its first draft per user authorization; Q1-Q4 headers were retrofitted to the same schema in the same batch commit. See §9 Decision Record for the transition log.

## 1. Inputs

The 7-field header above lists pointers; this section provides expanded narrative context.

- **Audit triage**: workflow/audit/active/2026-05-22_workflow-governance-vs-shipped.md §3.1 A11 (CADENCE.md canonical) classified `(a) shipped covers via Step 0.1`; A12 (per-pillar AGENTS) `(b) small gap`; A13 (workflow/AGENTS.md umbrella) `(a)`; A14 (6 companion files promotion) `(e) deferred-aligned`; A15 (lock-in statement) `(a)`; §3.2 I15 (cross-pillar soft-trigger) `(c) shape conflict`.
- **Step 0.1 commit `0199ab20`**: scaffolded `workflow/` skeleton + wrote `workflow/CADENCE.md` (517 lines, repo-ized from auto-memory `feedback_audit_to_archive_cadence.md`) + wrote `workflow/AGENTS.md` (93 lines) containing the verbatim user-provided lock-in statement at line 23.
- **Q1-Q4 decisions**: each is a Stage 2 input to this Q5 because Q5 codifies how their state machines and rules will be enforced via the per-pillar AGENTS layer (Phase 1.5 author work).
- **2026-05-22 design conversation**:
  - User verbatim lock-in statement on cadence-as-primary-mode (already in `workflow/AGENTS.md`).
  - User-corrected proposal that I had initially framed cross-pillar flow as a forced linear chain; user clarified it should be soft-trigger with blueprint as the only hard gate.
  - User-locked deferred promotion of 6 companion auto-memory files (this slice is too large to absorb that work; later slices will promote them).

## 2. Scope

This decision locks:

- **Ratification of Step 0.1 promotion**: `workflow/CADENCE.md` is the canonical source of truth for the Audit-to-Archive Cadence; the auto-memory copy may persist as a session-priming pointer but is no longer authoritative.
- **Ratification of the lock-in statement**: the verbatim user-provided text in `workflow/AGENTS.md` line 23 is the project-canonical primary-work-mode declaration.
- **The two-level four-file AGENTS hierarchy**: which directories receive an `AGENTS.md` and which do not, plus their respective scopes.
- **The conflict priority** between `workflow/CADENCE.md`, per-pillar `AGENTS.md`, and `README.md` files (also locked in Step 0.1 `workflow/AGENTS.md` line 32-37; Q5 ratifies and codifies).
- **The cross-pillar soft-trigger flow**: blueprint is the only hard gate; design / audit / decisions are trigger-based prerequisites enumerated in `workflow/CADENCE.md` Scope-and-Applicability.
- **The 6 companion auto-memory files deferred-promotion plan**: identifies the files, their planned canonical target locations, and the slice-level deferral rationale.
- **The Q1-Q5 batch flip commit specification**: scope, mechanics, and retrofit obligations.

## 3. Non-scope

- The actual content of `workflow/design/AGENTS.md` and `workflow/audit/AGENTS.md` (drafted in Phase 1.5 of the implementing blueprint, using Q2 / Q3 / Q4 as specifications).
- Companion-rules promotion execution (each promotion is its own slice; only the promotion plan is locked here).
- Future per-pillar AGENTS for `foundations/`, `templates/`, `memory/`, `working/`, or `heritage/` (Q5 explicitly does NOT add AGENTS to those; rejected alternative below).
- Detailed validator implementation for cross-pillar consistency (covered by Phase 4 of the implementing blueprint, building on Q4 §7.5).
- Auto-memory file deletion policy (the source `feedback_audit_to_archive_cadence.md` and the 6 companion files remain in auto-memory regardless of canonical promotion status; Q5 does not mandate auto-memory housekeeping).

## 4. Decision

### 4.1 Ratification of Step 0.1 promotion

The Step 0.1 commit `0199ab20` created:

- `workflow/CADENCE.md` (517 lines) — repo-ized canonical Audit-to-Archive Cadence; **declared canonical source of truth** with provenance section pointing back to auto-memory `feedback_audit_to_archive_cadence.md`.
- `workflow/AGENTS.md` (93 lines) — umbrella governance with verbatim lock-in statement at line 23.

Q5 **ratifies** both as locked, design-final artifacts. Future cadence updates land directly in `workflow/CADENCE.md` (treated as canonical), not in auto-memory.

The auto-memory copy of `feedback_audit_to_archive_cadence.md` may persist as a Claude session-priming pointer; if it is updated post-Q5, the canonical file takes precedence on any divergence.

### 4.2 Ratification of the lock-in statement

The verbatim text in `workflow/AGENTS.md` line 23:

> Primary work mode for large-scope workflow, architecture, migration, and audit-first implementation work is the Audit-to-Archive Cadence. See `workflow/CADENCE.md`. Tiny local fixes may use the lightweight exception path, but must not bypass blueprint requirements when the task changes workflow, architecture, protocol, or cross-module behavior.

is **locked verbatim**. Future revisions require an explicit new Q-delta-decision per the Q-delta-decision pattern from Slice 7C.

### 4.3 two-level four-file AGENTS hierarchy

The `workflow/` directory uses a **two-level four-file AGENTS layout** (Level 0 umbrella + 3 Level 1 per-pillar AGENTS files):

```
workflow/AGENTS.md                  (Level 0: umbrella; done Step 0.1)
├── workflow/blueprints/AGENTS.md   (Level 1: blueprints state machine; Phase 3 mv from docs/blueprints/AGENTS.md)
├── workflow/design/AGENTS.md       (Level 1: design pillar state machines; new in Phase 1.5)
└── workflow/audit/AGENTS.md        (Level 1: audit pillar rules + sub-types; new in Phase 1.5)
```

**No `AGENTS.md` is created** for: `foundations/`, `templates/`, `memory/`, `working/`, `heritage/`.

Rationale per pillar:

| Pillar | Has AGENTS.md? | Why |
|---|---|---|
| `foundations/` | ❌ | Stable, no state machine; governed by content (architecture_principles.md + module_docs_convention.md themselves) |
| `templates/` | ❌ | Static template inventory; governed by `workflow/templates/README.md` and Q4 §4.3 schema |
| `design/design-points/` + `design/decisions/` | ✓ (joint at `design/AGENTS.md`) | Has 2 state machines (design-point 3-condition archive + decisions ADR 4-state); needs explicit governance |
| `audit/` | ✓ | Has 3 sub-types + trigger conditions + cross-branch visibility convention; needs explicit governance |
| `blueprints/` | ✓ (inherited) | Has 8-state machine; inherited verbatim from `docs/blueprints/AGENTS.md` |
| `memory/` | ❌ | Session continuity content; content cleanup deferred to separate slice; governed by `workflow/memory/README.md` (light) |
| `working/` | ❌ | Temporary, gitignored content; governed by `workflow/working/README.md` (skill convention) |
| `heritage/` | ❌ | Append-only legacy archive; governed by `workflow/heritage/README.md` |

### 4.4 Per-pillar AGENTS content scope

Each Level 1 AGENTS.md codifies:

**`workflow/blueprints/AGENTS.md`** (inherited from `docs/blueprints/AGENTS.md`, Phase 3 mv) — adds:
- A "Templates" pointer section per Q4 §4.4 (referencing `workflow/templates/blueprints/`).
- A cross-reference clarifying paired-blueprint-audit-log vs standalone-audit-record distinction per Q3 §4.2.
- The existing 70-line state machine + reconstructed archive rules + legacy boundary is preserved verbatim.

**`workflow/design/AGENTS.md`** (new, Phase 1.5) — codifies:
- Q2 §4.3 design-point 3-condition archive criteria.
- Q2 §4.4 design-point authority boundary (cannot directly override shipped behavior).
- Q2 §4.5 decisions ADR 4-state machine + allowed transitions + not-allowed transitions.
- Q2 §4.6 directory placement rule (`active/` = `{proposed, adopted}`; `archive/` = `{superseded, withdrawn}`).
- Q2 §4.7 trigger boundary between design-point and decision.
- Q4 §4.4 template pointer block referencing `workflow/templates/design/`.

**`workflow/audit/AGENTS.md`** (new, Phase 1.5) — codifies:
- Q3 §4.2 paired-vs-standalone disambiguation (with explicit cross-reference to `workflow/blueprints/AGENTS.md`).
- Q3 §4.3 standalone sub-types (vs-shipped / preflight / synthesis) with filename conventions.
- Q3 §4.4 preflight trigger conditions (required vs optional cases).
- Q3 §4.5 synthesis trigger conditions.
- Q3 §4.6 active/archive lifecycle tied to consuming slice.
- Q3 §4.7 cross-branch visibility convention (slice-scoped, never auto-merge to master).
- Q3 §4.8 audit file header convention.
- Q4 §4.4 template pointer block referencing `workflow/templates/audit/`.

### 4.5 Cross-pillar soft-trigger flow

The relationship between pillars is **trigger-based, not forced linear chain**. The only hard gate is the blueprint requirement for non-trivial implementation work (per `workflow/CADENCE.md` Scope-and-Applicability section).

**Hard gate**:

- A blueprint (in `workflow/blueprints/active/`) is required for any task that changes workflow, architecture, protocol, public API, cross-module behavior, or operator-facing behavior. Tiny local fixes (per `workflow/CADENCE.md`) may skip.

**Soft triggers** (each may or may not be needed per task scope):

- A **design-point** essay is triggered when the task's conceptual area is not yet articulated. Iterative, may evolve over weeks.
- A **vs-shipped audit** is triggered when the design intent must be compared against shipped runtime (audit-first slices, drift detection).
- A **decision record** is triggered when a specific load-bearing question must be locked before downstream work. Discrete, ADR-style.
- A **post-Q synthesis audit** is triggered per Q3 §4.5 (≥3 Q closures spanning ≥2 buckets).
- A **preflight audit** is triggered per Q3 §4.4 (subtractive removal / cross-module protocol / namespace migration / historical-design compatibility / pre-release verification).

**Typical full chain** (when all triggers fire — e.g., this slice):

```
design-point essay (iterative)
   ↓ (raises load-bearing Qs)
vs-shipped audit (drift triage)
   ↓ (surfaces Q1..QN)
decision records (ADR-style closure)
   ↓ (≥3 closed)
post-Q synthesis (re-bucketing)
   ↓
blueprint (hard gate; only required artifact)
   ↓ (high-risk slice)
preflight audit (Step 4.3)
   ↓
implementation
```

**Typical minimal chain** (small slice):

```
blueprint (hard gate only)
   ↓
implementation
```

The CADENCE Scope-and-Applicability and the per-pillar trigger conditions (Q2 §4.7, Q3 §4.4, Q3 §4.5) together determine which softer artifacts a given slice needs.

### 4.6 Conflict priority

When governance documents disagree:

1. **`workflow/CADENCE.md`** is authoritative for stage transitions, branch naming, verification rituals, and commit discipline.
2. **Per-pillar `AGENTS.md`** (when present) is authoritative for that pillar's state machine, naming convention, and structural rules.
3. **`README.md`** at any level is descriptive, not prescriptive. If a README contradicts AGENTS or CADENCE, the README is the one to update.
4. **Legacy repo-root `/AGENTS.md`** (`docs/`-era pointers): being updated during the implementing blueprint; until that update completes, this `workflow/AGENTS.md` and `workflow/CADENCE.md` take precedence for any workflow concern.

This priority is also stated in `workflow/AGENTS.md` (Step 0.1 line 32-37). Q5 ratifies it as a design-locked rule.

### 4.7 6 companion auto-memory files deferred-promotion plan

The CADENCE.md "Companion rules (currently in auto-memory)" section lists 6 auto-memory files. During the deferral window, those files serve as **supplemental session-behavior inputs** for Claude; they are not the canonical workflow source of truth, but they remain in effect **where the canonical workflow docs are silent**. Their canonical promotion is **deferred to later slices** per this Q5 plan:

| Auto-memory file | Planned canonical target | Proposed promotion slice |
|---|---|---|
| `feedback_preflight_code_audit_required.md` | `workflow/audit/AGENTS.md` (or new section) | Future audit-discipline-promotion slice |
| `feedback_audit_execution_discipline.md` (Rule 1 + Rule 2 bidirectional) | `workflow/audit/AGENTS.md` (Rule 1 already implied; Rule 2 explicit) | Future audit-discipline-promotion slice |
| `feedback_push_master_gate.md` (never auto-push master) | `workflow/AGENTS.md` Sacred-branch section (currently brief; needs expansion) | Future release-discipline-promotion slice |
| `feedback_blueprint_workflow.md` (direct active/ creation, no plan mode) | `workflow/blueprints/AGENTS.md` (extend existing Required Practice) | Future blueprint-discipline-promotion slice |
| `feedback_milestone_branch_refs.md` (milestone refs are branches, not git tags) | `workflow/AGENTS.md` Git ref conventions section (new) | Future release-discipline-promotion slice |
| `feedback_smaller_batch_design_blueprints.md` (single-PR cadence for rule-touching blueprints) | `workflow/blueprints/AGENTS.md` (extend existing State Rules) | Future blueprint-discipline-promotion slice |

**Deferral rationale**: this workflow-governance-promotion slice already covers 9 Q-decision-level locks + 14 documents (1 audit + 5 decisions + 1 synthesis + 1 blueprint + 6 file mvs) + 8 implementation phases. Absorbing 6 additional auto-memory file promotions would over-saturate the slice. Each future slice can promote 1-2 companion files with its own audit + decision + blueprint cycle.

**Until promotion**: the 6 auto-memory files serve as **supplemental session-behavior inputs** that are authoritative **only where the canonical workflow docs are silent**. On any divergence with `workflow/CADENCE.md` or `workflow/AGENTS.md`, the canonical workflow docs win (per §4.6 conflict priority). Both canonical files carry forward-pointer references so future agents know to read the companion files as supplementary inputs, not as the canonical source.

### 4.8 Q1-Q5 batch flip commit specification

Once Q5 closes (after this decision's review approval), a **single batch commit** does the following:

1. Flips `Status:` from `proposed` to `adopted` in all 5 decision files (Q1, Q2, Q3, Q4, Q5).
2. Retrofits Q1-Q4 headers to the Q4 §4.3 7-field schema:
   - Adds `Last Updated`, `Outputs / Downstream`, `Related` fields.
   - Recasts `Audit source:` as a bullet under `Inputs:`.
   - Recasts `Depends on:` as a bullet under `Inputs:` (peer decisions) or `Related:` (cross-references).
   - Preserves `Branch:` as a pillar-specific extension per Q4 §4.3.
3. Adds one row per file to the `## 9. Decision Record` table marking `adopted` state + this batch commit hash + the date.
4. Updates Q5 `Last Updated:` to match the batch commit date.

The batch flip commit **does not** trigger any mv operations or template authoring. Those happen later, in the implementing blueprint's phases. The batch flip is purely a status-and-schema-alignment commit.

Commit message convention: `docs: batch adopt q1-q5 + retrofit headers to 7-field schema`.

## 5. Rejected Alternatives

### Option (a-single-master): Single master `workflow/AGENTS.md` covering all pillars (no per-pillar AGENTS files)

- **Why rejected**: would produce a single ~300-line AGENTS.md mixing 3-4 different state machines (blueprints 8-state + decisions 4-ADR + design-points 3-condition + audit 3-sub-type-lifecycle). Hard to navigate; blast radius of any update affects all pillars. The hierarchical layout matches the existing `docs/blueprints/AGENTS.md` precedent and is consistent with the `/AGENTS.md` per-area convention used elsewhere in the repo (`src/factgraph/AGENTS.md`, etc.).

### Option (b-everywhere-AGENTS): Per-pillar AGENTS.md for foundations / templates / memory / working / heritage as well (8 AGENTS files total)

- **Why rejected**: those pillars have no state machine that warrants AGENTS.md. `foundations/` content is itself governance (architecture principles); `templates/` is static inventory governed by Q4 schema; `memory/` is content-only (session continuity); `working/` is gitignored temp; `heritage/` is append-only legacy. Adding AGENTS.md to these would create empty-ceremony files without governance value.

### Option (c-promote-all-companions-this-slice): Promote all 6 companion auto-memory files to canonical AGENTS sections in this slice

- **Why rejected**: this slice is already large (9 Q-decision locks + 14 documents + 8 implementation phases). Adding 6 more promotion sub-tasks would over-saturate. The deferred-promotion plan in §4.7 explicitly identifies each file's target slice, so the work is not lost — just sequenced.

### Option (d-forced-linear-chain): Cross-pillar flow is a mandatory sequence (design-point → audit → decisions → synthesis → blueprint → preflight → impl)

- **Why rejected**: user explicitly corrected my initial draft framing in the 2026-05-22 conversation. The forced linear chain over-applies to small slices that need only blueprint + impl. Soft-trigger preserves cadence rigor for large slices while avoiding ceremony tax on small slices.

### Option (e-paraphrase-lockin): Use a paraphrased lock-in statement instead of verbatim user-provided text

- **Why rejected**: the user provided the exact wording during the 2026-05-22 conversation with the explicit instruction "Lock-in statement verbatim". Paraphrasing would lose the nuance ("must not bypass blueprint requirements when the task changes workflow, architecture, protocol, or cross-module behavior" is calibrated to prevent both over-application and under-application of the cadence; rewording risks drift).

### Option (f-canonical-deletes-automemory): Delete auto-memory `feedback_audit_to_archive_cadence.md` once `workflow/CADENCE.md` is canonical

- **Why rejected**: auto-memory is Claude session-priming infrastructure, not subject to the workflow/ governance. Auto-memory may continue to point at the canonical file (as a pointer or short summary) without conflict. Forcing deletion would risk a Claude session arriving with empty cadence priming if the canonical file weren't yet loaded.

### Option (g-batch-flip-skip-retrofit): Q1-Q5 batch flip only flips Status; does not retrofit headers to 7-field schema

- **Why rejected**: Q4 §7.3 explicitly identifies the batch flip as the canonical retrofit moment. Skipping retrofit would leave Q1-Q4 perpetually out of sync with the schema they themselves rely on for downstream validator enforcement. The batch flip is the cleanest moment because all 5 are touched in the same commit anyway.

## 6. Supporting Evidence

- Audit §3.1 A11 — Q5 explicitly ratifies the Step 0.1 promotion.
- Audit §3.1 A12, A13 — per-pillar + umbrella AGENTS layout.
- Audit §3.1 A14 — 6 companion files deferred.
- Audit §3.1 A15 — lock-in statement.
- Audit §3.2 I15 — cross-pillar soft-trigger flow.
- `workflow/CADENCE.md` (Step 0.1) — already contains the cadence in canonical form.
- `workflow/AGENTS.md` (Step 0.1) line 23 — already contains the verbatim lock-in statement.
- Q4 §4.4 + §7.3 — template pointer rule + Q1-Q5 retrofit obligation that this Q5 inherits as a downstream consequence.
- 2026-05-22 design conversation: user-verbatim lock-in + user-corrected soft-trigger framing + user-deferred companion-files promotion.
- `docs/blueprints/AGENTS.md` (current, 70 lines) — proven blueprint state machine that inherits via Phase 3 mv with minimal extension (Q4 §4.4 pointer + Q3 §4.2 cross-reference).
- `/AGENTS.md` (repo root) — current 51-line pointer file that needs path update from `docs/` to `workflow/` during the implementing blueprint's root-update step (Q1 §4.4).

## 7. Consequences

### 7.1 Downstream unblocking

- A11, A12, A13, A14, A15, I15 in audit triage are formally closed.
- The Q1-Q5 batch flip can proceed (per §4.8 spec) immediately after this decision's review approval.
- Phase 1.5 (AGENTS authoring) of the implementing blueprint has concrete content specifications for both new AGENTS files (per §4.4) and the extension scope for `workflow/blueprints/AGENTS.md` (Q4 §4.4 + Q3 §4.2 cross-reference).
- Phase 0.3 synthesis writing can proceed using the Q1-Q5 closure state.

### 7.2 Required follow-up actions in the implementing blueprint

- **Q1-Q5 batch flip commit** (immediately post-Q5 closure): scope per §4.8.
- **Synthesis writing** (Step 0.3): incorporates the closed-Q state into the slice's drift re-bucketing.
- **Blueprint draft** (Step 0.4): §4 lock table cites Q1-Q5; §8 phase plan implements Phase 1.5 AGENTS authoring + Phase 3 blueprint mv + Phase 4 validator + companion deferral acknowledgment.
- **Phase 1.5 (AGENTS authoring)**: write the two new AGENTS files per §4.4 content specifications.
- **Phase 3 (blueprints mv)**: `git mv docs/blueprints/AGENTS.md` → `workflow/blueprints/AGENTS.md`, then extend in-place with Q4 §4.4 template pointer section + Q3 §4.2 paired-vs-standalone cross-reference.
- **Phase 4 (validator)**: per Q4 §7.2 stratified rules; additionally check that each Level 1 AGENTS.md exists at the expected path.

### 7.3 Companion-files state during deferral

Between this slice closure and the future companion-promotion slices:

- The 6 auto-memory companion files serve as **supplemental session-behavior inputs**, authoritative **only where the canonical workflow docs are silent**. On any divergence with `workflow/CADENCE.md` or `workflow/AGENTS.md`, the canonical workflow docs win (per §4.6).
- `workflow/CADENCE.md` and `workflow/AGENTS.md` already contain pointer references; no additional sync action is required this slice.
- Future Claude sessions following the cadence will read both the canonical `workflow/CADENCE.md` and the auto-memory companion files; if these two diverge during the deferral window, the canonical file wins (per §4.6 conflict priority).

### 7.4 Q1-Q5 retrofit obligation visibility

The batch flip commit message (per §4.8 convention) must explicitly mention both actions:
- `proposed → adopted` status flip for all 5 files.
- Header retrofit to 7-field schema for Q1-Q4 (Q5 already complies).

The implementing blueprint §10 closure will record the retrofit as a deviation-with-justification per the "Q1-Q5 drafted before Q4 locked the schema" sequencing logic.

### 7.5 No retroactive enforcement on legacy artifacts

The two-level four-file AGENTS hierarchy and the cross-pillar soft-trigger flow apply to **new and active workflow content** post-this slice. Pre-existing artifacts (491 archived blueprints, 8 DB/view Q1-Q8 decisions, etc.) are not retroactively re-evaluated against §4.4 content specifications or §4.5 trigger conditions.

## 8. Acceptance Criteria

Post-implementing-blueprint, the AGENTS hierarchy must satisfy:

1. `workflow/AGENTS.md` exists with the verbatim user-provided lock-in statement (already true post-Step 0.1; preserved through Phase 1.5 edits).
2. `workflow/blueprints/AGENTS.md` exists with:
   - The 70-line existing state machine inherited from `docs/blueprints/AGENTS.md` (Phase 3 mv).
   - A new "Templates" pointer section per Q4 §4.4.
   - A new paired-vs-standalone cross-reference to `workflow/audit/AGENTS.md` per Q3 §4.2.
3. `workflow/design/AGENTS.md` exists and codifies Q2 §4.3-4.7 verbatim or with semantic equivalence, plus the Q4 §4.4 template pointer section.
4. `workflow/audit/AGENTS.md` exists and codifies Q3 §4.2-4.8 verbatim or with semantic equivalence, plus the Q4 §4.4 template pointer section.
5. No `AGENTS.md` exists at `workflow/foundations/`, `workflow/templates/`, `workflow/memory/`, `workflow/working/`, or `workflow/heritage/` (per §4.3 rationale).
6. Q1-Q5 all have `Status: adopted` post-batch-flip, with Q1-Q4 also retrofitted to the 7-field schema.
7. Validator (Phase 4) passes:
   - The 3 expected Level 1 AGENTS files exist: `workflow/blueprints/AGENTS.md`, `workflow/design/AGENTS.md`, `workflow/audit/AGENTS.md`. No `AGENTS.md` exists in `foundations/`, `templates/`, `memory/`, `working/`, or `heritage/` (per §4.3).
   - Each `AGENTS.md` includes a "Templates" pointer section (per Q4 §4.4 + Phase 4 check).
   - Lock-in statement in `workflow/AGENTS.md` matches verbatim text from §4.2 (string match).
8. `workflow/CADENCE.md` provenance line still points at the auto-memory source; no deletion of auto-memory `feedback_audit_to_archive_cadence.md` is gated by this slice.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-22 | proposed | Decision drafted | Q5 of 5; first decision authored under the Q4 §4.3 7-field schema (used from initial draft per user authorization) |
| 2026-05-22 | adopted | Status flip via Q1-Q5 batch commit | Q5 already 7-field compliant from first draft; this commit only flips `Status: proposed → adopted` and adds this Decision Record row. Q1-Q4 retrofit to 7-field schema performed in the same batch commit per §4.8. |

This decision will not trigger AGENTS authoring until the implementing blueprint reaches `Status: scoped`.
