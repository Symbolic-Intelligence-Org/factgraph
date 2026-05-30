# Slice 4 — Docs Polish for Form I / Identity-as-Claim / API Namespace

- Status: draft
- Created: 2026-05-30
- Last Updated: 2026-05-30
- Slice: 4 of identity/API alignment ladder
- Class: M(docs-only, broad surface; no runtime changes)
- Related Modules:
  - `src/factgraph/sdk/docs/`
  - `docs/official/kernel/quickstart/`
  - `examples/`
  - `src/factgraph/application/docs/`
  - `src/factgraph/authoring/docs/`
  - `src/factgraph/core/docs/`
  - `workflow/design/design-points/active/`
- Related Docs:
  - Standalone audit: `workflow/audit/active/2026-05-30_slice-4-docs-polish-vs-shipped.md` @ `1012c6e4` on branch `v0.2.0-slice-4-docs-polish-audit-2026-05-30`
  - `workflow/blueprints/archive/2026-05-29_slice-1-form-i-schema.md` — Form I baseline
  - `workflow/blueprints/archive/2026-05-29_slice-2-identity-claim-emission.md` — Identity-as-Claim baseline
  - `workflow/blueprints/archive/2026-05-30_slice-3a-api-namespace.md` — API namespace baseline
  - `workflow/audit/active/2026-05-30_slice-2-shipped-alignment-audit.md` @ `7c87f68b` — post-close Slice 2 verification
- Audit Log:
  - [2026-05-30_slice-4-docs-polish.audit.md](./2026-05-30_slice-4-docs-polish.audit.md)
- Branch: `v0.2.0-blueprint-slice-4-docs-polish-2026-05-30`
- Fork point: `722595ba`(Slice 3a archive head plus N1 ingest docstring fix)

## 1. Problem

Slice 1, Slice 2, and Slice 3a changed the user-facing SDK surface substantially:

- Form I removed `Identity(primary_key=...)`, `default`, and `default_factory` from Identity declarations.
- Identity-as-Claim introduced INV-7c protected Identity Claims, `:exists` transitional guard, and shadow-store legacy positioning.
- Slice 3a removed `fg.read.*`, `fg.write.*`, and all flat top-level shortcuts; it introduced `fg.entities.*`, `fg.fields.*`, `fg.assertions.*`, unified `AssertionView`, canonical `_meta` filtering, and `fg.schema.register/extend/apply`.

Slice 3a Step 12 updated the load-bearing docs, but the wider docs corpus still contains stale public examples:

- public quickstarts still show `fg.read.*` / `fg.write.*`, `Identity(primary_key=True)`, `FieldAssertions`, `.version(v)`, flat assertion `where(source=...)`, and `fg.schema.add(...)`;
- active examples, especially `examples/05_sdk_assertion_views.ipynb`, still demonstrate removed APIs;
- non-load-bearing SDK docs and module docs have isolated legacy references;
- active design-points contain both intentional historical text and current-status text that now need careful separation.

Slice 4 is a docs-only cleanup slice to align the wider public/reference documentation with the shipped Slice 1/2/3a surface.

## 2. Goals

- G1 Update public quickstarts that still describe removed read/write/schema/assertion surfaces.
- G2 Update examples that are part of the active example set, without overwriting dirty notebook baseline.
- G3 Update non-load-bearing SDK docs that still contain old API references.
- G4 Update selected module docs with current schema/namespace/filter wording.
- G5 Update active design-points only where current-status / cross-reference / landed-status text is stale.
- G6 Preserve historical rationale sections and archived material unless explicitly scoped.
- G7 Keep this slice docs-only: no runtime code, no tests, no schema/protocol changes.
- G8 Preserve Q-PR1 sacred paths, sacred branches, and existing dirty baseline.

## 3. Non-goals

- N1 Runtime API changes of any kind.
- N2 Test-suite migration; Slice 3a Step 11 already migrated the target tests.
- N3 Rewriting archived design-points under `workflow/design/design-points/archive/`.
- N4 Automatic migration of `examples/archive/*`.
- N5 Automatic overwriting of dirty notebooks.
- N6 New ADR or Q-resolution. Slice 4 is docs drift cleanup against already-shipped APIs.
- N7 Master merge, PR creation, or push. Those remain user-authorized operations.
- N8 Memory consolidation updates.

## 4. Current Context

### 4.1 Baseline

- Current blueprint branch forks from `722595ba`, which includes:
  - Slice 3a archive head `33090323`;
  - N1 docstring fix `722595ba`.
