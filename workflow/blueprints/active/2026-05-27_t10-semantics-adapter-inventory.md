# Task Blueprint: T10 Semantics Adapter Execution Inventory

- Status: scoped
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: S/M (design-only planning inventory)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_t10-semantics-adapter-inventory.audit.md`
- Trigger: T8-C inventory completed and identified T10 / engine-specific semantics locks as the gate for T8-C-1 ProbLog and T8-C-2 PyReason.

## 0. Scope Locks

### In scope

This is a **T10 pre-implementation inventory cycle**, not T10 runtime
implementation. It should quantify the shipped / partial / missing state of
C74 / C76 / C77 / C78 before any adapter-touching blueprint starts.

Candidate planning outputs:

1. Source-backed inventory of C74 PyReason `PyReasonRuleParams` fields:
   `derived_bound`, `atom_bounds`, and `timestep_delay`.
2. Source-backed inventory of C76 ProbLog uncertainty projection across its
   three promised layers: SDK shell, SemanticsProfile lowering, and adapter
   consumption of `raw_kind + bound`.
3. Source-backed inventory of C77 temporal projection modes: `none`,
   `fact_boundaries`, and `time_binned`.
4. Source-backed inventory of C78 PyReason `iteration_count`.
5. Independent verification of the reviewer due-diligence findings that C77 is
   partially implemented and C76 adapter consumption is missing.
6. T10 sub-cycle split decision: per-C-id, per-engine, per-axis, or another
   explicitly scoped split.
7. Per-C-id dependency map: C74/C78 coupling, C77/C78 temporal-vs-iteration
   separation, and C76 independence.
8. T8-C unblock map, reusing and verifying the T8-C inventory dependency
   matrix.
9. SemanticsProfile field-shape inventory: whether each C-id needs schema
   extension or only adapter consumption of existing fields.
10. C74 atom-bounds key convention inventory and C77 rename/migration policy.
11. Evidence engine-meta cross-link decision for future T8-C.
12. Output-shape decision for this planning result.

### Out of scope

- Any runtime code changes.
- Any test code changes.
- Drafting the actual T10 sub-cycle implementation blueprints.
- T8-C-1 / T8-C-2 implementation.
- D20 match witness, failed graph, why-not, counterfactual, service/OpenAPI,
  Database/view, match API, or `fg.eval.run` deletion.
- SDK API shape changes.
- Release machinery, PyPI, tags, or dirty-baseline cleanup.
- Rewriting adapter `engine_eval` modules wholesale.
- Weakening T8-A, T8-B, T8-D, or T8-C-inventory invariants.
- Extending `EvidenceGraph` DTO schema.

### Stop / amend triggers

Pause and amend before closure if Step 4.6 shows:

- The reviewer C77 partial-implementation finding is materially wrong: C77 is
  either fully shipped or not implemented at all.
- The reviewer C76 adapter-consumption gap finding is materially wrong:
  ProbLog adapter already consumes uncertainty projection `raw_kind + bound`.
- A C-id requires an `EvidenceGraph` schema change or top-level 14-key metadata
  contract change.
- T10 invalidates the T8-C-1 / T8-C-2 gating model from the archived T8-C
  inventory.
- Any planning item attempts to edit runtime, tests, dirty baseline files, or
  user-facing docs.

## 1. Problem

T10 is the adapter-execution semantics lane that now gates the remaining
T8-C engine-enrichment implementation. C74/C76/C77/C78 are not uniform: some
may already have wrappers or partial adapter substrate, while others may be
missing at the adapter-consumption layer.

Before opening a runtime T10 blueprint, we need a source-backed map of current
SemanticsProfile fields, SDK wrapper surfaces, adapter consumption behavior,
and dependency boundaries.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:1599-1603` | Canonical C74/C76/C77/C78 definitions. |
| `workflow/design/design-points/active/post-t5-completion-roadmap.zh.md` §3.6 / §6 | T10 anchors, class warning, and C-id reactivation triggers. |
| `workflow/blueprints/archive/2026-05-27_t8-c-engine-enrichment-inventory.md` §4.2 | T10 -> T8-C dependency matrix to verify and reuse. |
| `workflow/blueprints/archive/2026-05-26_t5-8-semantics-lite-wrapper-fix.md` | Recent semantics-lite wrapper behavior and deferred adapter-touching context. |
| `src/factgraph/core/semantics/profile.py` | SemanticsProfile field inventory for C74/C76/C77/C78. |
| `src/factgraph/adapters/problog/engine_eval.py` | ProbLog adapter execution and uncertainty-consumption target. |
| `src/factgraph/adapters/pyreason/engine_eval.py` | PyReason adapter execution, temporal projection substrate, and iteration target. |
| Existing semantics / adapter tests | Verification surfaces for future T10 sub-cycles. |

