# Task Blueprint: T8-D Round 4 PyReason + ProbLog Canonical User Docs

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Class: S (docs-only)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-28_t8-d-round4-pyreason-problog-canonical-user-docs.audit.md`
- Trigger: Five public semantics cycles have shipped without a matching
  user-facing quickstart refresh: T10-1 ProbLog C76 uncertainty projection at
  `cde072fa`, T10-2-A C78 `iteration_count` at `65cc79a3`, T10-2-B C74
  `derived_bound` / `atom_bounds` at `92fd6013`, T10-3-A C77 `fact_boundaries`
  at `e7bab90f`, and T10-3-B C77 `time_binned` at `ac42a379`. T8-D rounds
  1/2/3 established the docs-follow cadence for shipped evidence/adapter
  surfaces; round 4 aligns public semantics user docs without touching runtime.
  Per user amend, it also includes `rules-and-inferences.md` deprecation
  cleanup for stale first-class `Inference` / `Query` teaching.

## 0. Scope Locks

### In scope

This is a docs-only user-facing alignment cycle. File scope is capped at four
files.

1. `docs/official/kernel/quickstart/semantics.md` as the primary target:
   - Teach `ProbLogSemantics.uncertainty_projection`, including policy mapping,
     supported point-projection policies, rejected interval-valued policies, and
     default reject behavior.
   - Teach `PyReasonSemantics.iteration_count: int = 1`, including explicit
     conflict behavior with legacy temporal timesteps and the user-facing
     warning that the wrapper default is now canonical `1` while no-profile
     adapter execution keeps its existing engine default.
   - Teach `PyReasonSemantics.derived_bound` and `atom_bounds`, including
     `<rule_id>:atom_<index>` atom ids, legacy compatibility, and asymmetric
     conflict behavior.
   - Teach `temporal_projection.mode = "fact_boundaries"` as the canonical
     valid-time alias while keeping legacy `valid_time_boundaries` accepted.
   - Teach `temporal_projection.mode = "time_binned"` with explicit `universe`,
     strict `bin_size` whitelist, exact universe divisibility, ISO date /
     timezone-aware datetime rules, and naive datetime rejection.
2. `docs/official/kernel/quickstart/assertions.md` as a secondary T10-1 target:
   - Add the public write annotation shape for ProbLog raw uncertainty:
     `shared/semantic/raw_kind` and `shared/semantic/bound`.
   - Keep the explanation brief: when to use it, how it interacts with
     `ProbLogSemantics.uncertainty_projection`, and that default projection
     rejects unsupported uncertainty instead of silently choosing a point value.
3. `docs/official/kernel/quickstart/rules-and-inferences.md` for deprecation
   cleanup:
   - Remove or significantly demote the stale "Use Query for one-off
     projections" teaching.
   - Move `Inference` teaching behind a clear legacy compatibility boundary
     instead of presenting it as the first/default user API.
   - Update the opening and summary table so `Rule`, `RuleExpr`,
     `fg.read.match()`, and `fg.eval.evaluate()` lead.
   - Clean redundant `Inference` / `Query` imports where they only support stale
     teaching.
4. `src/factgraph/sdk/docs/00_user_guide.en.md` only if Step 4.6 finds the
   existing semantics summary is stale:
   - Use the T8-D round 3 pattern: concise summary plus quickstart pointer.
   - Do not duplicate the full quickstart detail.

### Out of scope

- `docs/official/kernel/quickstart/evidence.md`; T8-D round 3 aligned ProbLog
  row provenance user docs and this cycle must not disturb that work.
- `src/factgraph/audit/docs/02_evidence_graph.md`; T8-C-1 commit `a916a856`
  aligned audit-module evidence docs.
- Adapter module docs:
  `src/factgraph/adapters/docs/02_problog_adapter.md` and
  `src/factgraph/adapters/docs/03_pyreason_adapter.md`. Adapter docs alignment
  is named future work, not part of this user-doc cycle.
- Other quickstart files: database, persistence, schema, first-factgraph,
  index, namespace-map, and read-write.
- Deleting or weakening the `Inference` / `Query` DSL implementation. This
  cycle changes user-doc teaching only.
- Changing existing canonical `Rule`, `RuleExpr`, `fg.read.match()`, or
  `fg.eval.evaluate()` teaching except where needed to make it lead the stale
  compatibility content.
- Non-`Inference` / non-`Query` content in `rules-and-inferences.md`.
- T8-C-2 PyReason evidence enrichment; it remains gated on D11 / Form 2.
- Runtime or test code changes.
- D20, failed graph, why-not, counterfactual, service, OpenAPI, Database/view,
  match API, `fg.eval.run`, release, PyPI, or tags.
- `EvidenceGraph` DTO, 14-key metadata, `_FORM1_ROW_SUPPORT_KINDS`, or
  `_WITNESS_BEARING_SUPPORT_KINDS`.
- T8-A, T8-B, or T8-D round 1/2/3 shipped user-doc behavior weakening.
- T10-1, T10-2-A, T10-2-B, T10-3-A, or T10-3-B runtime behavior weakening.
- C110 / C119 / C136 / D11 / D13 / Nemo / Form 2 deferred-state changes.
- Governance / workflow rule changes.
- Sacred `master`.
- Dirty baseline `4 M + 1 D + 6 U`, including the four untracked active
  design-point files.
- Reopening any session archive: T10-1, T8-C-1 inventory, T8-C-1 runtime,
  T8-D round 3, memory compaction, T10-2 inventory, T10-2-A, T10-2-B, T10-3
  inventory, T10-3-A, or T10-3-B. If source-back contradicts an archive, stop
  and amend the relevant archive instead of silently diverging.
- Claim-first ledger design discussion or adoption/classification of the four
  untracked design-point files.
- Full JSON/HTML schema dumps.

### Stop / amend triggers

Pause and amend before implementation if Step 4.6 shows:

1. Any shipped T10 behavior needs reopening instead of documentation.
2. The T10-2-A default `iteration_count=1` / no-profile engine default
   distinction cannot be explained clearly for users.
3. A docs change would regress T8-D round 1/2/3 user-facing evidence docs.
4. Adapter module docs must align first because the quickstart would otherwise
   contradict them.
5. Runtime, tests, governance, sacred, dirty-baseline, or untracked design-point
   files need edits.
6. File scope exceeds four files.
7. `rules-and-inferences.md` cleanup would require changing runtime DSL classes
   or T8-D round 1 evidence stability wording.

## 1. Problem

The runtime/API side of T10 is now complete: ProbLog C76 shipped, and PyReason
C74/C77/C78 shipped across T10-2-A, T10-2-B, T10-3-A, and T10-3-B. The
user-facing semantics quickstart still needs to teach those public wrappers and
canonical temporal/rule parameters so users can discover shipped behavior
without reading archived implementation blueprints.

This cycle is the T8-D round 4 docs-follow slice. It aligns user docs only; it
does not change adapter behavior, evidence graphs, audit docs, or design-point
lifecycle state.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/blueprints/archive/2026-05-27_t10-1-problog-uncertainty-projection.md` | T10-1 shipped C76 ProbLog behavior. |
| `workflow/blueprints/archive/2026-05-28_t10-2-a-pyreason-iteration-count-migration.md` | T10-2-A C78 `iteration_count` behavior and default warning. |
| `workflow/blueprints/archive/2026-05-28_t10-2-b-pyreason-canonical-rule-params.md` | T10-2-B C74 `derived_bound` / `atom_bounds` behavior. |
| `workflow/blueprints/archive/2026-05-28_t10-3-a-fact-boundaries-migration.md` | T10-3-A `fact_boundaries` alias behavior. |
| `workflow/blueprints/archive/2026-05-28_t10-3-b-time-binned-migration.md` | T10-3-B `time_binned` behavior and `bin_size` whitelist. |
| `docs/official/kernel/quickstart/semantics.md` | Primary user-facing target. |
| `docs/official/kernel/quickstart/assertions.md` | Secondary ProbLog raw-uncertainty annotation target. |
| `src/factgraph/sdk/docs/00_user_guide.en.md` | Optional concise SDK summary target. |
| T8-D round 1/2/3 archive pairs | Docs-only cadence and leave-alone discipline. |