- Standalone Stage 1 audit is on separate branch `v0.2.0-slice-4-docs-polish-audit-2026-05-30` at `1012c6e4`.
- The audit intentionally used `git grep` against tracked HEAD content to avoid treating dirty notebooks as shipped content.

### 4.2 Stage 1 Audit Findings

The Stage 1 audit produced 15 findings:

| Bucket | Findings |
|---|---|
| Required | D1-D7 |
| Recommended | D8-D10 |
| Verified | D13-D14 |
| Scoped-detail | D11-D12 |
| Abandonment / out-of-scope | D15 |

### 4.3 Shipped Target Surface

Slice 4 docs must describe this surface as current truth:

| Area | Current surface |
|---|---|
| Form I schema | `Identity()` / `Field()`; no `primary_key`, no Identity defaults |
| Entities | `fg.entities.create/get/where/match/ref/exists/delete/edit` |
| Fields | `fg.fields.set/add/retract/delete/get` |
| Assertions | `fg.assertions.active/all/where/by_id/by_ids/retract` |
| Assertion views | `AssertionView`; `FieldAssertions` and `AssertionNamespace` removed |
| Assertion filtering | `where(value=..., value_tag=..., _meta={...})` |
| Version filtering | `.where(_meta={"version": v})`; no `.version(v)` |
| Schema mutation | `fg.schema.register`, `fg.schema.extend`, `fg.schema.apply`; no `fg.schema.add` |
| Identity protection | Identity retract -> `INV_7C_IDENTITY_PROTECTED`; `:exists` retract -> `EXISTENCE_CLAIM_TRANSITIONAL_GUARD` |

### 4.4 Dirty Baseline

Known dirty baseline must be preserved:

- `docs/references/working/design-points/readme.md`
- `examples/01_sdk_check_diagnose.ipynb`
- `examples/02_overlay_why_not_frontier.ipynb`
- `examples/archive/01_sdk_basics.ipynb`
- deleted `workflow/working/.gitkeep`
- untracked `docs/references/working/change-requests-2026-05-27/`
- untracked `rainbird-ai sdk code/`

## 5. Proposed Shape

### 5.1 Public Quickstarts

Heavy rewrite targets:

- `docs/official/kernel/quickstart/first-factgraph.md`
- `docs/official/kernel/quickstart/read-write.md`
- `docs/official/kernel/quickstart/assertions.md`
- `docs/official/kernel/quickstart/schema.md`

These files contain dense stale walkthrough flow and should be updated section-by-section rather than mechanically substituted.

Mechanical / local migration targets:

- `docs/official/kernel/quickstart/namespace-map.md`
- `docs/official/kernel/quickstart/evidence.md`
- `docs/official/kernel/quickstart/database.md`
- `docs/official/kernel/quickstart/persistence.md`
- `docs/official/kernel/quickstart/rules-and-inferences.md`
- `docs/official/kernel/quickstart/semantics.md`

### 5.2 Examples

Active examples are in scope only when they are not dirty or when the user explicitly authorizes per-notebook changes.

Primary non-dirty target:

- `examples/05_sdk_assertion_views.ipynb`

Other active tracked targets from audit:

- `examples/03_proofframe_rule_overlays.ipynb`
- `examples/04_round_persistence_diff.ipynb`
- `examples/round_story_full_demo.py`

Dirty notebook targets are governed by SF3 and may not be edited automatically:

- `examples/01_sdk_check_diagnose.ipynb`
- `examples/02_overlay_why_not_frontier.ipynb`

### 5.3 Non-Load-Bearing SDK Docs

Update isolated stale references in:

- `src/factgraph/sdk/docs/README.md`
- `src/factgraph/sdk/docs/01_concepts.en.md`
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
- `src/factgraph/sdk/docs/07_walker_and_advanced.en.md`

`src/factgraph/sdk/docs/README.md` was added by Step 4.2 review after the Stage 1 audit missed live `fg.read.*` / `fg.write.*` examples there. Avoid broad rewrites of load-bearing docs already updated in Slice 3a unless a local cross-reference is plainly stale.

### 5.4 Module Docs

Update grep-positive current-truth wording in:

- `src/factgraph/application/docs/01_overview_en.md`
- `src/factgraph/application/docs/README.md`
- `src/factgraph/authoring/docs/01_overview.md`
- `src/factgraph/core/docs/01_architecture.en.md`

### 5.5 Active Design-Points

Update only current-status / cross-reference / landed-status text in:

