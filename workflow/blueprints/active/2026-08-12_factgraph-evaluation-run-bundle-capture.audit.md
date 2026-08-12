# Task Blueprint Audit: FactGraph EvaluationRun bundle capture

- Status: scoped
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

## Decision Notes

- The F4B name is retained as a roadmap label; F4B1 itself does not expose replay.
- Effective-relation capture is sufficient for the original execution but not
  for general What-if because chosen-hidden claims have already been discarded.
- Full sensitive values are necessary for deterministic verification; capture
  is therefore explicit and custody remains outside FactGraph core.
