# Slice 4 — Docs Polish for Form I / Identity-as-Claim / API Namespace

- Status: implemented
- Created: 2026-05-30
- Last Updated: 2026-05-30(implemented after Step 9 final grep gate + §10 Outcome)
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

- public quickstarts still show `fg.read.*` / `fg.write.*`, `Identity(primary_key=...)`, `FieldAssertions`, `.version(v)`, flat assertion `where(source=...)`, and `fg.schema.add(...)`;
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
- `Identity(...primary_key...)`
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

- [x] Heavy rewrite quickstarts use canonical namespace APIs.
- [x] Mechanical migration quickstarts have no current stale `fg.read.*` / `fg.write.*` / `fg.schema.add` / `Identity(...primary_key...)` references.
- [x] Assertion quickstart documents `AssertionView`, canonical `_meta`, no `.version(v)`, and no `FieldAssertions`.
- [x] Schema quickstart documents `register/extend/apply` and Form I Identity semantics.

### 7.2 Examples

- [x] In-scope active examples use Form I and canonical namespace APIs.
- [x] `examples/05_sdk_assertion_views.ipynb` demonstrates `AssertionView` and `_meta`.
- [x] Dirty notebooks are either untouched or explicitly approved per-file before edit.
- [x] `examples/archive/*` is untouched unless blueprint amended.

### 7.3 SDK / Module Docs

- [x] `README.md`, `01_concepts.en.md`, `03_rules_and_inferences.en.md`, and `07_walker_and_advanced.en.md` no longer present removed APIs as current truth.
- [x] Application / authoring / core docs no longer refer to `fg.schema.add` or flat meta filters as current truth.

### 7.4 Active Design-Points

- [x] Current-status / landed-status text is aligned with Slice 1/2/3a.
- [x] `explanation-completion-roadmap.zh.md` current API references use `fg.entities.match` where they describe the shipped namespace surface.
- [x] Historical rationale sections are preserved unless explicitly marked current and stale.

### 7.5 Final Checks

- [x] Final grep gate in §5.6 passes for in-scope current docs/examples.
- [x] Q-PR1 sacred paths 0 diff.
- [x] examples committed diff respects dirty-notebook guard.
- [x] sacred master unchanged.
- [x] dirty baseline preserved.
- [x] `git diff --check` clean.
- [x] `compileall` clean if any executable docs helper was touched; otherwise not required.

## 8. Implementation Plan

**Step 0 — Pre-implementation grep gate**

- Re-run Stage 1 audit grep commands from the implementation branch.
- Also run Step 4.2 added-target checks for `src/factgraph/sdk/docs/README.md` and `workflow/design/design-points/active/explanation-completion-roadmap.zh.md`.
- Use the broad Form I removed-argument pattern `Identity\([^)]*primary_key`, not only the historical `Identity(primary_key=True)` spelling.
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
- Use `Identity\([^)]*primary_key` for Form I legacy detection.
- Fill §10 Outcome / Deviations.
- Flip status `implementing` -> `implemented`.
- Prepare archive cadence after reviewer pass.

## 9. Docs To Update

In-scope docs are listed in §5. New docs are not introduced.

`docs/README.md` update is not expected unless implementation introduces a new persistent docs entry, which is a non-goal.

## 10. Outcome / Deviations

### 10.1 Final Landing Result

Slice 4 landed as a docs-only implementation branch `v0.2.0-impl-slice-4-docs-polish-2026-05-30`, forked from scoped anchor `a62e9a2d`.

Implementation lineage:

| Step | Commit | Result |
|---|---|---|
| Step 1 | `3dc8d8aa` | Rewrote `first-factgraph.md` and `read-write.md`; both complete examples smoke-tested. |
| Step 2 | `df4f605d` | Rewrote `assertions.md` and `schema.md`; both complete examples smoke-tested. |
| Step 3 | `565ae6f1` | Migrated six remaining public quickstarts; four complete examples smoke-tested. |
| Step 4 | `2ec2f51f` | Migrated four active non-dirty examples; three notebooks executed with `nbconvert`, and the Python example ran end-to-end. |
| Step 5 | `f036734f` | Recorded dirty-notebook decision point; no notebook edits. |
| Step 6 | `7b1ca24e` | Migrated non-load-bearing SDK docs, including the Step 4.2-added `sdk/docs/README.md`. |
| Step 7 | `b3484472` | Migrated application / authoring / core module docs. |
| Step 8 | `445a28c3` | Migrated current-status active design-point text while preserving historical sections. |
| Step 9 | this commit | Ran final grep gate, filled §10, and marked the blueprint `implemented`. |

Net implementation diff through Step 8: 26 docs/example/design files plus this blueprint/audit close record; runtime source and tests were untouched.

### 10.2 Deviations And Amendments

- Step 4.2 reviewer amend added `src/factgraph/sdk/docs/README.md` and `workflow/design/design-points/active/explanation-completion-roadmap.zh.md` after the Stage 1 audit missed live current-surface references.
- Step 4.3 preflight amend PF-R1 broadened Form I detection from exact `Identity(primary_key=True)` to `Identity\([^)]*primary_key`.
- Step 7 performed one in-scope bonus cleanup in `application/docs/01_overview_en.md`: stale `fg.what_if.*` / `fg.read.get` examples were replaced with current `fg.entities.get`, `fg.eval.evaluate`, and `fg.audit.diff_proof_frames` wording.
- Step 8 rewrote `ledger-schema-specification.zh.md` §8.6 from the old assertion-level `delete` alias framing to the shipped `fg.assertions.retract` framing plus a field-level delete note.
- No runtime, test, Q-PR1, archive-example, or dirty-notebook scope deviation occurred.