- `workflow/design/design-points/active/ledger-schema-specification.zh.md`
- `workflow/design/design-points/active/append-only-ledger-evaluation.zh.md`
- `workflow/design/design-points/active/identity-mechanism-redesign.zh.md`
- `workflow/design/design-points/active/explanation-completion-roadmap.zh.md`

Historical problem statements, source-grep baselines, and rationale sections are not rewritten unless they explicitly claim to be current implementation truth. For `explanation-completion-roadmap.zh.md`, the scope is limited to current API surface references such as `fg.read.match(...)` -> `fg.entities.match(...)`; the deferred-roadmap intent remains unchanged.

### 5.6 Final Grep Gate

For in-scope current docs/examples, final grep should not show current-API uses of:

- `fg.read.*`
- `fg.write.*`
- `Identity(primary_key=True)`
- `FieldAssertions`
- `AssertionNamespace`
- `.version(v)`
- flat assertion `where(source=..., trace_id=..., version=..., meta=...)`
- `fg.schema.add(...)`

Historical quoted migration tables, removed-surface narrative notes, and explicit "removed in Slice X" deprecation markers may keep old names only if clearly marked as historical or removed-surface mapping.

## 6. Boundaries And Invariants

### 6.1 Scope Freeze

| SF | Lock | Source |
|---|---|---|
| SF1 | D1-D10 are in scope: Required D1-D7 plus Recommended D8-D10. | Stage 1 audit + reviewer/Codex lock |
| SF2 | D11 historical sections in `identity-mechanism-redesign.zh.md` are not rewritten; only current-status / cross-reference / landed-status sections may change. | OQ3 |
| SF3 | Dirty notebooks are not auto-overwritten. Each dirty notebook requires per-file diff review and explicit user authorization before editing. | OQ2 |
| SF4 | Archived design-points and `examples/archive/*` are out of scope unless an active doc links to them and the blueprint is amended. | OQ1 + D15 |
| SF5 | No Stage 2 ADR / Q decision is needed; this is docs drift cleanup only. | OQ5 |
| SF6 | Hybrid implementation strategy: four heavy quickstarts are rewritten; other docs get mechanical/local migration. | OQ4 |
| SF7 | Final grep gate must enforce the deletion targets in §5.6, with a historical-quote carve-out only when explicitly labeled. | Audit §7 |
| SF8 | Q-PR1 sacred paths remain 0 diff. | meta-ADR §4.4 + Slice 1/2/3a inheritance |
| SF9 | Sacred branches and dirty baseline remain untouched. | Slice 1/2/3a inheritance |
| SF10 | Implementation follows the six-phase audit order expanded into commit-boundary steps in §8. | Stage 1 audit §7 |

### 6.2 Compatibility Constraints

- The docs must reflect shipped behavior, not proposed future behavior.
- `examples/archive/*` is not a current tutorial surface unless explicitly selected.
- Public quickstarts should be runnable in principle, but this slice is documentation polish, not a runtime-test expansion slice.
- Notebook edits must preserve existing user dirty cells and metadata unless explicitly authorized.

### 6.3 Q-PR1 Carve-Out

This slice is docs-only. It must not touch:

- `src/factgraph/core/evidence/write_protocol.py`
- `src/factgraph/core/store/ledger.py`
- `src/factgraph/core/store/_builders.py`
- `src/factgraph/adapters/pyreason/`
- `src/factgraph/core/derivation/accept.py`

### 6.4 Sacred Branches

- local `master` and origin `master` remain `562c74195df43e933bed92a3ff25de94dd8ce666`.
- `v0.1-oss-prep` remains untouched.
- Push, PR creation, master merge, reset, or destructive git remain user-authorized operations.

### 6.5 Per-Commit Ritual

Each implementation commit must verify branch, sacred master, Q-PR1 0 diff, dirty baseline preservation, and `git diff --check`.

## 7. Acceptance

### 7.1 Public Quickstarts

- [ ] Heavy rewrite quickstarts use canonical namespace APIs.
- [ ] Mechanical migration quickstarts have no current stale `fg.read.*` / `fg.write.*` / `fg.schema.add` / `Identity(primary_key=True)` references.
- [ ] Assertion quickstart documents `AssertionView`, canonical `_meta`, no `.version(v)`, and no `FieldAssertions`.
- [ ] Schema quickstart documents `register/extend/apply` and Form I Identity semantics.

### 7.2 Examples

- [ ] In-scope active examples use Form I and canonical namespace APIs.
- [ ] `examples/05_sdk_assertion_views.ipynb` demonstrates `AssertionView` and `_meta`.
- [ ] Dirty notebooks are either untouched or explicitly approved per-file before edit.
- [ ] `examples/archive/*` is untouched unless blueprint amended.