## 3. Step 4.6 Inventory Results

### 3.1 Design anchors

| Anchor | Finding |
|---|---|
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:1599-1603` | C74/C76/C77/C78 canonical definitions. C76 explicitly has three layers: SDK shell, lower to `SemanticsProfile`, and ProbLog adapter consumption of `raw_kind + bound`, with the adapter layer marked currently unimplemented. |
| `workflow/design/design-points/active/post-t5-completion-roadmap.zh.md:250-265` | T10 is adapter-touching semantics work and may be L-class unless narrowed to one engine / one wrapper field. |
| `workflow/design/design-points/active/post-t5-completion-roadmap.zh.md:376-379` | Reactivation triggers: C74 PyReason bounds / delay, C76 raw-kind projection, C77 time-binned or fact-boundary runtime use, and C78 multi-round PyReason inference. |
| `workflow/blueprints/archive/2026-05-27_t8-c-engine-enrichment-inventory.md` §4.2 | Baseline T8-C dependency matrix remains directionally correct: C76 gates T8-C-1 ProbLog; C74/C77 gate T8-C-2 PyReason; C78 is conditional for multi-round PyReason enrichment. |

### 3.2 Source-backed shipped-state table

| C-id | SDK wrapper | `SemanticsProfile` / lowering | Adapter consumption | Classification |
|---|---|---|---|---|
| C74 PyReason params | `PyReasonSemantics` has legacy `timestep_delay`, `head_bound`, and `branch_bounds` at `src/factgraph/sdk/semantics.py:133-138`; it does not expose canonical `derived_bound` / `atom_bounds`. | SDK lowering writes `head:0`, `branch:<index>`, and `rule` projection entries at `src/factgraph/sdk/store.py:3417-3436`. | `resolve_pyreason_engine_ext(...)` consumes profile rule projection and materializes legacy `head_bound`, `body_predicate_bounds`, and `timestep_delay` in `src/factgraph/adapters/pyreason/rule_ext.py:138-229`. | **Partial / legacy**. `timestep_delay` is shipped; `derived_bound` is currently `head_bound`; `atom_bounds` are not keyed by full atom id. |
| C76 ProbLog uncertainty projection | `ProbLogSemantics` has `branch_probabilities` and `rule_params` only at `src/factgraph/sdk/semantics.py:73-114`; no `uncertainty_projection` shell field. | Core `SemanticsProfile.uncertainty_projection` exists at `src/factgraph/core/semantics/profile.py:43` and normalizes raw-kind keys at `:128-147`; ProbLog lowering at `src/factgraph/sdk/store.py:3385-3414` only produces `rule_projection.problog` branch probabilities. | `evaluate_problog(...)` resolves only rule extension and timeout at `src/factgraph/adapters/problog/engine_eval.py:45-51`; grep finds no `uncertainty_projection` consumption in the adapter. | **Missing for C76**, with only generic core carrier substrate shipped. |
| C77 temporal projection | `PyReasonSemantics.temporal_projection` exists at `src/factgraph/sdk/semantics.py:137` and is copied at `:167-170`. | `SemanticsProfile.temporal_projection` exists at `src/factgraph/core/semantics/profile.py:44`; supported modes are `none`, `fixed_timesteps`, and `valid_time_boundaries` at `:150-168`. It does not support canonical `fact_boundaries` or `time_binned`. | PyReason consumes `fixed_timesteps` and `valid_time_boundaries` in `_resolve_temporal_projection_state(...)` at `src/factgraph/adapters/pyreason/engine_eval.py:297-324`, materializing valid-time boundaries at `:354-389`. | **Partial / legacy**. `none` shipped; legacy `valid_time_boundaries` shipped; canonical `fact_boundaries` rename and `time_binned` are missing. |
| C78 PyReason iteration count | No `iteration_count` in `PyReasonSemantics` at `src/factgraph/sdk/semantics.py:133-140`. | No `iteration_count` field in `SemanticsProfile` at `src/factgraph/core/semantics/profile.py:39-48`. | PyReason runtime already derives timesteps from legacy `fixed_timesteps` / engine options at `src/factgraph/adapters/pyreason/engine_eval.py:327-336`, but does not consume a canonical `iteration_count`. | **Missing**, with legacy timestep substrate to migrate away from C77. |

### 3.3 Reviewer finding verification

Reproducible grep/source checks:

- C77 partial finding is accurate but needs refinement: PyReason has shipped
  temporal substrate under legacy names. `rg
  'temporal_projection|fact_boundaries|valid_time_boundaries|time_binned'
  src/factgraph/adapters/pyreason src/factgraph/core/semantics
  src/factgraph/sdk tests/test_pyreason_semantics_profile_migration.py` finds
  `fixed_timesteps` and `valid_time_boundaries` throughout
  `profile.py:150-168`, `engine_eval.py:297-324`, and
  `tests/test_pyreason_semantics_profile_migration.py:270-409`, but no
  canonical `fact_boundaries` / `time_binned` implementation.
- C76 adapter gap finding is accurate and stronger than the initial hint:
  `ProbLogSemantics` lacks an SDK `uncertainty_projection` field
  (`src/factgraph/sdk/semantics.py:73-114`), ProbLog lowering omits it
  (`src/factgraph/sdk/store.py:3385-3414`), and the adapter only consumes
  rule probabilities through `resolve_problog_engine_ext(...)`
  (`src/factgraph/adapters/problog/engine_eval.py:45-51`;
  `src/factgraph/adapters/problog/rule_ext.py:72-117`). Existing
  `raw_kind` / `bound` occurrences in the SDK grep are row explanation fields,
  not ProbLog uncertainty projection consumption.

### 3.4 T10 split decision

| Option | Shape | Estimate | Risk / rationale |
|---|---|---:|---|
| A. Per-C-id: four cycles C76 / C74 / C77 / C78 | Exact traceability to commitments. | C76 M; C74 M; C77 M/L; C78 S/M | Too fragmented around PyReason: C74/C77/C78 touch the same wrapper/profile/adapter surfaces and migration policy. |
| B. Per-engine: ProbLog C76, then PyReason C74+C77+C78 | Engine-local implementation and tests. | ProbLog M; PyReason L | PyReason bundle is likely too large because it mixes canonical params, temporal rename, time-binned mode, and iteration migration. |
| C. Per-axis: uncertainty, rule params, temporal lifecycle, iteration | Aligns with semantics domains. | Similar to A | Useful for design analysis but still splits PyReason into coupled migrations. |
| **D. Staged hybrid (selected)** | **T10-1 ProbLog C76 full three-layer ship; T10-2 PyReason C74 + C78 canonical shell/migration; T10-3 PyReason C77 temporal rename + time-binned.** | **T10-1 M; T10-2 M; T10-3 M/L** | Best balance: unblocks T8-C-1 first, keeps PyReason canonical API migration separate from more complex temporal runtime behavior, and preserves shipped legacy substrates until explicit migration. |

### 3.5 T8-C unblock map

| T8-C slice | T10 dependency after this inventory | Unblock rule |
|---|---|---|
| T8-C-1 ProbLog metadata bridge / enrichment | C76 | Requires **full C76 ship**: SDK shell, lowering, and adapter consumption. Generic `SemanticsProfile.uncertainty_projection` alone is not enough. |
| T8-C-2 PyReason enrichment | C74 + C77; C78 conditional | Requires C74 canonical atom/bound semantics and C77 canonical temporal policy. C78 is required if the PyReason enrichment slice exposes multi-round inference; otherwise it gates a later PyReason enrichment sub-slice. |

### 3.6 C-id dependency notes

- C76 is independent from C74/C77/C78 and should be first because it is the
  narrowest direct T8-C-1 unblocker.
- C74 and C78 are adapter-local PyReason changes but conceptually independent:
  C74 maps rule atom/head bounds and delay; C78 maps inference round count.
- C77 and C78 are conceptually orthogonal per C78, but current shipped
  `fixed_timesteps` couples round count into `temporal_projection`. T10 must
  decouple that legacy behavior by migrating `fixed_timesteps` toward
  `iteration_count` while keeping an explicit compatibility policy.
- C74 atom ids are not aligned today: application `Rule.atom_ids` use
  `<rule_id>:atom_<index>` (`src/factgraph/application/protocol/rule.py:99-100`;
  `tests/application/protocol/test_rule.py:119-126`), current PyReason lowering
  uses `body_atom:{branch}:{atom}` targets (`src/factgraph/sdk/store.py:3424-3433`),
  and T8-B witness keys use `b<n>.a<n>:pred_id`
  (`src/factgraph/core/store/_support.py:201-210`). Future C74 should add a
  conversion layer rather than reuse T8-B witness atom keys.

### 3.7 Output shape

Selected output shape: **blueprint-only split plan**. A design-point note would
duplicate source-backed inventory and risks becoming implementation design
before T10 sub-cycles are opened. The archived blueprint/audit pair is the
durable planning artifact, matching the T8-C inventory pattern.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | What is the shipped state of C74 PyReason `PyReasonRuleParams` fields? | Partial / legacy: `timestep_delay` ships end-to-end; `derived_bound` is currently legacy `head_bound`; `atom_bounds` are currently legacy branch/body targets, not full atom ids. |
| Q2 | What is the shipped state of C76's three-layer ProbLog promise? | Core `SemanticsProfile.uncertainty_projection` substrate ships, but the C76 SDK shell, SDK lowering, and ProbLog adapter `raw_kind + bound` consumption are missing. |
| Q3 | What is the shipped state of C77's three temporal projection modes? | `none` ships; legacy `valid_time_boundaries` ships; canonical `fact_boundaries` and `time_binned` are missing. |
| Q4 | What is the shipped state of C78 `iteration_count`? | Missing as SDK/profile field and adapter consumer; legacy `fixed_timesteps` / engine-options timesteps are separate substrate to migrate. |
| Q5 | Are the reviewer findings accurate? | Yes, with refinement: C77 is partial under legacy names; C76 adapter gap is accurate and the SDK shell/lowering are also missing. |
| Q6 | How should T10 split? | Selected staged hybrid: T10-1 C76 ProbLog, T10-2 C74+C78 PyReason canonical shell/migration, T10-3 C77 PyReason temporal rename/time-binned. |
| Q7 | How does T10 unblock T8-C? | T8-C-1 requires full C76. T8-C-2 requires C74+C77; C78 gates multi-round PyReason enrichment. |
| Q8 | What are the dependencies between C74/C76/C77/C78? | C76 independent; C74/C78 conceptually independent but both PyReason; C77/C78 orthogonal by design but currently coupled by legacy `fixed_timesteps`. |
| Q9 | What is the C77 rename/migration policy? | Future T10-3 should accept canonical `fact_boundaries`, keep `valid_time_boundaries` as an explicit compatibility alias initially, and rename internal helper/docs around fact boundaries. |
| Q10 | What atom-id convention does C74 require and what is shipped today? | C74 requires full `<rule_id>:atom_<index>`; shipped PyReason lowering uses `body_atom:{branch}:{atom}` and T8-B witness keys use `b<n>.a<n>:pred_id`; future C74 needs a conversion layer. |
| Q11 | How should T10 fields relate to future evidence `engine_meta`? | T10 fields are adapter-execution inputs first. Future T8-C may expose selected namespaced `engine_meta.pyreason` / `engine_meta.problog` facts after runtime semantics ship. |
| Q12 | What durable output shape should this cycle produce? | Blueprint-only split plan. |
| Q13 | Are there stop/amend findings? | None for planning. Findings refine scope but do not invalidate T8-C gating or require runtime edits in this cycle. |

## 5. Existing Invariants To Preserve

- This cycle is design-only: no runtime/test/user-doc edits unless amended.
- T8-A metadata foundation remains current truth.
- T8-B native + Souffle Form 1 behavior remains current truth.
- T8-D native + Souffle user docs remain current truth.
- T8-C inventory split and gating decisions remain current truth unless this
  cycle explicitly records a source-backed correction.
- SemanticsProfile existing fields must not be silently reinterpreted.
- `EvidenceGraph` DTO schema and top-level 14-key metadata vocabulary are not
  changed.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains `4 M + 1 D + 3 U` and must not be touched.

## 6. Step 4.6 Inventory Plan

Step 4.6 must produce:

1. Exact source refs for C74/C76/C77/C78 in the parent design.
2. SemanticsProfile field inventory for all four C-ids.
3. PyReason wrapper / lowering / adapter consumption inventory for C74/C77/C78.
4. ProbLog wrapper / lowering / adapter consumption inventory for C76.
5. Independent verification of the reviewer C77/C76 findings.
6. T5.8 archive scan for partial ship records.
7. T8-C dependency update map.
8. Q1-Q13 answers with selected split and output shape.
9. No-op baseline result for relevant adapter/semantics tests.
10. Dirty/sacred status check.

## 7. Proposed Implementation Shape

This cycle is expected to have no runtime/test implementation commit. Likely
commits:

1. Draft blueprint/audit.
2. Scoped source-backed inventory.
3. Optional durable design note if Step 4.6 selects one.
4. Closure.
5. Archive.

## 8. Acceptance

- [x] Step 4.6 verifies or corrects the reviewer C77 partial / C76 gap findings
      with source refs.
- [x] Q1-Q13 are answered with file:line or section-anchor support.
- [x] C74/C76/C77/C78 shipped state is classified as shipped / partial /
      missing per relevant layer.
- [x] T10 split direction is locked or explicitly deferred.
- [x] T8-C unblock map is verified or corrected.
- [x] Output shape is selected.
- [x] No runtime/test/user-doc/dirty-baseline files are edited.
- [x] Focused no-op baseline is recorded and `git diff --check` is clean.
- [x] Sacred master and dirty baseline are preserved.

## 9. Verification Commands

Scoped checks:

```bash
PYTHONPATH=src python -m unittest \
  tests.test_problog_semantics_profile_migration \
  tests.test_pyreason_semantics_profile_migration \
  tests.test_problog_evidence_graph \
  tests.test_pyreason_evidence_graph
```

Current scoped baseline result: 46 tests run, 44 OK / 2 existing errors in
`tests.test_problog_semantics_profile_migration` caused by legacy
`meta[confidence]` writes rejected by the current write protocol. This cycle
does not edit runtime/tests, so the failures are recorded as pre-existing
adapter-semantics baseline drift. `git diff --check` is clean.

```bash
git diff --check
git status --short --branch
```

Step 4.6 may refine these commands after source-backed inventory.

## 10. Outcome / Deviations

Pending scoped inventory / closure.
