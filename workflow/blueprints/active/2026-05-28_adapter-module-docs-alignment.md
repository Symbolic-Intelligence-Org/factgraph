# Task Blueprint: Adapter Module Docs Alignment

- Status: scoped
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

## 3. Step 4.6 Source-Backed Inventory

### 3.1 ProbLog Adapter Doc Current State

`02_problog_adapter.md` is mostly current for branch probabilities and raw
`raw_kind` / `bound` carrier names, but it predates T10-1 C76 and T8-C-1 row
provenance integration:

| Lines | Current / stale | Step 4.7 action |
|---|---|---|
| `02_problog_adapter.md:75-122` | Current workflow covers branch-probability export, trace parsing, `support_kind="problog_provenance_v1"`, and pending probability annotation templates, but it does not mention C76 `uncertainty_projection` or projection decisions. | Extend the workflow around export / trace / provenance steps with C76 projection input and trace decision metadata. |
| `02_problog_adapter.md:124-163` | Stale candidate explainability wording still focuses on `explain_ref(kind="candidate")` and older tree-family projections. | Reframe as lower-level candidate provenance; do not claim this is the row-result shape. |
| `02_problog_adapter.md:164-199` | Current for the adapter-level `problog_trace_to_evidence_graph(...)` converter, but incomplete for row-result `EvaluateRow.explain()` provenance. | Add a row-result note pointing to `PROBLOG_PROVENANCE_KIND`, `derives` edges, and `engine_meta["problog"]`. |
| `02_problog_adapter.md:200-225` | Current for shared raw uncertainty annotations and `problog/semantic/probability`; missing C76 default reject / policy list. | Add default reject plus supported point policies and interval-policy rejection. |
| `02_problog_adapter.md:228-268` | Current for deterministic default `1.0`, `problog/semantic/probability`, branch probabilities, and `ProbLogSemantics` wrapper lowering. | Add `uncertainty_projection` as the raw uncertainty projection lane, separate from engine-native probability. |
| `02_problog_adapter.md:329-349` | Stale limitation says only runtime candidate provenance envelope and no auto-generated candidate evidence graph / summary / narrative / NL. | Update to distinguish row-result ProbLog provenance graph from lower-level candidate/static surfaces. |

Source-backed runtime behavior:

- `ProbLogSemantics.uncertainty_projection` is a public wrapper field with
  validation at `src/factgraph/sdk/semantics.py:120-169`.
- `evaluate_problog(...)` passes profile `uncertainty_projection` into
  `export_problog(...)` and carries `projection_decisions` into provenance at
  `src/factgraph/adapters/problog/engine_eval.py:98-117`.
- The exporter consumes paired `shared/semantic/raw_kind` and
  `shared/semantic/bound` at
  `src/factgraph/adapters/problog/problog_export.py:229-258`.
- `lower`, `midpoint`, `upper`, degenerate `identity_probability`, interval
  policy rejection, and fallback rejection are implemented at
  `src/factgraph/adapters/problog/problog_export.py:260-350`.
- ProbLog row provenance is built in
  `src/factgraph/application/protocol/evaluate_result.py:887-989`, with
  `support_kind=PROBLOG_PROVENANCE_KIND`, `derives` edges, and
  `engine_meta={"problog": ...}`.

### 3.2 PyReason Adapter Doc Current State

`03_pyreason_adapter.md` is current for many adapter internals, but stale for
the public canonical semantics added by T10-2 / T10-3 and for the row-evidence
boundary clarified in T8-D round 5:

