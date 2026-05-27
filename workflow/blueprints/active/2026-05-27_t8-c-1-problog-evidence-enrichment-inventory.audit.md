# Audit: T8-C-1 ProbLog Evidence Enrichment Inventory

- Status: scoped
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t8-c-1-problog-evidence-enrichment-inventory.md`
- Stage: scoped
- Class: S/M (design-only planning inventory)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current `4 M + 1 D + 4 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T8-C-1 ProbLog evidence enrichment inventory blueprint pair drafted | Triggered after T10-1 C76 shipped at `cde072fa`; Q1-Q10 intentionally pending for Step 4.6. |
| 2026-05-27 | scoped | pending | Source-backed T8-C-1 ProbLog inventory completed | Selected trace-payload projection memory, private provenance row context, T8-A 14-key top-level metadata with namespaced ProbLog engine metadata, and C119 single-path defer. |

## 2. Draft Inventory Summary

Reviewer due diligence supplied the starting hypothesis:

- ProbLog provenance already has a `problog_trace_to_evidence_graph(...)`
  converter that returns an `EvidenceGraph`, but it is candidate/provenance
  readback today, not row-result evidence.
- Current ProbLog converter top-level metadata remains adapter-local
  (`event_count`, `answer_count`, `root_goal`, `answer_probability`) and has no
  overlap with the T8-A 14-key row-result metadata bridge.
- T10-1 C76 projection decisions are applied during ProbLog export, but the
  current export path materializes only a point probability into the `.pl`
  program and does not persist a structured decision table for evidence
  metadata.
- T8-C inventory Option C (adapter-side metadata bridge / provenance row
  bridge) appears still valid, but Step 4.6 must verify rather than accept it.

Step 4.6 source-backed and refined these findings:

- ProbLog remains provenance-bearing, not witness-bearing; T8-C inventory
  Option C remains the right architecture path.
- The converter has direct candidate/test and legacy service audit-package call
  sites, but no row-result `EvaluateRow.explain()` call site.
- Current ProbLog graph metadata and flat `engine_meta` should not be promoted
  to row-result top-level metadata; row-result graphs need T8-A 14-key metadata
  and namespaced `engine_meta["problog"]`.
- Projection decisions should be remembered in the provenance payload, because
  ProbLog export is the source of truth for policy application before the
  `.pl` program collapses the decision to a point probability.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Which projection decision memory channel should T8-C-1 use? | Answered: trace-payload attachment produced by the ProbLog adapter at export/provenance time. |
| Q2 | Where should the row-result bridge attach? | Answered: private provenance row context plus `_build_passed_row_evidence_graph(...)` branch, preserving T8-A validation gates. |
| Q3 | How should T8-C-1 assemble top-level 14-key metadata, ProbLog adapter-local metadata, and uncertainty projection decisions? | Answered: 14-key top-level metadata stays exact; ProbLog trace summary and projection decisions move into namespaced row-result `engine_meta["problog"]`. |
| Q4 | What is the `engine_meta` namespacing strategy for existing flat ProbLog converter fields and future fields? | Answered: preserve current candidate converter flat shape; future row-result wrapper emits namespaced ProbLog engine_meta. |
| Q5 | Does C119 multi-path remain deferred? | Answered: yes. Current tests and import logic remain single selected trace/candidate; duplicate bindings collapse before candidate creation. |
| Q6 | What future implementation test matrix is required? | Answered: converter regressions, row bridge, 14-key metadata, namespaced engine_meta, uncertainty projection decision metadata, and T8-A/B/D/T10 regressions. |
| Q7 | What is the future T8-C-1 implementation cycle class and file scope? | Answered: M-class, roughly 250-550 runtime LOC and 150-300 test LOC across ProbLog adapter, protocol row dispatch, SDK plumbing, and focused tests. |
| Q8 | Does T8-C-1 need any user/audit docs in the implementation cycle? | Answered: future implementation should update audit-module docs; user docs should wait for a T8-D round 3 after runtime ships. |
| Q9 | Are there additional T10 or engine-specific prerequisites after T10-1? | Answered: no for first ProbLog row bridge; T10-1 C76 is sufficient. |
| Q10 | Are there stop/amend findings? | Answered: none. |

## 4. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| Existing ProbLog graph converter is assumed row-ready without checking metadata | Row evidence could bypass T8-A 14-key bridge or expose adapter-local metadata as top-level graph metadata | Completed: converter metadata is adapter-local; row-result graph metadata must stay T8-A 14-key. |
| Projection decision metadata is invented after information has been lost | Evidence engine_meta could misrepresent how probabilities were projected | Completed: selected trace-payload attachment at export/provenance time. |
| Row bridge is added in the wrong layer | T8-A validation gates or T8-B Form 1 dispatch could be bypassed | Completed: selected private provenance row context plus `_build_passed_row_evidence_graph(...)` branch, with gate trace. |
| Existing flat ProbLog `engine_meta` fields are renamed without compatibility plan | Existing `test_problog_evidence_graph.py` and candidate readback assumptions could regress in a later implementation cycle | Completed: preserve candidate converter flat shape; row-result wrapper owns namespaced engine_meta. |
| C119 multi-path is accidentally pulled into first ProbLog slice | T8-C-1 grows beyond the intended bridge/enrichment tranche | Completed: current tests/import are single-path; C119 remains deferred. |
| T8-C-1 drifts into PyReason, Form 2, aggregate, Nemo, user-doc, or governance work | Scope expands beyond ProbLog evidence enrichment planning | Completed: out-of-scope list preserved; no stop trigger. |
| Dirty baseline is touched | Workflow violation | Completed: only blueprint/audit files are staged for this design-only cycle. |

## 5. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q10 answered.
- [x] No runtime/test/user-doc/governance files changed.
- [x] Future implementation shape recorded.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending Step 4.6 inventory / closure.
