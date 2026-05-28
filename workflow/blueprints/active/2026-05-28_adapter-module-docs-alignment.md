# Task Blueprint: Adapter Module Docs Alignment

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Class: S (docs-only)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-28_adapter-module-docs-alignment.audit.md`
- Trigger: T8-D round 5 shipped at `1f5427ee`, closing the PyReason evidence
  deferred-state quickstart contract. T8-D round 4 (`06e575dd`) and T8-D round
  5 (`1f5427ee`) both named adapter module docs as future work. Quickstart
  docs are now aligned for shipped ProbLog/PyReason public semantics and
  evidence boundaries, but `src/factgraph/adapters/docs/02_problog_adapter.md`
  and `src/factgraph/adapters/docs/03_pyreason_adapter.md` have not yet been
  independently source-backed against the shipped T10 runtime and T8-C-1
  ProbLog row-provenance behavior.

## 0. Scope Locks

### In scope

This is a module-docs-only alignment cycle. Implementation file scope is capped
at two files:

1. `src/factgraph/adapters/docs/02_problog_adapter.md`
   - Align with T10-1 C76 `uncertainty_projection`: default reject, `lower`,
     `midpoint`, `upper`, degenerate `identity_probability`, and interval
     rejection behavior.
   - Align with shipped ProbLog raw `raw_kind` / `bound` consumption.
   - Align with T8-C-1 row provenance: `PROBLOG_PROVENANCE_KIND`,
     `EDGE_DERIVES`, and namespaced `engine_meta["problog"]`.
2. `src/factgraph/adapters/docs/03_pyreason_adapter.md`
   - Align with T10-2-A C78 `iteration_count`: wrapper default `1`,
     no-profile engine default `2`, and explicit conflict with temporal
     timesteps modes.
   - Align with T10-2-B C74 `derived_bound` and `atom_bounds`, including
     application atom id `<rule_id>:atom_<index>` and internal
     `body_atom:0:<index>` conversion, without reusing evidence witness keys.
   - Align with asymmetric C74 compatibility: `derived_bound + head_bound`
     rejects; `atom_bounds + branch_bounds` may coexist.
   - Align with T10-3-A C77 `fact_boundaries` canonical alias and legacy
     `valid_time_boundaries` compatibility.
   - Align with T10-3-B C77 `time_binned`: strict `bin_size` whitelist
     (`P<n>D`, `PT<n>H`, `PT<n>M`, `1d`, `1h`, `15m`, `1m`), exact universe
     divisibility, timezone-aware datetime requirement, and prose duration
     rejection.
   - Align with T8-D round 5 evidence boundary: PyReason is provenance-bearing
     at adapter level, but row-result evidence currently uses the safe
     single-`NODE_CONCLUSION` fallback until Form 2 design / T8-C-2 bridge work
     lands.

### Out of scope

- Quickstart docs under `docs/official/kernel/quickstart/*`; T8-D rounds
  1/2/3/4/5 already aligned user-facing docs.
- Runtime changes in ProbLog or PyReason adapters, `engine_eval.py`, protocol,
  store, or SDK wrappers.
- Tests or test docs.
- Governance or workflow rules.
- D11 / Form 2 schema definition: timestep, time-window, bound update,
  component identity, producer/consumer contract, detailed `LAYOUT_TIMELINE`,
  and `EDGE_DERIVES` vs `EDGE_UPDATES` design remain deferred.
- T8-C-2 PyReason evidence runtime.
- `EvidenceGraph` DTO, 14-key metadata, and support-kind partitions.
- T10-1 / T10-2-A / T10-2-B / T10-3-A / T10-3-B runtime behavior.
- T8-D round 1-5 quickstart teaching changes or regressions.
- Audit module docs such as `src/factgraph/audit/docs/02_evidence_graph.md`.
- Other adapter docs or module docs.
- Sacred `master`.
- Dirty baseline `4 M + 1 D + 6 U`, including untracked design-point files.
- Claim-first ledger design or design-point intake.
- Reopening the current 13-archive lockout set: T10-1, T8-C-1 inventory,
  T8-C-1 runtime, T8-D round 3, memory compaction, T10-2 inventory, T10-2-A,
  T10-2-B, T10-3 inventory, T10-3-A, T10-3-B, T8-D round 4, and T8-D round 5.
  If Step 4.6 finds a contradiction with an archive, stop and amend the
  relevant archive instead of silently diverging.

### Stop / amend triggers

Pause and amend before implementation if Step 4.6 shows:

1. Existing adapter docs contain runtime claims that contradict shipped T10 /
   T8-C-1 behavior in a way that would require reopening runtime or archives.
2. Form 2 schema details would need to be documented to make the adapter docs
   coherent.
3. Adapter docs and T8-D round 1-5 quickstarts contradict each other and fixing
   the contradiction requires touching quickstart docs.
4. `pyreason_trace_to_evidence_graph(...)` has a signature or import path that
   conflicts with planned module-doc wording.
5. Runtime or tests need changes.
6. Implementation file scope exceeds the two adapter-doc files.
7. Cross-adapter, audit-module, or quickstart stale areas are too broad for a
   self-contained adapter module docs cycle.

## 1. Problem

T10 runtime semantics and T8-C-1 ProbLog row provenance are shipped and now
taught in user-facing quickstarts. Adapter module docs are a lower-level surface
for contributors and advanced users; if they lag behind, they can teach stale
adapter behavior even when quickstarts are correct.

This cycle checks and aligns only the ProbLog and PyReason adapter docs. It
should close the named future work from T8-D rounds 4 and 5 without reopening
quickstart docs, runtime, tests, Form 2 design, or audit module docs.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/blueprints/archive/2026-05-27_t10-1-problog-uncertainty-projection.md` | T10-1 C76 shipped behavior anchor. |
| `workflow/blueprints/archive/2026-05-28_t8-c-1-problog-evidence-enrichment-runtime.md` | T8-C-1 ProbLog row provenance runtime anchor. |
| `workflow/blueprints/archive/2026-05-28_t8-d-round4-pyreason-problog-canonical-user-docs.md` | User-facing canonical semantics docs anchor and future-work trigger. |
| `workflow/blueprints/archive/2026-05-28_t8-d-round5-pyreason-evidence-deferred-state-docs.md` | PyReason evidence deferred-state docs anchor and future-work trigger. |
| `workflow/blueprints/archive/2026-05-28_t10-2-a-pyreason-iteration-count-migration.md` | T10-2-A C78 behavior anchor. |
| `workflow/blueprints/archive/2026-05-28_t10-2-b-pyreason-canonical-rule-params.md` | T10-2-B C74 behavior anchor. |
| `workflow/blueprints/archive/2026-05-28_t10-3-a-fact-boundaries-migration.md` | T10-3-A C77 alias behavior anchor. |
| `workflow/blueprints/archive/2026-05-28_t10-3-b-time-binned-migration.md` | T10-3-B C77 `time_binned` behavior anchor. |
| `src/factgraph/adapters/docs/02_problog_adapter.md` | ProbLog adapter module docs target. |
| `src/factgraph/adapters/docs/03_pyreason_adapter.md` | PyReason adapter module docs target. |
| Shipped source under `src/factgraph/` | Step 4.6 source-back for module-doc claims. |
| T8-D round 1-5 quickstart docs | Cross-doc consistency source. |

## 3. Step 4.6 Source-Backed Inventory Skeleton

### 3.1 ProbLog Adapter Doc Current State

Source-back `02_problog_adapter.md` against T10-1 and T8-C-1:

- Locate current ProbLog uncertainty / probability export wording.
- Locate any `raw_kind` / `bound` wording.
- Locate any row-provenance / `EvidenceGraph` / `engine_meta` wording.
- Classify stale vs current claims with line refs.

### 3.2 PyReason Adapter Doc Current State

Source-back `03_pyreason_adapter.md` against T10-2-A, T10-2-B, T10-3-A, T10-3-B,
and T8-D round 5:

- Locate current timesteps / temporal projection wording.
- Locate current rule-bound / atom-bound wording.
- Locate current `valid_time_boundaries`, `fact_boundaries`, and `time_binned`
  wording.
- Locate current evidence / timeline / helper wording.
- Classify stale vs current claims with line refs.

### 3.3 ProbLog Teaching Plan

Decide insertion or rewrite points for:

- C76 `uncertainty_projection`.
- Supported point-projection policies and default reject.
- Raw `raw_kind` / `bound` adapter consumption.
- T8-C-1 row provenance graph shape and `engine_meta["problog"]`.

### 3.4 PyReason Teaching Plan

Decide insertion or rewrite points for:

- C78 `iteration_count`.
- C74 `derived_bound` / `atom_bounds` and atom-id conversion.
- C77 `fact_boundaries` and `time_binned`.
- PyReason evidence deferred state and advanced helper wording.

### 3.5 Quickstart Consistency Sweep

Compare adapter docs wording against T8-D round 1-5 quickstarts:

- Do module docs expose more internal detail than quickstarts? If yes, ensure it
  is clearly module-level.
- Do module docs contradict quickstarts? If yes, decide whether this docs cycle
  can fix the adapter side without reopening quickstarts.

### 3.6 Form 2 / Evidence Boundary Sweep

Ensure PyReason adapter docs do not define deferred Form 2 schema. They may
state that rich row-level PyReason temporal evidence remains future and may
describe adapter-level helper availability only if source-backed.

### 3.7 Leave-Alone Table

List quickstart docs, audit docs, runtime, tests, workflow, dirty-baseline files,
and design-point files that must remain untouched.

## 4. Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | What stale/current claims exist in `02_problog_adapter.md` for T10-1 C76 and T8-C-1 row provenance? | Line refs plus stale/current table. |
| Q2 | What stale/current claims exist in `03_pyreason_adapter.md` for T10-2-A/B and T10-3-A/B? | Line refs plus stale/current table. |
| Q3 | Where should T10-1 C76 `uncertainty_projection` be taught in ProbLog adapter docs? | Insert/rewrite points with line refs. |
| Q4 | Where should T8-C-1 ProbLog row provenance and `engine_meta["problog"]` be taught? | Insert/rewrite points with line refs. |
| Q5 | Where should the five PyReason canonical axes be taught in PyReason adapter docs? | Insert/rewrite points with line refs. |
| Q6 | Should `03_pyreason_adapter.md` mention `pyreason_trace_to_evidence_graph(...)`, and if so how? | Source-backed yes/no plus wording strategy. |
| Q7 | Are adapter docs consistent with T8-D round 1-5 quickstarts? | Difference list and leave-alone decisions. |
| Q8 | Should implementation be one docs commit or one commit per engine? | Source-backed split decision. |
| Q9 | Do any stop/amend triggers fire? | Trigger-by-trigger assessment. |

## 5. Existing Invariants To Preserve

- T10-1 C76 ProbLog `uncertainty_projection` shipped behavior.
- T10-2-A C78 PyReason `iteration_count` shipped behavior.
- T10-2-B C74 PyReason `derived_bound` / `atom_bounds` shipped behavior.
- T10-3-A C77 PyReason `fact_boundaries` shipped behavior.
- T10-3-B C77 PyReason `time_binned` shipped behavior.
- T8-C-1 ProbLog row provenance behavior, including `PROBLOG_PROVENANCE_KIND`,
  `EDGE_DERIVES`, and namespaced `engine_meta["problog"]`.
- T8-D round 1/2/3/4/5 user quickstart teaching.
- `pyreason_trace_to_evidence_graph(...)` signature and import path.
- `_validate_row_provenance_envelopes` protocol gate,
  `_FORM1_ROW_SUPPORT_KINDS`, and row-evidence fallback behavior.
- D11 / Form 2 schema remains fully deferred.
- Current single-conclusion fallback for PyReason rows.
- `Inference`, `Query`, `Branch`, and `Pred` DSL runtime classes.
- C110 / C119 / C136 / D11 / D13 / Nemo / Form 2 deferred state.
- 13 archive lockout set named in §0.
- Sacred `master = 562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline `4 M + 1 D + 6 U`.

## 6. Inventory Plan

```bash
rg -n "uncertainty_projection|raw_kind|bound|PROBLOG_PROVENANCE_KIND|EDGE_DERIVES|engine_meta|provenance|probability|possibility" src/factgraph/adapters/docs/02_problog_adapter.md src/factgraph/adapters src/factgraph/application/protocol tests
rg -n "iteration_count|derived_bound|atom_bounds|head_bound|branch_bounds|fact_boundaries|valid_time_boundaries|time_binned|bin_size|pyreason_trace_to_evidence_graph|timeline|Form 2" src/factgraph/adapters/docs/03_pyreason_adapter.md src/factgraph/adapters/pyreason src/factgraph/core/semantics src/factgraph/sdk tests
rg -n "uncertainty_projection|raw_kind|bound|derived_bound|atom_bounds|fact_boundaries|time_binned|PyReason|ProbLog|row evidence|single-`NODE_CONCLUSION`" docs/official/kernel/quickstart src/factgraph/sdk/docs/00_user_guide.en.md
rg -n "pyreason_trace_to_evidence_graph|def pyreason_trace_to_evidence_graph|candidate_id|candidate_payload" src/factgraph/adapters/pyreason/provenance.py src/factgraph/adapters/docs/03_pyreason_adapter.md
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration tests.test_problog_semantics_profile_migration tests.test_audit_evidence_graph
PYTHONPATH=src python -m unittest discover tests
git diff --check
git status --short --branch
git rev-parse master
```

## 7. Implementation Split

Candidate chain:

1. `docs(adapters): align ProbLog adapter module docs with shipped runtime`
2. Optional separate commit:
   `docs(adapters): align PyReason adapter module docs with shipped runtime`
3. `docs(blueprint): close adapter module docs alignment`
4. `docs(blueprint): archive adapter module docs alignment`

Step 4.6 decides whether implementation should be one docs commit or one commit
per engine. If both files require small independent edits, a single commit may
be acceptable. If either file has a larger rewrite, split by engine for review
clarity.

## 8. Acceptance Checklist

- [ ] Step 4.2 review completed.
- [ ] Step 4.6 source-backed inventory completed.
- [ ] Q1-Q9 answered.
- [ ] `02_problog_adapter.md` aligned with T10-1 and T8-C-1 shipped behavior.
- [ ] `03_pyreason_adapter.md` aligned with T10-2-A/B, T10-3-A/B, and T8-D
      round 5 boundaries.
- [ ] Quickstart docs left untouched.
- [ ] Runtime, tests, governance, audit docs, dirty baseline, and untracked
      design-point files untouched.
- [ ] No Form 2 schema details introduced.
- [ ] 13 archive lockout preserved.
- [ ] Focused docs-only baseline passes.
- [ ] Full discover compared against `2038 tests / 72 failures / 231 errors`.
- [ ] `git diff --check` clean.
- [ ] Sacred master and dirty baseline preserved.

## 9. Verification Commands

```bash
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration tests.test_problog_semantics_profile_migration tests.test_audit_evidence_graph
PYTHONPATH=src python -m unittest discover tests
git diff --check
git status --short --branch
git rev-parse master
```

## 10. Outcome / Deviations

Pending Step 4.6 / implementation / closure.
