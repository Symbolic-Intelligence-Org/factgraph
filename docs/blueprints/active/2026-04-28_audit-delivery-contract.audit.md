# Task Blueprint Audit: Audit Delivery Contract

- Blueprint: [2026-04-28_audit-delivery-contract.md](./2026-04-28_audit-delivery-contract.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-04-28 | draft | Blueprint created | Created as a separate docs-only blueprint to avoid folding audit delivery/product contract work into runtime-authority cleanup. Trigger: follow-up review found audit docs still claiming static-site and old ECSS compliance ownership after namespace split. |
| 2026-04-28 | draft → scoped | Scope frozen | Scope limited to documentation truth correction and delivery contract documentation. No code behavior changes, no static UI redesign, no package exporter changes, no full PROV implementation, and no branch/commit in this local pass. |
| 2026-04-28 | scoped → implemented | Docs pass completed locally | Added audit package and static site contract docs; corrected audit/service/ECSS/root docs; kept active because this local pass is not committed or archived yet. |

## Decision Notes

1. **Separate from runtime-authority cleanup**
   - **Why**: runtime-authority cleanup owns `sdk ↔ application` runtime boundary. Audit delivery owns package/static-site/product contract documentation. Combining them would create scope coupling and hide delivery work behind unrelated implementation decisions.
   - **Impact**: this blueprint edits only audit/service/ECSS/root docs and its own audit log.

2. **Docs truth correction before code changes**
   - **Why**: code already has the desired ownership in key places: `service.static_ui` owns full static-site rendering, `domains.ecss.compliance` owns ECSS row assembly, and `kernel.audit` owns reader/query/DTO/evidence graph consumption.
   - **Impact**: first pass is docs-only. Any later behavior work needs a separate scoped blueprint.

3. **Minimum provenance mapping, not full PROV**
   - **Why**: existing carriers already expose provenance-like semantics, but forcing a full external provenance model would expand scope. A minimum mapping is enough to make the current delivery contract auditable and honest.
   - **Impact**: new docs should map current fields to entity/activity/agent/bundle roles without claiming conformance.