### 10.3 Scope Freeze Verification

| SF | Close verification |
|---|---|
| SF1 | D1-D10 landed: public quickstarts, active non-dirty examples, SDK docs, module docs, and current-status design-points. |
| SF2 | `identity-mechanism-redesign.zh.md` historical/problem/source-grep sections were preserved; only current carry-forward/status checklist rows changed. |
| SF3 | Dirty notebooks `01_sdk_check_diagnose.ipynb` and `02_overlay_why_not_frontier.ipynb` were not edited. |
| SF4 | `examples/archive/*` and archived design-points were not edited. |
| SF5 | No ADR / Q-resolution work was introduced. |
| SF6 | Hybrid strategy was followed: four dense quickstarts were rewritten, lower-density files received local migrations. |
| SF7 | Final grep gate completed; remaining hits are classified carve-outs in §10.4. |
| SF8 | Q-PR1 sacred paths remain 0 diff against `722595ba..HEAD`. |
| SF9 | Sacred master and dirty baseline preserved. |
| SF10 | Implementation followed the audit phase order as Step 0-9. |

### 10.4 Final Grep Gate

Final grep commands covered public quickstarts, active non-dirty examples, SDK docs, module docs, and active design-points:

- `Identity\([^)]*primary_key`
- `fg\.read\.|fg\.write\.|FieldAssertions|AssertionNamespace|\.version\(|fg\.schema\.add|Field\([^)]*cardinality`
- `where\([^_)]*meta=|where\([^)]*(source=|trace_id=|version=)`
- `ReadPolicy|kernel\.sdk|kernel\.application|from kernel\.`

Current-surface docs/examples are clean. Remaining hits are explicit carve-outs:

| Location | Classification |
|---|---|
| `src/factgraph/sdk/docs/04_api_surface.en.md` migration examples and removed-surface notes | Allowed historical / removed-surface narrative. |
| `workflow/design/design-points/active/identity-mechanism-redesign.zh.md` | SF2-preserved historical problem statements, option tables, migration maps, and shipped-status rows naming removed surfaces as past state. |
| `workflow/design/design-points/active/ledger-schema-specification.zh.md:916` | Historical 2026-05-29 consistency-pass changelog entry. |

`ReadPolicy` / `kernel.*` bonus grep returned no hits.

### 10.5 Dirty Notebook Handling

Step 5 used the SF3 default path: active dirty notebooks were intentionally untouched because no per-file user authorization was requested during Slice 4 implementation. `examples/archive/01_sdk_basics.ipynb` remained out of scope under SF4.

Committed diff against `722595ba..HEAD` for:

- `examples/01_sdk_check_diagnose.ipynb`
- `examples/02_overlay_why_not_frontier.ipynb`
- `examples/archive/01_sdk_basics.ipynb`
- `examples/archive/`

is empty.

### 10.6 Q-PR1 / Sacred Branch Preservation

Q-PR1 sacred paths remain 0 diff against `722595ba..HEAD`:

- `src/factgraph/core/evidence/write_protocol.py`
- `src/factgraph/core/store/ledger.py`
- `src/factgraph/core/store/_builders.py`
- `src/factgraph/adapters/pyreason/`
- `src/factgraph/core/derivation/accept.py`

Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`. The existing dirty baseline remains unchanged.

### 10.7 Docs Landed

| Area | Files |
|---|---|
| Public quickstarts | `assertions.md`, `database.md`, `evidence.md`, `first-factgraph.md`, `namespace-map.md`, `persistence.md`, `read-write.md`, `rules-and-inferences.md`, `schema.md`, `semantics.md` |
| Active examples | `examples/03_proofframe_rule_overlays.ipynb`, `examples/04_round_persistence_diff.ipynb`, `examples/05_sdk_assertion_views.ipynb`, `examples/round_story_full_demo.py` |
| Non-load-bearing SDK docs | `sdk/docs/README.md`, `01_concepts.en.md`, `03_rules_and_inferences.en.md`, `07_walker_and_advanced.en.md` |
| Module docs | `application/docs/01_overview_en.md`, `application/docs/README.md`, `authoring/docs/01_overview.md`, `core/docs/01_architecture.en.md` |
| Active design-points | `append-only-ledger-evaluation.zh.md`, `explanation-completion-roadmap.zh.md`, `identity-mechanism-redesign.zh.md`, `ledger-schema-specification.zh.md` |

### 10.8 Carry-Forward Dependencies

- Step 2+ `:exists` removal remains a future lifecycle decision.
- Step 2+ shadow-store removal remains future work after lazy compatibility is retired.
- Slice 3b ledger schema migration remains the next runtime-heavy carry-forward candidate.
- Slice 5+ Q-PR1 PyReason adapter rewrite + INV-9 runtime strict enforcement remains out of Slice 4.
- Archived docs/examples and broader historical design-point cleanup remain out of scope unless a later slice explicitly selects them.

### 10.9 Archive Cadence

After reviewer acceptance of this implemented state:

1. `git mv` the blueprint and audit log from `workflow/blueprints/active/` to `workflow/blueprints/archive/`.
2. Add / update the Slice 4 row in `workflow/blueprints/archive/INVENTORY.md`.
3. Add a final archive row to this audit log.
4. Commit archive cadence separately.
5. Do not push unless the user explicitly authorizes it.
