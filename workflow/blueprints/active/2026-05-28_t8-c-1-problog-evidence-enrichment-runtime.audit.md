# Audit: T8-C-1 ProbLog Evidence Enrichment Runtime

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-28_t8-c-1-problog-evidence-enrichment-runtime.md`
- Stage: draft
- Class: M (runtime implementation)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 5 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | this commit | T8-C-1 ProbLog evidence enrichment runtime blueprint pair drafted | Triggered by T10-1 C76 ship at `cde072fa` and T8-C-1 inventory at `bd5baeec`; Q1-Q10 pending for Step 4.6. |

## 2. Draft Inventory Summary

This runtime cycle starts from locked inventory decisions:

- Use trace-payload attachment for ProbLog uncertainty projection decision
  memory.
- Add private provenance row context parallel to `_row_support_artifacts`, not
  a Form 1 support-kind widening.
- Add a ProbLog row branch in `_build_passed_row_evidence_graph(...)` while
  preserving T8-A metadata validation gates.
- Keep top-level graph metadata exactly 14 keys and move ProbLog trace summary
  / projection details under namespaced `engine_meta["problog"]`.
- Preserve the existing candidate converter's flat adapter-local `engine_meta`.
- Keep C119 multi-path DAG and C136 aggregate envelope deferred.

Step 4.6 must source-back concrete schema and implementation choices without
reopening these decisions.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | What is the projection decision table schema? | Pending Step 4.6. |
| Q2 | How should `_claim_probability(...)` expose structured decisions? | Pending Step 4.6. |
| Q3 | What private row provenance context field should `EvaluateResult` use? | Pending Step 4.6. |
| Q4 | Where exactly should `_build_passed_row_evidence_graph(...)` branch? | Pending Step 4.6. |
| Q5 | What is the complete namespaced `engine_meta` field set? | Pending Step 4.6. |
| Q6 | What audit docs change is required? | Pending Step 4.6. |
| Q7 | What implementation commit split should be used? | Pending Step 4.6. |
| Q8 | How is anti-silent-ignore enforced at row bridge level? | Pending Step 4.6. |
| Q9 | Does this unblock T8-D round 3? | Pending Step 4.6. |
| Q10 | Are there stop/amend findings? | Pending Step 4.6. |

## 4. Risk Register

| Risk | Impact | Step 4.6 / implementation check |
|---|---|---|
| Inventory decisions are reopened silently | Runtime implementation drifts from the archived source-backed plan | Treat T8-C-1 inventory Q1-Q9 as locked; stop and amend archive if wrong. |
| Projection decisions are reconstructed after export | Evidence metadata may lie about how probabilities were produced | Produce the decision table at export time before `.pl` point-probability collapse. |
| Row bridge bypasses T8-A validation | ProbLog row graphs could miss 14-key metadata validation | Trace metadata validation before and after dispatch. |
| `_FORM1_ROW_SUPPORT_KINDS` is widened | ProbLog provenance could be misclassified as native/Souffle Form 1 | Keep private provenance row context separate. |
| Existing ProbLog converter flat engine_meta is migrated in-place | Existing candidate/readback tests and service audit-package path may regress | Use row-result wrapper, not one-shot converter migration. |
| Default `reject` is rendered as empty evidence | T10-1 anti-silent-ignore guarantee is weakened | Reject remains execution error; no row evidence graph exists on reject. |
| C119 multi-path enters scope | M-class bridge grows into graph algorithm work | Keep full multi-path DAG deferred unless source disproves single-path assumption and stop/amend. |
| User docs are updated in this cycle | T8-D round 3 boundary is violated | Limit docs to audit module. |
| Dirty baseline is touched | Workflow violation | Stage only cycle-owned files and scoped runtime/test/docs files. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed inventory complete.
- [ ] Q1-Q10 answered.
- [ ] Projection memory producer implemented.
- [ ] Private row provenance context implemented.
- [ ] ProbLog row bridge implemented.
- [ ] Focused test matrix implemented.
- [ ] Audit docs updated.
- [ ] Full discover delta explained.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending Step 4.6 inventory / implementation / closure.
