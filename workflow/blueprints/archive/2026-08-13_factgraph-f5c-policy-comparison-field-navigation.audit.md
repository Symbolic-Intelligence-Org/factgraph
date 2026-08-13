# Task Blueprint Audit: FactGraph F5C Policy comparison and field navigation

- Status: archived
- Created: 2026-08-13
- Last Updated: 2026-08-13
- Blueprint: [2026-08-13_factgraph-f5c-policy-comparison-field-navigation.md](./2026-08-13_factgraph-f5c-policy-comparison-field-navigation.md)

## Event log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-13 | draft | Source audit completed | Q4B, Query target resolution, lowering, Explain and bundle playback were inspected before edits. |
| 2026-08-13 | scoped | Q12 adopted | The implementation is a constrained Policy compiler/evidence slice, not a general DSL or What-if expansion. |
| 2026-08-13 | implementing | Work started | Pending verification and independent review. |
| 2026-08-13 | verified | Local verification passed | 59 focused tests, 124 application-discovery tests and 180 SDK-discovery tests passed; Ruff, targeted mypy and diff checks were clean. |
| 2026-08-13 | review | Independent adversarial reviews returned CLEAR | Compiler/lineage and evidence/bundle reviewers found no P0/P1/P2. The latter requested an explicit decoded-bundle-to-evidence round-trip regression; it was added before closure. |
| 2026-08-13 | implemented | Q12 acceptance closed | The shipped path is AST through native Query, live Explain, captured bundle decoding and Policy evidence projection, with direct Query bind/select intentionally unchanged. |
| 2026-08-13 | archived | Blueprint pair archived | Module docs are current truth. No generic DSL, Query-level navigation, Scenario/What-if or Meander work starts from this archive transition. |

## Preflight observations

- Direct Policy targets compile before Query `.compile()`, so the builder must
  provide a trusted SchemaIndex during target resolution.
- Existing bundles seal nested Policy DTOs through `asdict`; new independent
  compare/condition DTOs are required to preserve old V0 shapes.
- A compiler-only change would misclassify injected atoms in both live and
  detached evidence, so the evidence chain is mandatory rather than deferred.
- Integrity seals detect accidental or ordinary artifact splicing at the
  existing boundary; they are not an authentication mechanism across a hostile
  process boundary.
