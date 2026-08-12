# Task Blueprint Audit: FactGraph EvaluationRun bundle capture

- Status: implemented
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: paired blueprint audit log
- Blueprint: [`2026-08-12_factgraph-evaluation-run-bundle-capture.md`](./2026-08-12_factgraph-evaluation-run-bundle-capture.md)
- Related: [`2026-08-12_q6b-evaluation-run-bundle-capture-decision.md`](../../design/decisions/active/2026-08-12_q6b-evaluation-run-bundle-capture-decision.md)

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-12 | draft | Three read-only F4B audits completed | All rejected view-digest/live-Store pseudo replay and required capture before verification. |
| 2026-08-12 | scoped | User authorized continuation after F4A CLEAR | The slice is limited to opt-in bundle capture, strict codec and detached inspection; no replay/Explain/What-if. |
| 2026-08-12 | implementing | Scoped contract entered implementation | Protocol/codec and the single-projection capture seam may proceed in parallel; public integration follows their tests. |
| 2026-08-12 | implementing | Review-driven strictness amendment | Gross production cap raised from 1,000 to a hard 1,750; after the canonical-JSON error-path consolidation, the review-ready strict codec implementation measures 1,692 lines. The delta closes a public callback bypass, JSON/value ceiling gaps and runtime type-reflection failure; no replay, Explain, What-if or repository scope was added. ProofReceipt validation was clarified as structural playback, leaving logical re-evaluation to F4B2. |
| 2026-08-12 | verified | Final implementation checks passed | The application/SDK cohort passed 480 tests plus 108 subtests; the post-commit focused cohort passed 36 tests plus 12 subtests; Ruff, targeted mypy, diff-check and the independent 1,692/1,750 cap calculation passed. |
| 2026-08-12 | review | Internal fixed-state reviews returned CLEAR | API-boundary, protocol red-team and scope/simplicity reviews closed all findings; final state has zero P0/P1/P2. |
| 2026-08-12 | review | User-side independent review returned CLEAR | The reviewer repeated 480 application/SDK tests plus 108 subtests, static checks and approximately 40 adversarial checks, independently confirmed 1,692/1,750 production additions and reported zero P0/P1/P2. |
| 2026-08-12 | implemented | F4B1 acceptance criteria closed | Implementation lineage `62655986`/`d6f70252`/`6d32beb1` ships opt-in atomic bundle capture, a strict codec and detached inspection while leaving isolated replay to F4B2, detached inner Explain to F4B3 and Policy overlay to F4C. |

## Decision Notes

- The F4B name is retained as a roadmap label; F4B1 itself does not expose replay.
- Effective-relation capture is sufficient for the original execution but not
  for general What-if because chosen-hidden claims have already been discarded.
- Full sensitive values are necessary for deterministic verification; capture
  is therefore explicit and custody remains outside FactGraph core.
- The initial 1,000-line estimate was not compatible with the required strict
  codec and red-team guards. Independent scope review found no honest
  simplification worth losing AST-aware dependency traversal, typed canonical
  values, component seals or strict decoding. The 1,750 cap leaves 58 lines
  solely for final review fixes.
- Raw effective-relation capture is private and atomic. Neither public
  `evaluate_store(...)` nor public `evaluate_derivation_plans(...)` accepts an
  observer/callback, so callers cannot bypass the bundle limits and custody
  declarations through a public evaluation API.
