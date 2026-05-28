# Audit: Adapter Module Docs Alignment

- Status: implemented
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/archive/2026-05-28_adapter-module-docs-alignment.md`
- Stage: implemented
- Class: S (docs-only)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 6 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | this commit | Adapter module docs alignment blueprint pair drafted | Triggered by T8-D round 4/5 named future work, completed T10 shipped semantics, completed T8-C-1 ProbLog row provenance, and user direction to align only `02_problog_adapter.md` / `03_pyreason_adapter.md`. |
| 2026-05-28 | scoped | pending commit | Step 4.6 source-backed inventory completed | Found bounded adapter-doc drift in `02_problog_adapter.md` and `03_pyreason_adapter.md`; no stop/amend triggers; focused `140 OK`; full discover baseline remains `2038 / 72F / 231E`. |
| 2026-05-28 | implemented | pending commit | Step 4.7 implementation accepted | Two adapter-doc commits aligned ProbLog and PyReason module docs; focused `140 OK`; full discover remained `2038 / 72F / 231E`; sacred and dirty baseline preserved. |

## 2. Draft Source Scan

Read-only orientation from the user telegraph and recent session source-back:

- T8-D round 4 and T8-D round 5 both left adapter module docs as named future
  work while keeping quickstart docs in scope.
- T10-1 C76, T10-2-A C78, T10-2-B C74, T10-3-A C77 alias, and T10-3-B C77
  `time_binned` are pushed runtime behavior.
- T8-C-1 ProbLog row provenance is pushed runtime behavior.
- T8-D round 5 closed the user-facing PyReason evidence deferred-state gap:
  T10 PyReason inference semantics are shipped, but rich row-level temporal
  evidence remains deferred to future Form 2 design.
- This cycle should inspect adapter module docs independently before editing;
  draft text does not assume which lines are stale.

This draft scan is not a Step 4.6 answer. Step 4.6 must independently verify
line refs, source behavior, and quickstart consistency before implementation.

## 2A. Step 4.6 Scoped Findings

### ProbLog

`02_problog_adapter.md` needs bounded alignment with shipped C76 and T8-C-1:

- `:75-122` covers the evaluate workflow but omits C76
  `uncertainty_projection` input and projection decisions.
- `:124-199` still emphasizes lower-level candidate provenance / converter
  wording and needs a row-result ProbLog provenance note.
- `:200-268` already describes raw `raw_kind` / `bound`, engine-native
  `problog/semantic/probability`, branch probabilities, and wrapper lowering,
  but it needs default reject and point-policy details for raw uncertainty.
- `:329-349` still says the adapter only commits a flat candidate provenance
  envelope and no generated candidate evidence tree / summary / narrative / NL;
  update this to distinguish row-result provenance from lower-level candidate
  surfaces.

Runtime source-back:

- `ProbLogSemantics.uncertainty_projection`: `src/factgraph/sdk/semantics.py:120-169`.
- Export projection policies: `src/factgraph/adapters/problog/problog_export.py:229-350`.
- Engine propagation into provenance payload: `src/factgraph/adapters/problog/engine_eval.py:98-117`.
- Row-result provenance graph: `src/factgraph/application/protocol/evaluate_result.py:887-989`.

### PyReason

`03_pyreason_adapter.md` needs bounded alignment with shipped C78/C74/C77 and
T8-D round 5:

- `:250-284` is stale for public wrapper fields: update to
  `iteration_count`, `derived_bound`, `atom_bounds`, `temporal_projection`,
  and compatibility surfaces.
- `:313-402` needs public wrapper/profile route updates plus the C78 dual
  default warning (`PyReasonSemantics()` lowers to `iteration_count=1`; direct
  no-profile adapter runs keep `timesteps=2`).
- `:403-451` needs `fact_boundaries` and `time_binned` in the temporal table,
  plus public `atom_bounds` to internal `body_atom:0:<index>` conversion
  framing.
- `:536-632` may keep the adapter-level timeline helper, but it must be
  clearly advanced/module-level and not row-result Form 2.
- `:634-657` needs limitations updated to the current shipped evaluation
  surface and evidence boundary.

Runtime source-back:

- `PyReasonSemantics` fields / validation:
  `src/factgraph/sdk/semantics.py:172-245`.
- SDK lowering and C74 atom-id conversion:
  `src/factgraph/sdk/store.py:3440-3466` and `:3479-3539`.
- `SemanticsProfile` carriers and temporal modes:
  `src/factgraph/core/semantics/profile.py:40-47` and `:165-250`.
- Adapter temporal / conflict consumption:
  `src/factgraph/adapters/pyreason/engine_eval.py:282-410`.
- Valid-time and binned materializers:
  `src/factgraph/adapters/pyreason/engine_eval.py:421-456` and `:459-570`.
- Advanced helper signature and candidate payload requirements:
  `src/factgraph/adapters/pyreason/provenance.py:113-119` and `:339-359`.

### Cross-Doc / Boundary

- Quickstarts are already aligned and stay untouched:
  `docs/official/kernel/quickstart/semantics.md:139-278` and
  `docs/official/kernel/quickstart/evidence.md:283-310`.
- SDK guide is already aligned and stays untouched:
  `src/factgraph/sdk/docs/00_user_guide.en.md:634-681` and `:1028-1105`.
- Protocol source confirms PyReason row-level rich evidence remains deferred:
  ProbLog-only row provenance gate at
  `src/factgraph/application/protocol/evaluate_result.py:1221-1240`, native /
  Souffle Form 1 kinds at `:81-82`, adapter support partition in
  `src/factgraph/core/store/_support.py:13-20`, and single-conclusion fallback
  at `src/factgraph/application/protocol/evaluate_result.py:857-884`.

Verification:

- Focused docs-only baseline:
  `PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration tests.test_problog_semantics_profile_migration tests.test_audit_evidence_graph`
  → `Ran 140 tests ... OK`.
- Full discover baseline:
  `PYTHONPATH=src python -m unittest discover tests` → `Ran 2038 tests` with
  baseline `72 failures / 231 errors`.
- `git diff --check` clean.

No stop/amend trigger fires. Implementation should split into one docs commit
per engine.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | What stale/current claims exist in `02_problog_adapter.md` for T10-1 C76 and T8-C-1 row provenance? | Answered in §2A: C76 projection and row-result provenance framing are stale; raw carrier and branch-probability wording are mostly current. |
| Q2 | What stale/current claims exist in `03_pyreason_adapter.md` for T10-2-A/B and T10-3-A/B? | Answered in §2A: wrapper fields, temporal modes, dual default, and evidence boundary are stale; adapter-local target/helper details are partly current. |
| Q3 | Where should T10-1 C76 `uncertainty_projection` be taught in ProbLog adapter docs? | Workflow, semantic-delivery, and export convention sections. |
| Q4 | Where should T8-C-1 ProbLog row provenance and `engine_meta["problog"]` be taught? | EvidenceGraph addendum and limitations, source-backed to protocol row builder. |
| Q5 | Where should the five PyReason canonical axes be taught in PyReason adapter docs? | Wrapper / execution / runtime options / semantics profile / limitations sections. |
| Q6 | Should `03_pyreason_adapter.md` mention `pyreason_trace_to_evidence_graph(...)`, and if so how? | Yes, as an advanced adapter-level helper, not row-result quickstart or Form 2 contract. |
| Q7 | Are adapter docs consistent with T8-D round 1-5 quickstarts? | Quickstarts are current; adapter docs lag and can be fixed without touching quickstarts. |
| Q8 | Should implementation be one docs commit or one commit per engine? | One commit per engine. |
| Q9 | Do any stop/amend triggers fire? | No. |

## 4. Risk Register

| Risk | Impact | Check |
|---|---|---|
| Adapter docs teach shipped runtime incorrectly | Advanced users follow stale adapter behavior | Step 4.6 source-back every teaching point to archives and current source. |
| Form 2 schema details leak into PyReason adapter docs | Deferred schema becomes accidentally user-committed | Reuse T8-D round 5 neutral future-Form-2 wording; avoid timestep/window/update/component identity design. |
| Adapter docs contradict T8-D quickstarts | Module docs and user docs diverge | Cross-doc sweep T8-D round 1-5 quickstarts before editing. |
| `pyreason_trace_to_evidence_graph(...)` wording conflicts with quickstart | Helper is framed too public or with wrong signature | Source-back signature/import path and keep wording advanced/module-level. |
| File scope expands beyond two adapter docs | S docs-only cycle becomes broad docs rewrite | Hard file cap in scope and Step 4.6 leave-alone table. |
| Inference/evidence/temporal semantics are conflated | Users mistake shipped inference for shipped row-evidence timeline | Keep T8-D round 5 distinction: T10 inference shipped, row-level rich temporal evidence deferred. |
| Runtime, tests, or governance touched | Workflow violation | Diff-scope checks before closure. |
| Dirty baseline or design-point files absorbed | Workflow violation | Preserve `4 M + 1 D + 6 U`; design-point intake remains out of scope. |
| 13 archive lockout contradicted | Historical docs lose auditability | Stop/amend if Step 4.6 finds contradiction with an archive. |

## 5. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q9 answered.
- [x] ProbLog adapter docs target map reviewed.
- [x] PyReason adapter docs target map reviewed.
- [x] Quickstart consistency sweep reviewed.
- [x] Form 2 deferred boundary reviewed.
- [x] File-scope decision reviewed.
- [x] Focused docs-only verification baseline reviewed.
- [x] Closure notes filled.

## 6. Closure Notes

Implementation:

- `dd8a5a2f` updated `src/factgraph/adapters/docs/02_problog_adapter.md`:
  - added C76 `uncertainty_projection` default reject and policy details;
  - connected raw `raw_kind` / `bound` projection to ProbLog point export;
  - aligned row-result ProbLog provenance with `PROBLOG_PROVENANCE_KIND`,
    `derives` edges, and namespaced `engine_meta["problog"]`;
  - clarified adapter-level candidate/static provenance remains distinct from
    public row-result evidence.
- `601e6ec0` updated `src/factgraph/adapters/docs/03_pyreason_adapter.md`:
  - replaced stale wrapper-field wording with canonical
    `iteration_count`, `derived_bound`, `atom_bounds`, and temporal projection
    fields;
  - documented C78 dual default and timesteps conflict behavior;
  - documented C74 public atom ids and internal `body_atom:0:<index>`
    conversion without reusing evidence witness keys;
  - added C77 `fact_boundaries` and `time_binned` details, including strict
    `bin_size` forms and exact universe divisibility;
  - aligned adapter-level helper wording with T8-D round 5's deferred
    row-evidence boundary.

Verification:

- Focused docs-only baseline: `Ran 140 tests ... OK`.
- Full discover: `Ran 2038 tests` with expected `72 failures / 231 errors`.
- `git diff --check` clean.
- Sacred `master` remained `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remained `4 M + 1 D + 6 U`.

Scope notes:

- Quickstart docs, SDK guide, audit docs, runtime, tests, governance, and
  untracked design-point files were not touched.
- No Form 2 schema details were introduced.
- 13 archive lockout remained intact.
