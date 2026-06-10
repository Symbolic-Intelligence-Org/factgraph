# FactPy Audit Docs

This directory records the current implementation contract for
`src/factgraph/audit`, targeting developers who need to read audit
packages, run offline audit queries, build DTOs, or consume the
evidence graph. Full static-site rendering belongs to the external
delivery layer, not to the factgraph-only package.

## Current documents

- `src/factgraph/audit/docs/01_overview.en.md`
  - audit module responsibilities, public entry points, audit
    workflow, round event log, and boundaries with runtime / registry.
- `src/factgraph/audit/docs/02_evidence_graph.md`
  - `factgraph.audit.evidence_graph` thin re-export façade: paths-model
    `EvidenceGraph(paths=...)`, `EvidenceTree`, `EvidenceTimeline`,
    serialization helpers, row-result `metadata` key set, layout constants.
    The old flat-DAG DTOs were removed in S6d.
    Canonical type definitions live in `factgraph.application.explain`.
- `src/factgraph/audit/docs/03_audit_package_contract.md`
  - Required / optional files of the audit package, the
    `round_events.jsonl` contract, query-derived surfaces, ECSS
    compliance ownership boundary, and minimal provenance carrier
    mapping.

## Conventions

- Documents in this directory reflect the current audit-package
  reading and query implementation.
- When `AuditQuery`, the audit package contract, or the shared
  `EvidenceGraph` DTO change, update the corresponding doc and tests
  in the same change.
- When the full static-site output, `site_manifest.json`, or
  `ui_index.json` change, update the corresponding delivery-layer doc
  in the same change.
