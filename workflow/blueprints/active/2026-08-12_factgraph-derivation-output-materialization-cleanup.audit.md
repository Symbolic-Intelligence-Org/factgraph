# Task Blueprint Audit: FactGraph derivation-output/materialization cleanup

- Status: scoped
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: paired blueprint audit log
- Inputs:
  - [`2026-08-12_factgraph-derivation-output-materialization-cleanup.md`](./2026-08-12_factgraph-derivation-output-materialization-cleanup.md)
- Outputs / Downstream:
  - (none)
- Related:
  - [`2026-08-12_q5c-derivation-output-materialization-boundary-decision.md`](../../design/decisions/active/2026-08-12_q5c-derivation-output-materialization-boundary-decision.md)
- Blueprint: [`2026-08-12_factgraph-derivation-output-materialization-cleanup.md`](./2026-08-12_factgraph-derivation-output-materialization-cleanup.md)

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-12 | draft | Three bounded read-only audits completed | Candidate inventory, public/accept surface and minimal migration design converged. |
| 2026-08-12 | scoped | User authorized the next isolated step | Lightweight path skips a separate preflight because three independent audits already cover the deletion, type migration and cross-layer risks. |
| 2026-08-12 | scoped | Cross-repository dependency narrowed Batch A | Meander `main@4ddb8e36` has four live `evaluate_candidates` consumers; deletion is deferred to a cross-repository migration. |

## Decision Notes

- Batch A removes five zero-call primary service codecs and their four-helper-only
  parser chain. The HTTP tombstone and all Agent/core materialization paths remain.
- Batch B changes canonical Python terminology, not persisted candidate protocol.
- `evaluate_candidates` is temporary compatibility debt, not a newly endorsed
  public design. Current public API coherence and D23 completion are not claimed.
- Batch B repairs Store-digest bypass and dropped batch intent without creating
  or renaming a public materialization surface.
- F4 is barred from using output/candidate identity as a durable anchor.