### 7.3 SDK / Module Docs

- [ ] `README.md`, `01_concepts.en.md`, `03_rules_and_inferences.en.md`, and `07_walker_and_advanced.en.md` no longer present removed APIs as current truth.
- [ ] Application / authoring / core docs no longer refer to `fg.schema.add` or flat meta filters as current truth.

### 7.4 Active Design-Points

- [ ] Current-status / landed-status text is aligned with Slice 1/2/3a.
- [ ] `explanation-completion-roadmap.zh.md` current API references use `fg.entities.match` where they describe the shipped namespace surface.
- [ ] Historical rationale sections are preserved unless explicitly marked current and stale.

### 7.5 Final Checks

- [ ] Final grep gate in §5.6 passes for in-scope current docs/examples.
- [ ] Q-PR1 sacred paths 0 diff.
- [ ] examples committed diff respects dirty-notebook guard.
- [ ] sacred master unchanged.
- [ ] dirty baseline preserved.
- [ ] `git diff --check` clean.
- [ ] `compileall` clean if any executable docs helper was touched; otherwise not required.

## 8. Implementation Plan

**Step 0 — Pre-implementation grep gate**

- Re-run Stage 1 audit grep commands from the implementation branch.
- Verify no new in-scope drift since audit `1012c6e4`.
- Confirm dirty notebook baseline before any docs edits.

**Step 1 — Public quickstart heavy rewrite Phase 1**

- Update `first-factgraph.md`.
- Update `read-write.md`.
- Keep examples minimal and canonical.

**Step 2 — Public quickstart heavy rewrite Phase 2**

- Update `assertions.md`.
- Update `schema.md`.
- Focus on `AssertionView`, `_meta`, Form I, and schema three-way split.

**Step 3 — Public quickstart mechanical migration**

- Update `namespace-map.md`, `evidence.md`, `database.md`, `persistence.md`, `rules-and-inferences.md`, and `semantics.md`.
- Prefer targeted substitutions and local sentence edits.

**Step 4 — Active examples migration(non-dirty only)**

- Update `examples/05_sdk_assertion_views.ipynb`.
- Update `examples/03_proofframe_rule_overlays.ipynb`.
- Update `examples/04_round_persistence_diff.ipynb`.
- Update `examples/round_story_full_demo.py`.

**Step 5 — Dirty notebook decision point**

- Inspect `examples/01_sdk_check_diagnose.ipynb` and `examples/02_overlay_why_not_frontier.ipynb`.
- Default: record as intentionally untouched in §10 unless the user explicitly authorizes per-file edits during Step 5.

**Step 6 — Non-load-bearing SDK docs**

- Update `src/factgraph/sdk/docs/README.md`.
- Update `src/factgraph/sdk/docs/01_concepts.en.md`.
- Update `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`.
- Update `src/factgraph/sdk/docs/07_walker_and_advanced.en.md`.

**Step 7 — Module docs**

- Update `src/factgraph/application/docs/01_overview_en.md`.
- Update `src/factgraph/application/docs/README.md`.
- Update `src/factgraph/authoring/docs/01_overview.md`.
- Update `src/factgraph/core/docs/01_architecture.en.md`.

**Step 8 — Active design-points current-status migration**

- Update `ledger-schema-specification.zh.md`.
- Update `append-only-ledger-evaluation.zh.md`.
- Update current API references in `explanation-completion-roadmap.zh.md`.
- Update current-status / cross-ref rows in `identity-mechanism-redesign.zh.md` only if needed.

**Step 9 — Final grep gate + close**

- Run final grep gate.
- Fill §10 Outcome / Deviations.
- Flip status `implementing` -> `implemented`.
- Prepare archive cadence after reviewer pass.

## 9. Docs To Update

In-scope docs are listed in §5. New docs are not introduced.

`docs/README.md` update is not expected unless implementation introduces a new persistent docs entry, which is a non-goal.

## 10. Outcome / Deviations

To be filled at close:

### 10.1 Final Landing Result

TBD.

### 10.2 Deviations And Amendments

TBD.

### 10.3 Scope Freeze Verification

TBD.

### 10.4 Final Grep Gate

TBD.

### 10.5 Dirty Notebook Handling

TBD.

### 10.6 Q-PR1 / Sacred Branch Preservation

TBD.

### 10.7 Docs Landed

TBD.

### 10.8 Carry-Forward Dependencies

TBD.

### 10.9 Archive Cadence

TBD.
