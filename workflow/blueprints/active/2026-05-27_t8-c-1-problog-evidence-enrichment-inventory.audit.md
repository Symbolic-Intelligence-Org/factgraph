# Audit: T8-C-1 ProbLog Evidence Enrichment Inventory

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t8-c-1-problog-evidence-enrichment-inventory.md`
- Stage: draft
- Class: S/M (design-only planning inventory)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current `4 M + 1 D + 4 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T8-C-1 ProbLog evidence enrichment inventory blueprint pair drafted | Triggered after T10-1 C76 shipped at `cde072fa`; Q1-Q10 intentionally pending for Step 4.6. |

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

Step 4.6 must source-back or correct each finding before implementation
planning is considered complete.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Which projection decision memory channel should T8-C-1 use? | Pending Step 4.6. |
| Q2 | Where should the row-result bridge attach? | Pending Step 4.6. |
| Q3 | How should T8-C-1 assemble top-level 14-key metadata, ProbLog adapter-local metadata, and uncertainty projection decisions? | Pending Step 4.6. |
| Q4 | What is the `engine_meta` namespacing strategy for existing flat ProbLog converter fields and future fields? | Pending Step 4.6. |
| Q5 | Does C119 multi-path remain deferred? | Pending Step 4.6. |
| Q6 | What future implementation test matrix is required? | Pending Step 4.6. |
| Q7 | What is the future T8-C-1 implementation cycle class and file scope? | Pending Step 4.6. |
| Q8 | Does T8-C-1 need any user/audit docs in the implementation cycle? | Pending Step 4.6. |
| Q9 | Are there additional T10 or engine-specific prerequisites after T10-1? | Pending Step 4.6. |
| Q10 | Are there stop/amend findings? | Pending Step 4.6. |

## 4. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| Existing ProbLog graph converter is assumed row-ready without checking metadata | Row evidence could bypass T8-A 14-key bridge or expose adapter-local metadata as top-level graph metadata | Compare converter metadata with `_EVIDENCE_GRAPH_METADATA_KEYS` and define bridge ownership. |
| Projection decision metadata is invented after information has been lost | Evidence engine_meta could misrepresent how probabilities were projected | Decide where the projection decision table is produced and persisted. |
| Row bridge is added in the wrong layer | T8-A validation gates or T8-B Form 1 dispatch could be bypassed | Trace `_build_passed_row_evidence_graph(...)` and candidate/evaluate adapter boundaries. |
| Existing flat ProbLog `engine_meta` fields are renamed without compatibility plan | Existing `test_problog_evidence_graph.py` and candidate readback assumptions could regress in a later implementation cycle | Decide one-shot migration, additive namespacing, or compatibility dual-track before runtime work. |
| C119 multi-path is accidentally pulled into first ProbLog slice | T8-C-1 grows beyond the intended bridge/enrichment tranche | Verify current converter/test single-path behavior and keep multi-path deferred unless source proves it is already required. |
| T8-C-1 drifts into PyReason, Form 2, aggregate, Nemo, user-doc, or governance work | Scope expands beyond ProbLog evidence enrichment planning | Enforce out-of-scope list and stop triggers. |
| Dirty baseline is touched | Workflow violation | Stage only T8-C-1 blueprint/audit files in this draft cycle. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed inventory complete.
- [ ] Q1-Q10 answered.
- [ ] No runtime/test/user-doc/governance files changed.
- [ ] Future implementation shape recorded.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending Step 4.6 inventory / closure.