## 3. Step 4.6 Source-Backed Inventory Skeleton

### 3.1 `semantics.md` Current Wording

Inventory the current `ProbLogSemantics` / `PyReasonSemantics` sections:

- Existing wrapper examples and policy tables.
- Current mentions of `uncertainty_projection`, `iteration_count`,
  `derived_bound`, `atom_bounds`, `fact_boundaries`, and `time_binned`.
- Sections that should remain byte-stable because they cover already-shipped
  T8-D round 1/2/3 or non-semantic topics.

### 3.2 `assertions.md` Annotation Surface

Inventory existing ProbLog / PyReason assertion annotation text and decide the
smallest insertion point for `shared/semantic/raw_kind` +
`shared/semantic/bound`.

### 3.3 Five-Cycle Teaching Plan

For each shipped cycle, Step 4.6 must record the exact user-facing content:

1. T10-1: ProbLog `uncertainty_projection` policies and raw uncertainty
   annotations.
2. T10-2-A: PyReason `iteration_count`, default behavior, and conflict
   behavior.
3. T10-2-B: PyReason `derived_bound`, `atom_bounds`, atom id format, and
   legacy compatibility.
4. T10-3-A: `fact_boundaries` canonical alias and legacy
   `valid_time_boundaries` compatibility.
5. T10-3-B: `time_binned`, strict `bin_size` whitelist, universe divisibility,
   date/datetime parsing, and conflict behavior.

