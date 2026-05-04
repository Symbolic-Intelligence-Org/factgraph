# Task Blueprint Audit: Diagnose Operation

- Blueprint: [2026-05-04_diagnose-operation.md](./2026-05-04_diagnose-operation.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-04 | draft | Blueprint created | Opened as the second application capability candidate after Check. Purpose is Step 0 only: freeze Diagnose DTO / algorithm / engine boundary before any implementation. |
| 2026-05-04 | draft | Step 0.A source pass opened | Initial anchors recorded from Check protocol/runtime, archived Check blueprint/audit, application common protocol DTOs, baseline P0-3 support artifacts, and engine-extension §6.3 / §6.4 / §6.5. |

## Decision Notes

- 2026-05-04: Diagnose starts as a `draft` blueprint because the application DTO shape is not frozen. Per application-first hard constraint, implementation cannot begin until Step 0 answers "what is the application DTO shape?"
- 2026-05-04: Initial positioning: Diagnose is expected to be a sibling application capability to Check, not an SDK extension and not an Explain / Why-not / UI projection feature.
- 2026-05-04: Step 0.A initial source anchors:
  - `CheckRequest` / `CheckResult` / `EvidenceEnvelope` show the closest existing request/result/evidence pattern.
  - `check_derivation_binding(...)` shows final-result matching, representability precheck, and typed evidence lookup boundaries.
  - `ErrorDTO` / `WarningDTO` are the current application error/warning carriers.
  - baseline P0-3 records support/provenance data contracts and the partial-binding silent-false trap.
  - engine-extension §6.3 requires observable evidence misses for new capabilities.
  - engine-extension §6.4 blocks request-level engine options unless promotion criteria are met.
  - engine-extension §6.5 keeps typed Union as payload default unless a concrete migration trigger appears.
- 2026-05-04: Open Step 0.A question: does Diagnose create enough second-consumer pressure to promote §3.6 engine capability declaration, or can MVP stay locally hardcoded like Check?
