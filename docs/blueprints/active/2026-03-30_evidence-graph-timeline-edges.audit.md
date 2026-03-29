# Task Blueprint Audit: Timeline Renderer Edge Visualization

- Blueprint: [2026-03-30_evidence-graph-timeline-edges.md](./2026-03-30_evidence-graph-timeline-edges.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-30 | draft | Blueprint created | F-EG-2: last remaining walkthrough finding |
| 2026-03-30 | scoped | Scope frozen | Inline edge annotations only; no SVG/CSS connectors |
| 2026-03-30 | implemented | All fixes applied | 605 tests green; Python 3.10 f-string compat fix applied |

## Decision Notes

- Inline edge annotations below timeline cards, not SVG overlay
- Reuse _render_edge_note style (muted grey, small font)
- Show "← {edge_kind} · {rule_label} from {source_label}" per incoming edge
- Default params on _render_timeline_card for backward compat
