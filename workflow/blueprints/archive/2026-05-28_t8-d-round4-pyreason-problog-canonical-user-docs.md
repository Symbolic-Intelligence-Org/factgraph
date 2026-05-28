# Task Blueprint: T8-D Round 4 PyReason + ProbLog Canonical User Docs

- Status: implemented
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Class: S (docs-only)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/archive/2026-05-28_t8-d-round4-pyreason-problog-canonical-user-docs.audit.md`
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
| `docs/official/kernel/quickstart/rules-and-inferences.md` | Deprecation cleanup target for stale `Inference` / `Query` teaching. |
| `src/factgraph/sdk/docs/00_user_guide.en.md` | Optional concise SDK summary target. |
| T8-D round 1/2/3 archive pairs | Docs-only cadence and leave-alone discipline. |

## 3. Step 4.6 Source-Backed Inventory

### 3.1 `semantics.md` Current Wording

`docs/official/kernel/quickstart/semantics.md` is the primary edit surface.

| Lines | Current state | Step 4.7 edit decision |
|---|---|---|
| `:18-41` | Wrapper table still teaches ProbLog defaults / branch probabilities and PyReason delays / `head_bound` / `branch_bounds`. | Rewrite table and wrapper descriptions to include `uncertainty_projection`, `iteration_count`, `derived_bound`, `atom_bounds`, `fact_boundaries`, and `time_binned`. |
| `:101-137` | `ProbLogSemantics` section teaches default wrapper and engine mismatch only. | Expand with T10-1 uncertainty projection policy map, default reject behavior, supported point policies, and rejected interval policies. |
| `:139-175` | `PyReasonSemantics` teaches `timestep_delay`, `head_bound`, `branch_bounds`; no C78/C74/C77 canonical fields. | Rewrite as canonical-first PyReason section: `iteration_count`, `derived_bound`, `atom_bounds`, `fact_boundaries`, `time_binned`; keep legacy aliases as compatibility notes. |
| `:177-194` | `SemanticsProfile` section still generic and accurate. | Minimal update only if needed to mention canonical lower form now includes `iteration_count`, `uncertainty_projection`, and temporal modes. |
| `:196-229` | Read-only/evaluation lifecycle wording remains accurate. | Leave mostly stable; ensure row `raw_kind`/`bound` comment still points to assertions. |
| `:231-255` | `Inference` branch-id compatibility remains accurate for branch-specific maps. | Keep as compatibility section; do not move in this cycle. |
| `:269-340` | Complete example/checklist still uses `head_bound` and omits new fields. | Update example/checklist to canonical spellings and mention docs for legacy branch ids. |

Runtime source-back:

- `ProbLogSemantics.uncertainty_projection` exists and normalizes in
  `src/factgraph/sdk/semantics.py:131-139, :162-169`.
- Default ProbLog projection rejects both configured raw kinds with fallback
  `reject_unconfigured`, verified by
  `tests/test_problog_semantics_profile_migration.py:400-411`.
- Supported ProbLog point policies are `lower`, `midpoint`, `upper`, and
  `identity_probability`; interval policies `probability_interval` /
  `possibility_interval` are accepted by profile validation but rejected by
  ProbLog point export, verified by
  `tests/test_problog_semantics_profile_migration.py:430-453, :487-525` and
  `src/factgraph/adapters/problog/problog_export.py:284-346`.
- PyReason public fields are source-backed at
  `src/factgraph/sdk/semantics.py:180-199, :215-239`.
- Temporal modes are source-backed at
  `src/factgraph/core/semantics/profile.py:165-190` and adapter consumption at
  `src/factgraph/adapters/pyreason/engine_eval.py:283-359`.

### 3.2 `assertions.md` Annotation Surface

`docs/official/kernel/quickstart/assertions.md` already teaches the raw carrier
well:

- Convention meta table includes `raw_kind` and `bound` at `:136-146`.
- Raw uncertainty section explains probabilistic / possibilistic kinds at
  `:148-189`.
- Canonical quantitative carrier explains write/evaluate/audit surfaces and
  shared annotation rows at `:191-231`.
- Reserved-key section rejects `probability`, `bound_lower`, `bound_upper` at
  `:244-271`.

Edit decision: add a short T10-1 projection note inside the existing raw
uncertainty / canonical carrier area, not a new schema dump. The note should
say that `ProbLogSemantics.uncertainty_projection` decides how probabilistic
interval bounds are projected, and that unsupported/default paths reject rather
than silently picking a point.

Source-back:

- Write protocol enforces paired raw carrier and removed keys in
  `src/factgraph/core/evidence/write_protocol.py:282-314`.
- ProbLog export consumes canonical `shared/semantic/raw_kind` and
  `shared/semantic/bound`, with projection decisions attached to trace metadata
  in `src/factgraph/adapters/problog/engine_eval.py:97-106, :180-199`.

### 3.3 Five-Cycle Teaching Plan

| Cycle | User-facing teaching point | Source-back |
|---|---|---|
| T10-1 | `ProbLogSemantics(uncertainty_projection={...})` maps raw uncertainty intervals to ProbLog point probabilities. Defaults reject unsupported uncertainty. | SDK field `semantics.py:131-139`; default reject test `test_problog...py:400-411`; point policy tests `:430-453`; interval reject tests `:506-525`. |
| T10-2-A | `PyReasonSemantics.iteration_count` is a positive global inference round count. Wrapper default is `1`; explicit canonical count conflicts with temporal timesteps carriers. | SDK field/validation `semantics.py:182-193, :215-218`; omission/default tests `test_pyreason...py:384-423`; conflict tests `:582-676`; adapter conflict helper `engine_eval.py:398-403`. |
| T10-2-B | `derived_bound` is canonical head interval; `atom_bounds` uses `<rule_id>:atom_<index>` and lowers to PyReason body atom targets. `derived_bound + head_bound` rejects; `atom_bounds + branch_bounds` may coexist. | SDK fields `semantics.py:183-197`; conflict check `:221-227`; lowering tests `test_pyreason...py:293-380`; store lowering `src/factgraph/sdk/store.py:3481-3528`. |
| T10-3-A | `fact_boundaries` is the canonical valid-time spelling. Option A preserves input spelling; legacy `valid_time_boundaries` remains accepted. | Profile modes `profile.py:176-183`; adapter dynamic carrier `engine_eval.py:318-337`; tests `test_pyreason...py:437-462, :628-649, :705-728`. |
| T10-3-B | `time_binned` is a new temporal mode with `universe` and strict `bin_size`. It requires exact universe divisibility and rejects naive datetimes / arbitrary prose durations. | Profile validation `profile.py:184-190, :207-250`; materializer `engine_eval.py:459-580`; tests `test_pyreason...py:464-524, :651-676, :731-893`. |

### 3.4 SDK Guide Decision

Decision: edit `src/factgraph/sdk/docs/00_user_guide.en.md` as the optional
fourth file.

Rationale: the guide is stale in two visible places:

- Engine runtime options still show
  `PyReasonSemantics(temporal_projection={"timesteps": 10})` at `:578-582`,
  which omits `mode` and no longer matches the normalized temporal projection
  shape.
- The PyReason transition section at `:1038-1081` lists only
  `none`, `fixed_timesteps`, and `valid_time_boundaries`, omitting
  `iteration_count`, `derived_bound`, `atom_bounds`, `fact_boundaries`, and
  `time_binned`.

Implementation should keep this concise: update the transition summary and
point readers to `docs/official/kernel/quickstart/semantics.md` for detail.
Do not duplicate the full quickstart.

### 3.5 Cross-Doc Consistency

| File | Finding | Decision |
|---|---|---|
| `namespace-map.md` | Semantics row at `:188` generically lists wrappers and `SemanticsProfile`; no stale field list. | Leave alone. |
| `evidence.md` | T8-D round 3 ProbLog row provenance section remains accurate; stability section `:328-357` positions `Inference` / `Branch` as legacy compatibility and links to rules. | Leave alone; preserve link target. |
| `rules-and-inferences.md` | Current API sections for `Rule`, `RuleExpr`, `fg.read.match`, `fg.eval.evaluate` at `:60-489` are useful; `Inference` / `Query` teaching is over-prominent and duplicated. | Edit only stale `Inference` / `Query` teaching and opening/checklist. |
| Adapter docs | `03_pyreason_adapter.md` has stale mode list, but adapter docs are named future work. | Leave alone by scope. |

### 3.6 Anti-Silent-Ignore Teaching

Docs should teach explicit conflicts without turning quickstart into an error
catalog:

- T10-1: default ProbLog projection rejects unsupported raw uncertainty; users
  configure a policy rather than relying on silent midpoint.
- T10-2-A: wrapper default `iteration_count=1` is valid. The behavior warning is
  that `PyReasonSemantics()` now lowers to canonical timesteps 1, while direct
  no-profile PyReason adapter execution still keeps engine default timesteps 2.
  Explicit `iteration_count` plus `fixed_timesteps`, `valid_time_boundaries`,
  `fact_boundaries`, or `time_binned` rejects.
- T10-2-B: `derived_bound + head_bound` rejects because both target the rule
  head; `atom_bounds + branch_bounds` can coexist because body-atom and branch
  head intervals are different surfaces.
- T10-3-A/B: temporal conflict errors include the supplied carrier spelling
  (`fact_boundaries` or `time_binned`), following dynamic carrier tests at
  `tests/test_pyreason_semantics_profile_migration.py:628-676`.

### 3.7 Leave-Alone Sweep

| Surface | Reason |
|---|---|
| `docs/official/kernel/quickstart/evidence.md` | T8-D round 3 aligned row provenance; no contradiction found. |
| `src/factgraph/audit/docs/02_evidence_graph.md` | Audit-module evidence docs are outside this quickstart cycle. |
| `src/factgraph/adapters/docs/02_problog_adapter.md` / `03_pyreason_adapter.md` | Adapter docs alignment is named future work. |
| Other quickstart files | `namespace-map.md` and evidence are not stale for this cycle; database/persistence/schema/index/read-write are unrelated. |
| Runtime and tests | Docs-only cycle; no behavior changes. |
| Four untracked design-point files | Claim-first / design-point intake remains separate strategic work. |

### 3.8 `rules-and-inferences.md` Deprecation Cleanup Map

| Lines | Current state | Step 4.7 treatment |
|---|---|---|
| `:6-20` | Opening table presents `Inference` as first-class "Propose new facts" path. | Rewrite to lead with `Rule` / `RuleExpr`, `fg.read.match`, and `fg.eval.evaluate`; mention `Inference` only as legacy compatibility. |
| `:28-41` and `:647-659` | Imports include `Branch`, `Inference`, `Pred`, `Query` in broad examples. | Remove `Query`; keep legacy imports only in a scoped legacy section. |
| `:60-489` | Current `Rule`, `RuleExpr`, `match`, `evaluate`, head selection content. | Preserve, except line `:106` can say `Branch` belongs to legacy `Inference` rather than "use Inference for that". |
| `:491-514` | "Use Query for one-off projections" includes `Query(...)` example. | Delete or replace with a short internal-only note; public path is `fg.read.find`, `fg.read.match`, or `fg.eval.evaluate`. |
| `:516-589` | "Evaluate an Inference" is already labeled v0.2 compatibility but too large for the main path. | Move/demote under a "Legacy compatibility: Inference and Branch" section after current API path; keep enough example to preserve compatibility teaching. |
| `:608-625` | Lifecycle summary still says `Inference -> evaluate`. | Rewrite to `Rule / RuleExpr -> evaluate`; note legacy `Inference` can still be evaluated. |
| `:629-642` | Stability link to evidence §7. | Keep and ensure target remains valid. |
| `:644-717` | Complete example repeats both `Query` and `Inference`. | Remove `Query`; either omit legacy inference from complete example or move it below the legacy section. |
| `:719-759` | Syntax checklist still leads with `Inference` body details and Query removal. | Reorder to current canonical API first; leave legacy bullets clearly marked. |

## 4. Open Questions

| ID | Answer |
|---|---|
| Q1 | Edit `semantics.md` lines `:18-41`, `:101-175`, `:177-194` lightly, `:269-340`; keep `:50-99`, `:196-229`, and `:231-255` mostly stable. See §3.1. |
| Q2 | Insert a short T10-1 note in `assertions.md` around `:177-212`, where raw uncertainty and canonical carrier are already explained. Do not add a new schema dump. |
| Q3 | Yes, edit `src/factgraph/sdk/docs/00_user_guide.en.md`: `:578-630` and `:1038-1081` are stale after T10-2/T10-3. Keep it concise and point to the quickstart. |
| Q4 | Wording: "`PyReasonSemantics()` uses canonical `iteration_count=1`; direct no-profile PyReason adapter execution still has its existing engine default. If you also supply legacy temporal timesteps (`fixed_timesteps`, `fact_boundaries`, `valid_time_boundaries`, or `time_binned`), the adapter rejects the explicit conflict instead of choosing a winner." |
| Q5 | Document the full `bin_size` accept list: `P<n>D`, `PT<n>H`, `PT<n>M`, `1d`, `1h`, `15m`, `1m`; mention exact universe divisibility, ISO date / timezone-aware datetime rules, and examples of rejected prose/ambiguous forms. No full parser dump. |
| Q6 | Explain `atom_bounds` keys as application atom ids from the rule, formatted `<rule_id>:atom_<index>`, with a short example. Do not teach internal `body_atom:0:<index>` conversion or T8-B witness keys. |
| Q7 | Teach `fact_boundaries` first as canonical. Add one compatibility sentence: legacy `valid_time_boundaries` remains accepted and preserves its spelling for existing profiles. |
| Q8 | Leave alone: `evidence.md`, audit docs, adapter docs, unrelated quickstarts, runtime/tests, dirty baseline, four untracked design-point files. See §3.7. |
| Q9 | Use four docs commits plus close/archive: PyReason quickstart, ProbLog quickstart/assertions, `rules-and-inferences.md` cleanup, SDK guide summary. Commits 1-2 may combine only if small; commit 3 should stay independent. |
| Q10 | No stop/amend findings. All findings refine docs scope; no shipped archive contradiction. |
| Q11 | Teach `Inference` only as v0.2 legacy compatibility after current `Rule` / `RuleExpr` / `fg.eval.evaluate` path. Keep runtime compatibility wording; do not imply removal. |
| Q12 | Remove the user-facing `Query` one-off projection example. If `Query` remains mentioned, mark it internal/future DSL value and direct users to `fg.read.find`, `fg.read.match`, or `fg.eval.evaluate`. |

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

Step 4.6 verification baseline:

```text
PYTHONPATH=src python -m unittest ...  # focused docs-only set
Ran 140 tests in 0.455s
OK
```

## 7. Proposed Implementation Shape

Candidate chain:

1. `docs(quickstart): teach PyReason canonical semantics`
2. `docs(quickstart): teach ProbLog uncertainty projection`
3. `docs(quickstart): clean deprecated Inference Query references`
4. `docs(sdk-guide): summarize canonical semantics additions`
5. `docs(blueprint): close T8-D round 4 canonical user docs`
6. `docs(blueprint): archive T8-D round 4 canonical user docs`

Commits 1-2 may combine if Step 4.6 finds the edits are small and the audit
records why the engine-specific topics remain independently reviewable. Commit
3 should stay separate unless Step 4.6 proves the `Inference` / `Query` cleanup
is trivial; it has a different review surface than teaching new T10 semantics.

## 8. Acceptance Checklist

- [x] Step 4.2 review completed.
- [x] Step 4.6 source-backed inventory completed.
- [x] Q1-Q12 answered.
- [x] `semantics.md` teaches the five shipped semantics cycles accurately.
- [x] `assertions.md` teaches ProbLog raw uncertainty annotation only as needed.
- [x] `rules-and-inferences.md` demotes deprecated `Inference` / `Query`
  teaching without weakening current canonical API docs.
- [x] SDK guide decision implemented.
- [x] T10-2-A default behavior warning is user-friendly and accurate.
- [x] Existing T8-D round 1/2/3 user docs are not regressed.
- [x] Evidence quickstart, audit module docs, adapter module docs, runtime,
  tests, governance, and dirty-baseline files are untouched.
- [x] All 11 session archives remain locked.
- [x] Focused docs-only no-op verification passes.
- [x] Full discover delta, if run, is compared against
  `2038 tests / 72 failures / 231 errors`.
- [x] `git diff --check` clean.
- [x] Sacred master and dirty baseline preserved.

## 9. Verification Commands

Docs-only verification:

```bash
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration tests.test_problog_semantics_profile_migration tests.test_audit_evidence_graph
git diff --check
git status --short --branch
git rev-parse master
```

## 10. Outcome / Deviations

Implemented in six commits:

1. `fa63e851` — draft blueprint/audit pair.
2. `abce9fb9` — scoped source-backed implementation plan.
3. `be12f426` — `semantics.md` teaches PyReason canonical semantics:
   `iteration_count`, `derived_bound`, `atom_bounds`, `fact_boundaries`, and
   `time_binned`, including compatibility and conflict boundaries.
4. `d24bfe00` — `semantics.md` and `assertions.md` teach ProbLog
   `uncertainty_projection`, default reject behavior, supported point
   projection policies, and raw `raw_kind` / `bound` annotation usage.
5. `1545964a` — `rules-and-inferences.md` demotes `Inference` to v0.2 legacy
   compatibility, removes `Query` as a one-off projection teaching path, and
   keeps `Rule` / `RuleExpr` / `fg.read.match(...)` / `fg.eval.evaluate(...)`
   as the leading user path.
6. `b4824443` — SDK user guide summarizes canonical ProbLog/PyReason
   semantics additions and points readers to the quickstart for full examples.

Verification:

- Focused docs-only no-op set: `Ran 140 tests in 0.430s — OK`.
- Full discover: `Ran 2038 tests in 3.132s — FAILED (failures=72, errors=231)`,
  matching the established `2038 / 72F / 231E` baseline with zero composition
  shift.
- `git diff --check` clean.
- Sacred `master` stayed at `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline stayed at `4 M + 1 D + 6 U`; the four untracked design-point
  files were not absorbed.

Deviations / notes:

- The cycle expanded from the initial T10 semantics teaching target to include
  `rules-and-inferences.md` deprecation cleanup after user source-back showed
  stale first-class `Inference` / `Query` teaching. The cleanup stayed within
  the amended four-file cap and remained docs-only.
- Adapter module docs remain explicitly deferred to a separate adapter-docs
  alignment cycle.
- `Query` runtime/DSL code remains implemented; user docs now mark it as an
  internal DSL value rather than a quickstart projection path.
- `Inference` / `Branch` remain documented as v0.2 compatibility surfaces, and
  the T8-D round 1 stability link to `evidence.md` was preserved.
