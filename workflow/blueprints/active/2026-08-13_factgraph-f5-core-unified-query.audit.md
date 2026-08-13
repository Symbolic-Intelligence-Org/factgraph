# Task Blueprint Audit: FactGraph F5-Core unified Query target

- Blueprint: [2026-08-13_factgraph-f5-core-unified-query.md](./2026-08-13_factgraph-f5-core-unified-query.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-13 | draft | Blueprint created | Scope narrowed to resolved Rule/Policy target normalization and existing Query execution. |
| 2026-08-13 | preflight | Compact independent source audit complete | Target normalization, Scenario provenance boundary, and Operator/L3 exclusions independently checked before scope freeze. |
| 2026-08-13 | scoped | F5-Core boundary frozen | `expect`, completeness, generic Scenario evidence/replay, Operator, Meander and Agent surfaces remain explicit non-goals. |
| 2026-08-13 | implementing | Target-normalization implementation started | The branch adds a sealed Rule/Policy Query-target wrapper over the existing F3/F4 evaluator; no second evaluator or Scenario-evidence path is introduced. |

## Decision Notes

- Existing F4 ordinary Query anchors/bundles/evidence remain valid for a lifted
  one-occurrence Policy because its target topology/lineage is still a Policy.
- Q7 Scenario remains intentionally detached from those F4 artifacts; no
  Scenario Explain/replay path is introduced here.
- Operator, L3, source/Package authority, modes and expectations require
  separate contracts and are excluded rather than represented by placeholders.
