# Task Blueprint: T10 Semantics Adapter Execution Inventory

- Status: draft
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

## 3. Draft Source Scan

Draft orientation only:

- C74 defines PyReason per-rule params: `derived_bound`, `atom_bounds`, and
  `timestep_delay`, with `atom_bounds` keyed by full atom id.
- C76 defines `ProbLogSemantics.uncertainty_projection` and explicitly calls
  out three layers: SDK shell, SemanticsProfile lowering, and adapter
  consumption of `raw_kind + bound`.
- C77 defines temporal projection modes `none`, `fact_boundaries`, and
  `time_binned`, plus the rename from `valid_time_boundaries` to
  `fact_boundaries`.
- C78 defines PyReason `iteration_count` and explicitly separates it from fact
  temporal lifecycle.
- Reviewer due diligence found possible C77 partial substrate in PyReason
  `engine_eval.py` and a likely C76 ProbLog adapter-consumption gap. Step 4.6
  must verify or correct both findings with source refs.

This draft scan does not answer Q1-Q13. Step 4.6 must replace it with
source-backed file:line and section-anchor evidence.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | What is the shipped state of C74 PyReason `PyReasonRuleParams` fields? | Per-field status for `derived_bound`, `atom_bounds`, and `timestep_delay`, including SemanticsProfile presence and adapter consumption. |
| Q2 | What is the shipped state of C76's three-layer ProbLog promise? | Per-layer status: SDK shell, SemanticsProfile lowering, and adapter `raw_kind + bound` consumption. |
| Q3 | What is the shipped state of C77's three temporal projection modes? | Per-mode status for `none`, `fact_boundaries`, and `time_binned`, including rename/migration observations. |
| Q4 | What is the shipped state of C78 `iteration_count`? | Field presence, validation/default, and PyReason adapter consumption status. |
| Q5 | Are the reviewer findings accurate? | Source-backed verification or correction for C77 partial implementation and C76 missing adapter consumption. |
| Q6 | How should T10 split? | At least three split options with file/test/LOC/risk estimates and selected planning direction. |
| Q7 | How does T10 unblock T8-C? | Updated T8-C dependency map: which C-id must fully ship before T8-C-1 / T8-C-2 can start. |
| Q8 | What are the dependencies between C74/C76/C77/C78? | Per-C-id dependency matrix, including C74 <-> C78 and C77 <-> C78. |
| Q9 | What is the C77 rename/migration policy? | Decision on `valid_time_boundaries` -> `fact_boundaries`, aliases, and function naming. |
| Q10 | What atom-id convention does C74 require and what is shipped today? | Source-backed check against current PyReason lowering and T8-B atom key conventions. |
| Q11 | How should T10 fields relate to future evidence `engine_meta`? | Adapter-internal only vs future T8-C exposure policy. |
| Q12 | What durable output shape should this cycle produce? | Design-point note, blueprint-only split plan, or hybrid. |
| Q13 | Are there stop/amend findings? | None or explicit trigger with next action. |

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

- [ ] Step 4.6 verifies or corrects the reviewer C77 partial / C76 gap findings
      with source refs.
- [ ] Q1-Q13 are answered with file:line or section-anchor support.
- [ ] C74/C76/C77/C78 shipped state is classified as shipped / partial /
      missing per relevant layer.
- [ ] T10 split direction is locked or explicitly deferred.
- [ ] T8-C unblock map is verified or corrected.
- [ ] Output shape is selected.
- [ ] No runtime/test/user-doc/dirty-baseline files are edited.
- [ ] Focused no-op baseline and `git diff --check` pass.
- [ ] Sacred master and dirty baseline are preserved.

## 9. Verification Commands

Draft expected checks:

```bash
PYTHONPATH=src python -m unittest \
  tests.test_problog_evidence_graph \
  tests.test_pyreason_evidence_graph

git diff --check
git status --short --branch
```

Step 4.6 may refine these commands after source-backed inventory.

## 10. Outcome / Deviations

Pending scoped inventory / closure.