| Lines | Current / stale | Step 4.7 action |
|---|---|---|
| `03_pyreason_adapter.md:250-284` | Current for adapter-local `PyReasonRuleExt` internals, but stale for public `PyReasonSemantics`: it lists `head_bound`, `temporal_projection`, and `uncertainty_projection`, omitting `iteration_count`, `derived_bound`, `atom_bounds`, and asymmetric C74 conflict behavior. | Rewrite wrapper paragraph to canonical-first fields and compatibility surfaces. |
| `03_pyreason_adapter.md:313-375` | Execution sequence is still useful, but it teaches old `sdk.evaluate(... mode=..., engine_options=...)` and only `valid_time_boundaries` timesteps derivation. | Add public wrapper / profile route and update temporal projection bullets without changing low-level adapter flow. |
| `03_pyreason_adapter.md:377-402` | Current for no-profile adapter default `timesteps=2`, but missing wrapper default `iteration_count=1` and conflict behavior. | Add C78 dual-default warning and explicit conflict with temporal timesteps carriers. |
| `03_pyreason_adapter.md:403-451` | Current rule-projection target table includes internal `body_atom:{branch}:{atom}` / `head:0` / `branch:{index}` / `rule`; temporal table omits `fact_boundaries` and `time_binned`. | Add public C74 mapping explanation and update temporal table to five modes. |
| `03_pyreason_adapter.md:536-632` | Current for adapter-level timeline converter shape, but not enough boundary text after T8-D round 5. | Keep as module-level advanced helper; explicitly state row-result rich temporal evidence remains future Form 2 / T8-C-2 work. |
| `03_pyreason_adapter.md:634-657` | Stale limitations include pending rule registry / builder integration and no auto-generated candidate evidence graph wording. | Update to shipped evaluation surface and current PyReason evidence boundary. |

Source-backed runtime behavior:

- `PyReasonSemantics` fields and validation live at
  `src/factgraph/sdk/semantics.py:172-245`, including
  `iteration_count`, `derived_bound`, `atom_bounds`, `head_bound`,
  `branch_bounds`, `temporal_projection`, and conflict validation.
- Wrapper lowering maps `iteration_count`, canonical bounds, and temporal
  projection into `SemanticsProfile` at
  `src/factgraph/sdk/store.py:3440-3466`.
- C74 lowering maps `derived_bound` / `head_bound` to `head:0`, maps
  `<rule_id>:atom_<index>` into `body_atom:0:<index>`, and rejects missing or
  unknown application atom ids at `src/factgraph/sdk/store.py:3479-3539`.
- `SemanticsProfile` carries top-level `iteration_count` and
  `temporal_projection` at `src/factgraph/core/semantics/profile.py:40-47`.
- Supported temporal modes now include `none`, `fixed_timesteps`,
  `valid_time_boundaries`, `fact_boundaries`, and `time_binned` at
  `src/factgraph/core/semantics/profile.py:165-190`.
- `time_binned.bin_size` validation accepts only `P<n>D`, `PT<n>H`,
  `PT<n>M`, `1d`, `1h`, `15m`, and `1m` at
  `src/factgraph/core/semantics/profile.py:237-250`.
- Adapter consumption resolves `iteration_count`, `fact_boundaries`, and
  `time_binned` with dynamic carriers and conflict checks at
  `src/factgraph/adapters/pyreason/engine_eval.py:282-410`.
- `valid_time_boundaries` / `fact_boundaries` use the existing boundary
  materializer at `src/factgraph/adapters/pyreason/engine_eval.py:421-456`;
  `time_binned` uses the new exact-bin materializer at
  `src/factgraph/adapters/pyreason/engine_eval.py:459-570`.
- `pyreason_trace_to_evidence_graph(...)` is importable from
  `factgraph.adapters.pyreason.provenance` with signature
  `(trace, *, candidate_id, candidate_payload, support_kind=...)` at
  `src/factgraph/adapters/pyreason/provenance.py:113-119`; candidate payload
  requirements are enforced at `src/factgraph/adapters/pyreason/provenance.py:339-359`.

### 3.3 ProbLog Teaching Plan

Step 4.7 will edit only `02_problog_adapter.md` for ProbLog:

- Update the header date and responsibilities to include row-result provenance
  and raw uncertainty projection; remove over-specific accepted-candidate
  persistence framing where it implies the only output path.
- In the typical workflow, add that `SemanticsProfile.uncertainty_projection`
  is passed into export and projection decisions are copied into the proof-trace
  payload.
