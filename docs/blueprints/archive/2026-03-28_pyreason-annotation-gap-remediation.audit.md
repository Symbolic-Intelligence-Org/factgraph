# Task Blueprint Audit: PyReason Annotation Gap Remediation

- Blueprint: [2026-03-28_pyreason-annotation-gap-remediation.md](./2026-03-28_pyreason-annotation-gap-remediation.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-28 | draft | Scope verified from code audit | Confirmed bounded graph materialization still reads `value`, and annotation pipeline still has confidence-origin, revocation, accept validation, and static UI derivation gaps. |
| 2026-03-28 | scoped | Blueprint activated for implementation | Scope frozen to bounded materialization + annotation pipeline remediation only. |
| 2026-03-28 | implemented | Runtime/docs/tests updated | Implemented bounded graph lower-bound preference, shared confidence derived origin, revocation annotation dual-write, accept template validation, and static UI derivation column. Updated adapter/core docs and relevant unit tests. |
| 2026-03-28 | archived | Blueprint archived after validation | Targeted unittest suite and py_compile passed before archive move. |

## Decision Notes

- Bound fact text transport (`PyReasonFactDef.bound` -> `run_pyreason`) was already present in code and is explicitly out of scope for this remediation pass, except for verifying the remaining graph materialization gap.
- Graph materialization keeps a compatibility fallback: when a bounded fact has no explicit non-default bound, runner still parses the raw value to avoid breaking older call sites that only populated `value`.
- Shared `confidence_source` was not added as a new write_protocol whitelist annotation in this pass; instead `confidence.derivation` now carries the source contract, with PyReason session auto-populating `meta["confidence_source"]`.
