# Task Blueprint Audit: ECSS VCD Compliance Delivery

- Blueprint: [2026-03-18_ecss-vcd-compliance-delivery.md](./2026-03-18_ecss-vcd-compliance-delivery.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Opened the implementation-facing child slice for Scenario B, focused on VCD/compliance-matrix data modeling and delivery shape rather than temporal or uncertainty semantics. |
| 2026-03-18 | scoped | Scope frozen | Adopted `hybrid` requirement/data model, `offline-query-first` delivery, and `packages/export` unchanged as the first-round service boundary. |
| 2026-03-18 | implemented | Offline compliance query landed | Added requirement/compliance predicate helpers, `AuditQuery.list_compliance_matrix(...)`, DTO support, package-level contract tests, and audit docs updates without changing the audit package wire format. |

## Decision Notes

- 2026-03-18: This slice should start from `audit/export + offline consumer` boundaries, not from new runtime semantics.
- 2026-03-18: `explain_ref` is expected to remain an evidence drill-down helper, not the primary compliance-matrix contract.
- 2026-03-18: Adopted `hybrid` data model: requirement identity and related status/method/RID/milestone facts live in the ledger; compliance-matrix rows remain offline derived delivery objects.
- 2026-03-18: Adopted `offline-query-first`; v1 does not add `compliance_matrix.jsonl` or other pre-cooked package artifacts.
- 2026-03-18: `offline-query-first` requires access to assertion/fact-level package contents, likely by reusing `audit.assertions.load_assertion_index(...)` or an equivalent read path, because current `AuditQuery` only exposes JSONL audit ledgers.
- 2026-03-18: `packages/export` stays unchanged in v1; `AuditQuery`/`dto.py` become the primary compliance-matrix surface; `explain_ref` remains drill-down only.
- 2026-03-18: The implementation keeps `packages/export` unchanged and derives matrix rows offline from package facts/assertions by reusing the existing assertion-index read path.
- 2026-03-18: Requirement/compliance predicates use canonical `requirement_ref` (`idref_v1`) as the internal `e_ref` join key; human-facing `req_id` remains an explicit requirement fact field and matrix row output.
