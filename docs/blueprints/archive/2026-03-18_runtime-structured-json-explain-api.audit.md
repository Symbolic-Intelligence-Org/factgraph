# Task Blueprint Audit: Runtime Structured JSON Explain API

- Blueprint: [2026-03-18_runtime-structured-json-explain-api.md](./2026-03-18_runtime-structured-json-explain-api.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Runtime/service structured explain contract split out as its own task-scoped blueprint. |
| 2026-03-18 | scoped | Scope frozen | Canonical endpoint, legacy alias relationship, stable flat-list invocation shape, and stable-vs-opaque boundary are now fixed for implementation. |
| 2026-03-18 | implemented | Docs and tests landed | Service docs now state the adopted `rule_run` contract; service-level tests lock parity and boundary behavior. |
| 2026-03-18 | implemented | Verification completed | `PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1` passed with 60 tests. |
| 2026-03-18 | archived | Blueprint archived | Structured JSON explain API first-round contract freeze completed. |

## Decision Notes

- 2026-03-18
  - Initial narrowing: treat this as a runtime/service public contract freeze, not a `Scenario A` sub-line.
- 2026-03-18
  - Initial first-round object scope: `rule_run` only.
- 2026-03-18
  - Adopted draft direction: canonical endpoint is `explain_ref(kind="rule_run")`; `explain-rule-trace` remains legacy alias. Both share identical `explain` payload shape; only canonical keeps top-level `kind="rule_run"`.
- 2026-03-18
  - Adopted draft direction: `invocations` stays a stable flat list plus id-linkage contract; no payload-internal `explain.kind` / `rule_run_v1` discriminator is introduced in first round.
- 2026-03-18
  - Implementation outcome: runtime code already matched the adopted service contract; only docs freeze and test hardening were needed in this slice.
