# Audit: T10 Semantics Adapter Execution Inventory

- Status: scoped
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t10-semantics-adapter-inventory.md`
- Stage: scoped
- Class: S/M (design-only planning inventory)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current `4 M + 1 D + 3 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T10 inventory blueprint pair drafted | Triggered after T8-C inventory completed and identified C74/C76/C77/C78 as T8-C gates; Q1-Q13 intentionally pending for Step 4.6. |
| 2026-05-27 | scoped | pending | Source-backed T10 inventory completed | C77 partial substrate verified under legacy names; C76 gap verified and expanded to include missing ProbLog SDK shell/lowering; staged hybrid split selected. |

## 2. Step 4.6 Inventory Summary

Source-backed scoped findings:

- Parent C74/C76/C77/C78 definitions live in
  `rule-expression-and-proof-attempt.zh.md:1599-1603`.
- C74 is partial / legacy: `PyReasonSemantics.timestep_delay` ships
  (`src/factgraph/sdk/semantics.py:133-152`) and adapter consumption exists,
  while canonical `derived_bound` / `atom_bounds` and full atom-id keys are not
  shipped.
- C76 is missing at the C76-specific layers: generic
  `SemanticsProfile.uncertainty_projection` exists
  (`src/factgraph/core/semantics/profile.py:43,128-147`), but
  `ProbLogSemantics` has no `uncertainty_projection` shell field
  (`src/factgraph/sdk/semantics.py:73-114`), ProbLog SDK lowering omits it
  (`src/factgraph/sdk/store.py:3385-3414`), and the adapter consumes only
  rule probabilities (`src/factgraph/adapters/problog/engine_eval.py:45-51`).
- C77 is partial / legacy: `none`, `fixed_timesteps`, and
  `valid_time_boundaries` ship (`src/factgraph/core/semantics/profile.py:150-168`;
  `src/factgraph/adapters/pyreason/engine_eval.py:297-324`), while canonical
  `fact_boundaries` and `time_binned` are not shipped.
- C78 is missing: no `iteration_count` in `PyReasonSemantics` or
  `SemanticsProfile`; current timesteps behavior is legacy temporal projection
  substrate.

Reviewer due-diligence verification:

- C77 partial finding is accurate after refinement: partial runtime exists,
  but under old `valid_time_boundaries` / `fixed_timesteps` names.
- C76 adapter-consumption gap is accurate and broader than the initial hint:
  the ProbLog SDK shell and lowering layers are also missing for
  `uncertainty_projection`.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | What is the shipped state of C74 PyReason params? | Answered: partial / legacy; `timestep_delay` shipped, canonical `derived_bound` / `atom_bounds` missing. |
| Q2 | What is the shipped state of C76's three-layer ProbLog promise? | Answered: generic core carrier shipped; C76 SDK shell, lowering, and adapter consumption missing. |
| Q3 | What is the shipped state of C77's three temporal projection modes? | Answered: `none` shipped; legacy `valid_time_boundaries` shipped; canonical `fact_boundaries` and `time_binned` missing. |
| Q4 | What is the shipped state of C78 `iteration_count`? | Answered: missing, with legacy fixed-timestep substrate to migrate. |
| Q5 | Are the reviewer findings accurate? | Answered: yes, with C77 naming refinement and broader C76-layer gap. |
| Q6 | How should T10 split? | Answered: staged hybrid selected. |
| Q7 | How does T10 unblock T8-C? | Answered: T8-C-1 requires full C76; T8-C-2 requires C74+C77, with C78 conditional for multi-round enrichment. |
| Q8 | What are the dependencies between C74/C76/C77/C78? | Answered: C76 independent; PyReason C-ids conceptually separable but migration-coupled by legacy fixed timesteps. |
| Q9 | What is the C77 rename/migration policy? | Answered: add canonical `fact_boundaries`, keep `valid_time_boundaries` compatibility alias initially. |
| Q10 | What atom-id convention does C74 require and what is shipped today? | Answered: full `<rule_id>:atom_<index>` required; shipped PyReason and T8-B keys are distinct conventions. |
| Q11 | How should T10 fields relate to future evidence `engine_meta`? | Answered: adapter-internal first; future T8-C may expose selected namespaced fields. |
| Q12 | What durable output shape should this cycle produce? | Answered: blueprint-only split plan. |
| Q13 | Are there stop/amend findings? | Answered: none for planning. |

## 4. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| Reviewer C77/C76 findings are accepted without verification | Wrong split / duplicated work | Verify with source refs and grep results. |
| Partial shipped behavior is misclassified as missing | Future sub-cycle rewrites shipped substrate | Classify each C-id by layer: shell / profile / adapter consumption. |
| Missing adapter behavior is misclassified as shipped | T8-C starts too early | Check actual adapter `engine_eval` usage, not just wrapper fields. |
| T10 starts runtime work inside planning cycle | Scope creep | Keep commits docs/blueprint only. |
| T8-C unblock map is over-broad | Starts evidence enrichment before semantics are locked | Map per C-id and per engine. |
| Dirty baseline is touched | Workflow violation | Stage only T10 inventory files. |

## 5. Selected Split Plan

| Future slice | Scope | Unlocks |
|---|---|---|
| T10-1 ProbLog C76 | Add `ProbLogSemantics.uncertainty_projection`, lower it to `SemanticsProfile`, and make the ProbLog adapter consume `raw_kind + bound` projection. | T8-C-1 ProbLog may start after this fully ships or an engine-specific C76 semantics lock is accepted. |
| T10-2 PyReason C74 + C78 | Canonicalize PyReason rule params (`derived_bound`, full-atom-id `atom_bounds`, `timestep_delay`) and introduce `iteration_count` while preserving legacy compatibility. | Partially prepares T8-C-2 and decouples iteration count from temporal projection. |
| T10-3 PyReason C77 | Rename `valid_time_boundaries` to `fact_boundaries`, keep compatibility alias initially, and implement `time_binned` if still in scope. | Completes PyReason temporal prerequisite for T8-C-2 / D11 planning. |

## 6. Verification

```bash
PYTHONPATH=src python -m unittest \
  tests.test_problog_semantics_profile_migration \
  tests.test_pyreason_semantics_profile_migration \
  tests.test_problog_evidence_graph \
  tests.test_pyreason_evidence_graph
```

Result: 46 tests run, 44 OK / 2 existing errors. Both errors are in
`tests.test_problog_semantics_profile_migration` setup paths that still write
legacy `meta[confidence]`; current write protocol rejects it with
`meta[confidence] was removed. Use raw_kind / bound for uncertainty inputs.`
No runtime/test files are changed in this design-only cycle.
`git diff --check` is clean.

## 7. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q13 answered.
- [x] Output shape selected.
- [ ] Closure notes filled.

## 8. Closure Notes

Pending inventory / closure.