### 3.4 SDK Guide Decision

Decide whether `src/factgraph/sdk/docs/00_user_guide.en.md` needs a concise
summary update. If yes, keep it short and point to the quickstart. If no,
record why the existing SDK guide is not stale.

### 3.5 Cross-Doc Consistency

Check whether `namespace-map.md`, `rules-and-inferences.md`, `evidence.md`, and
audit docs contain stale semantics claims. The default expectation is
leave-alone unless Step 4.6 finds direct contradiction.

### 3.6 Anti-Silent-Ignore Teaching

Record how the docs should explain explicit rejection / conflict behavior:

- T10-1 default ProbLog projection rejects unsupported uncertainty.
- T10-2-A rejects explicit `iteration_count` plus legacy temporal timesteps.
- T10-2-B rejects `derived_bound` plus `head_bound`, while `atom_bounds` and
  `branch_bounds` can coexist.
- T10-3-A/B temporal modes reject explicit `iteration_count` conflicts with
  carrier-specific messages.

### 3.7 Leave-Alone Sweep

List all files intentionally not edited, including evidence quickstart, audit
module docs, adapter module docs, other quickstart files, and the four
untracked design-point files.

### 3.8 `rules-and-inferences.md` Deprecation Cleanup

Source-back every `Inference` / `Query` occurrence in
`docs/official/kernel/quickstart/rules-and-inferences.md` and classify each
stale segment:

- Delete or rewrite stale `Query` one-off projection teaching.
- Move `Inference` content to a legacy compatibility section when it remains
  useful.
- Keep `Rule`, `RuleExpr`, `fg.read.match()`, and `fg.eval.evaluate()` as the
  leading current API.
- Check any cross-link to `evidence.md` stability wording before editing.

## 4. Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | What exact `semantics.md` sections will be edited? | Line refs, section names, and leave-alone ranges. |
| Q2 | Where does the `assertions.md` raw uncertainty annotation text belong? | Line refs and minimal insertion plan. |
| Q3 | Should the SDK guide be edited? | Yes/no with source-backed rationale. |
| Q4 | How should T10-2-A's default `iteration_count=1` behavior change be explained? | User-facing warning that distinguishes wrapper default from no-profile engine default. |
| Q5 | How deep should `bin_size` documentation go? | Full whitelist and rejection examples without schema dump. |
| Q6 | How deep should `atom_bounds` atom-id documentation go? | Explain `<rule_id>:atom_<index>` enough for users to write it; no internal conversion dump. |
| Q7 | How should `fact_boundaries` be taught without encouraging legacy spelling? | Canonical-first wording plus compatibility note. |
| Q8 | Which files are explicitly left alone? | Table with reason for each leave-alone file. |
| Q9 | What implementation split should be used? | 1-4 docs commits plus close/archive. |
| Q10 | Are there stop/amend findings? | Trigger-by-trigger assessment. |
| Q11 | How should `Inference` be taught? | Prefer legacy compatibility section over first-class/default API teaching. |
| Q12 | How should `Query` be taught? | Prefer deleting user-facing one-off projection teaching; if referenced, mark internal-only. |

## 5. Existing Invariants To Preserve

- T8-A 14-key metadata, `run_id` envelope-only boundary, and always-on
  validation.
- T8-B-1 native Form 1 and T8-B-2 Souffle Form 1 behavior.
- T8-C-1 ProbLog row provenance graphs and namespaced `engine_meta["problog"]`.
- T8-D round 1 native Form 1 user docs.
- T8-D round 2 Souffle Form 1 user docs.
- T8-D round 3 ProbLog row provenance user docs.
- T10-1 anti-silent-ignore behavior for ProbLog uncertainty projection.
- T10-2-A C78 `iteration_count` behavior.
- T10-2-B C74 canonical rule parameter behavior.
- T10-3-A `fact_boundaries` alias behavior.
- T10-3-B `time_binned` strict whitelist and materialization behavior.
- Current canonical `Rule`, `RuleExpr`, `fg.read.match()`, and
  `fg.eval.evaluate()` teaching.