- Add a small C76 subsection near the semantic-delivery / export sections:
  default rejects raw uncertainty, supported point policies are `lower`,
  `midpoint`, `upper`, and degenerate `identity_probability`; canonical interval
  policies remain rejected by ProbLog point export.
- Update the EvidenceGraph addendum to distinguish adapter-level trace
  conversion from row-result ProbLog provenance graphs. Row-result graphs use
  `PROBLOG_PROVENANCE_KIND`, `derives` edges, and namespaced
  `engine_meta["problog"]`.
- Update limitations to remove the stale claim that the adapter only commits a
  flat candidate provenance envelope.

### 3.4 PyReason Teaching Plan

Step 4.7 will edit only `03_pyreason_adapter.md` for PyReason:

- Update the Track 2 wrapper paragraph to canonical-first
  `PyReasonSemantics`: `iteration_count`, `derived_bound`, `atom_bounds`,
  `temporal_projection`, and legacy compatibility. Remove the stale
  implication that PyReason wrapper semantics are about `uncertainty_projection`.
- Add the C78 dual-default warning: `PyReasonSemantics()` lowers to
  `iteration_count=1`; direct no-profile adapter execution keeps
  `timesteps=2`.
- Explain C74 public vs internal targets: users write
  `<rule_id>:atom_<index>` for `atom_bounds`; the lowering converts to
  internal `body_atom:0:<index>` targets. Do not reuse evidence witness keys.
- Explain asymmetric compatibility: `derived_bound + head_bound` rejects, while
  `atom_bounds + branch_bounds` may coexist.
- Update temporal mode table with `fact_boundaries` as canonical valid-time
  spelling, `valid_time_boundaries` as legacy accepted spelling, and
  `time_binned` with the strict `bin_size` whitelist, exact universe
  divisibility, and timezone-aware datetime behavior.
- Keep `pyreason_trace_to_evidence_graph(...)` as an adapter-level advanced
  helper but align it with T8-D round 5: current row-result PyReason evidence
  remains the safe single-conclusion fallback until future Form 2 / T8-C-2
  bridge work lands.

### 3.5 Quickstart Consistency Sweep

Quickstart / SDK user-guide wording is already aligned and should remain
untouched:

| Source | Relevant current wording | Decision |
|---|---|---|
| `docs/official/kernel/quickstart/semantics.md:139-180` | T10-1 ProbLog `uncertainty_projection` default reject and policy list. | Adapter docs should mirror, not reopen. |
| `docs/official/kernel/quickstart/semantics.md:182-278` | T10-2/T10-3 PyReason canonical fields, temporal modes, and dual default warning. | Adapter docs may include module-level internals but must not contradict. |
| `docs/official/kernel/quickstart/evidence.md:283-310` | ProbLog row provenance and PyReason single-conclusion fallback / advanced helper boundary. | Adapter docs should reuse the same boundary. |
| `src/factgraph/sdk/docs/00_user_guide.en.md:634-681` | SDK guide summarizes ProbLog raw uncertainty, PyReason canonical fields, and future PyReason evidence tracks. | No SDK guide edit in this cycle. |
| `src/factgraph/sdk/docs/00_user_guide.en.md:1028-1105` | Transition guide already lists ProbLog and PyReason canonical semantics. | No SDK guide edit in this cycle. |

### 3.6 Form 2 / Evidence Boundary Sweep

No Form 2 schema details are needed. `03_pyreason_adapter.md` may keep
adapter-level timeline helper details because it is a module doc, but Step 4.7
must avoid committing row-result Form 2 schema details such as timestep schema,
time-window schema, bound update contract, component identity policy, producer /
consumer contract, or `EDGE_DERIVES` vs `EDGE_UPDATES` design choices.

Protocol source confirms the current boundary:

- Row provenance envelopes are currently restricted to ProbLog proof traces at
  `src/factgraph/application/protocol/evaluate_result.py:1221-1240`.
