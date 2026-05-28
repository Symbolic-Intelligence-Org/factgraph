# Audit: Adapter Module Docs Alignment

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-28_adapter-module-docs-alignment.md`
- Stage: draft
- Class: S (docs-only)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 6 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | this commit | Adapter module docs alignment blueprint pair drafted | Triggered by T8-D round 4/5 named future work, completed T10 shipped semantics, completed T8-C-1 ProbLog row provenance, and user direction to align only `02_problog_adapter.md` / `03_pyreason_adapter.md`. |

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

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | What stale/current claims exist in `02_problog_adapter.md` for T10-1 C76 and T8-C-1 row provenance? | Pending Step 4.6. |
| Q2 | What stale/current claims exist in `03_pyreason_adapter.md` for T10-2-A/B and T10-3-A/B? | Pending Step 4.6. |
| Q3 | Where should T10-1 C76 `uncertainty_projection` be taught in ProbLog adapter docs? | Pending Step 4.6. |
| Q4 | Where should T8-C-1 ProbLog row provenance and `engine_meta["problog"]` be taught? | Pending Step 4.6. |
| Q5 | Where should the five PyReason canonical axes be taught in PyReason adapter docs? | Pending Step 4.6. |
| Q6 | Should `03_pyreason_adapter.md` mention `pyreason_trace_to_evidence_graph(...)`, and if so how? | Pending Step 4.6. |
| Q7 | Are adapter docs consistent with T8-D round 1-5 quickstarts? | Pending Step 4.6. |
| Q8 | Should implementation be one docs commit or one commit per engine? | Pending Step 4.6. |
| Q9 | Do any stop/amend triggers fire? | Pending Step 4.6. |

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

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed inventory complete.
- [ ] Q1-Q9 answered.
- [ ] ProbLog adapter docs target map reviewed.
- [ ] PyReason adapter docs target map reviewed.
- [ ] Quickstart consistency sweep reviewed.
- [ ] Form 2 deferred boundary reviewed.
- [ ] File-scope decision reviewed.
- [ ] Focused docs-only verification baseline reviewed.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending implementation.