- T8-D round 1 evidence stability wording around legacy `Inference` / `Branch`.
- `Inference` / `Query` DSL classes remain implemented; docs cleanup does not
  delete runtime compatibility surfaces.
- C110 legacy `confidence` rejection.
- `EvidenceGraph` DTO, `_FORM1_ROW_SUPPORT_KINDS`, and
  `_WITNESS_BEARING_SUPPORT_KINDS`.
- C119 / C136 / D11 / D13 / Nemo / Form 2 remain deferred.
- All 11 session archives remain locked unless this cycle stops and amends the
  relevant archive.
- Sacred `master = 562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline `4 M + 1 D + 6 U`.

## 6. Step 4.6 Inventory Plan

Commands:

```bash
rg -n "ProbLogSemantics|PyReasonSemantics|iteration_count|temporal_projection|uncertainty_projection|derived_bound|atom_bounds|fact_boundaries|time_binned|raw_kind|bound" docs/official/kernel/quickstart/semantics.md docs/official/kernel/quickstart/assertions.md
rg -n "ProbLog|PyReason|uncertainty|temporal|atom_bounds|fact_boundaries|time_binned" src/factgraph/sdk/docs/00_user_guide.en.md src/factgraph/sdk/docs/01_concepts.en.md
rg -n "ProbLog|PyReason" docs/official/kernel/quickstart/namespace-map.md docs/official/kernel/quickstart/rules-and-inferences.md docs/official/kernel/quickstart/evidence.md
rg -n "Inference|Query|fg\\.read\\.match|fg\\.eval\\.evaluate|RuleExpr" docs/official/kernel/quickstart/rules-and-inferences.md docs/official/kernel/quickstart/evidence.md
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration tests.test_problog_semantics_profile_migration tests.test_audit_evidence_graph
git diff --check
git status --short --branch
git rev-parse master
```

Expected Step 4.6 outputs:

1. Source-backed target section map.
2. Five-cycle teaching content plan.
3. SDK guide edit/no-edit decision.
4. Leave-alone file table.
5. `rules-and-inferences.md` deprecation cleanup map.
6. Verification baseline plan.
7. Stop/amend assessment.

## 7. Proposed Implementation Shape

Candidate chain:

1. `docs(quickstart): teach PyReason canonical semantics`
2. `docs(quickstart): teach ProbLog uncertainty projection`
3. `docs(quickstart): clean deprecated Inference Query references`
4. `docs(sdk-guide): summarize canonical semantics additions` (only if Step 4.6
   decides the SDK guide is stale)
5. `docs(blueprint): close T8-D round 4 canonical user docs`
6. `docs(blueprint): archive T8-D round 4 canonical user docs`

Commits 1-2 may combine if Step 4.6 finds the edits are small and the audit
records why the engine-specific topics remain independently reviewable. Commit
3 should stay separate unless Step 4.6 proves the `Inference` / `Query` cleanup
is trivial; it has a different review surface than teaching new T10 semantics.

## 8. Acceptance Checklist

- [ ] Step 4.2 review completed.
- [ ] Step 4.6 source-backed inventory completed.
- [ ] Q1-Q12 answered.
- [ ] `semantics.md` teaches the five shipped semantics cycles accurately.
- [ ] `assertions.md` teaches ProbLog raw uncertainty annotation only as needed.
- [ ] `rules-and-inferences.md` demotes deprecated `Inference` / `Query`
  teaching without weakening current canonical API docs.
- [ ] SDK guide decision implemented.
- [ ] T10-2-A default behavior warning is user-friendly and accurate.
- [ ] Existing T8-D round 1/2/3 user docs are not regressed.
- [ ] Evidence quickstart, audit module docs, adapter module docs, runtime,
  tests, governance, and dirty-baseline files are untouched.
- [ ] All 11 session archives remain locked.
- [ ] Focused docs-only no-op verification passes.
- [ ] Full discover delta, if run, is compared against
  `2038 tests / 72 failures / 231 errors`.
- [ ] `git diff --check` clean.
- [ ] Sacred master and dirty baseline preserved.

## 9. Verification Commands

Docs-only verification:

```bash
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration tests.test_problog_semantics_profile_migration tests.test_audit_evidence_graph
git diff --check
git status --short --branch
git rev-parse master
```

## 10. Outcome / Deviations

Pending Step 4.6 / implementation / closure.