- Form 1 row support kinds are native and Souffle only at
  `src/factgraph/application/protocol/evaluate_result.py:81-82`.
- PyReason support kind is provenance-bearing at adapter/store level but not
  Form 1 row support at `src/factgraph/core/store/_support.py:13-20`.
- Rows without row-aligned provenance/support use the safe single-conclusion
  fallback at `src/factgraph/application/protocol/evaluate_result.py:857-884`.

### 3.7 Leave-Alone Table

| Area | Decision |
|---|---|
| `docs/official/kernel/quickstart/*` | Leave untouched; T8-D rounds 1-5 are already aligned. |
| `src/factgraph/sdk/docs/00_user_guide.en.md` | Leave untouched; it already contains the relevant summaries and future evidence-track boundary. |
| `src/factgraph/audit/docs/*` | Leave untouched; audit module docs are a separate future work item if needed. |
| Runtime under `src/factgraph/**.py` | Leave untouched. |
| Tests | Leave untouched. |
| Governance / workflow rules | Leave untouched except blueprint/audit status files and later archive/status roll-up. |
| Dirty baseline and untracked design-point files | Preserve exactly; no design-point intake in this cycle. |

## 4. Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | What stale/current claims exist in `02_problog_adapter.md` for T10-1 C76 and T8-C-1 row provenance? | See §3.1. Stale areas are C76 projection decisions and row-result provenance framing; current areas include branch-probability semantics and raw `raw_kind` / `bound` names. |
| Q2 | What stale/current claims exist in `03_pyreason_adapter.md` for T10-2-A/B and T10-3-A/B? | See §3.2. Stale areas are public wrapper fields, temporal mode list, dual-default warning, and evidence boundary framing; current areas include adapter-local rule projection targets and helper converter details. |
| Q3 | Where should T10-1 C76 `uncertainty_projection` be taught in ProbLog adapter docs? | Add / rewrite in workflow `:75-122`, semantic-delivery `:200-225`, and export conventions `:228-268`. |
| Q4 | Where should T8-C-1 ProbLog row provenance and `engine_meta["problog"]` be taught? | Update EvidenceGraph addendum `:164-199` and limitations `:329-349`; source-back to protocol builder `evaluate_result.py:887-989`. |
| Q5 | Where should the five PyReason canonical axes be taught in PyReason adapter docs? | Update wrapper / runner boundaries `:250-284`, runtime options `:377-402`, semantics profile consumption `:403-451`, and limitations `:634-657`. |
| Q6 | Should `03_pyreason_adapter.md` mention `pyreason_trace_to_evidence_graph(...)`, and if so how? | Yes. It is a module doc and the helper is importable at `factgraph.adapters.pyreason.provenance`. Keep it advanced / adapter-level and not the row-result quickstart path. |
| Q7 | Are adapter docs consistent with T8-D round 1-5 quickstarts? | Quickstarts are aligned; adapter docs lag. Step 4.7 must update adapter docs only and avoid reopening quickstarts. |
| Q8 | Should implementation be one docs commit or one commit per engine? | One commit per engine. ProbLog and PyReason have independent stale surfaces, and PyReason is materially larger. |
| Q9 | Do any stop/amend triggers fire? | No. All contradictions are adapter-doc drift fixable inside the two-file cap; no runtime, quickstart, Form 2 schema, or archive amendment is needed. |

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

Planned chain:

1. `docs(adapters): align ProbLog adapter module docs with shipped runtime`
2. `docs(adapters): align PyReason adapter module docs with shipped runtime`
3. `docs(blueprint): close adapter module docs alignment`
4. `docs(blueprint): archive adapter module docs alignment`

Step 4.6 selects one implementation commit per engine. The two targets are
independent, and the PyReason file has a larger stale surface; splitting keeps
Step 4.7 review readable.

## 8. Acceptance Checklist

- [x] Step 4.2 review completed.
- [x] Step 4.6 source-backed inventory completed.
- [x] Q1-Q9 answered.
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
