# Task Blueprint Audit: Audit Package Artifact Export

- Blueprint: [2026-03-17_audit-package-artifact-export.md](./2026-03-17_audit-package-artifact-export.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-17 | draft | Blueprint created | Split the first durable-storage implementation slice out of the durable-artifact-storage parent after the parent direction was narrowed to audit/export completeness first. |
| 2026-03-17 | scoped | Export row shape and package integration clarified | Confirmed the first slice should follow existing flat JSONL audit row style, add artifact files through the existing `audit_files` manifest path, and allow direct registry reads from `package.py` in the first round. |
| 2026-03-17 | implemented | Audit package artifact export landed | Added `support_artifacts.jsonl` and `rule_trace_artifacts.jsonl` to audit package export, wired them into `audit_files`, and documented the new package files. |
| 2026-03-17 | validated | Compile + targeted unittest passed | `compileall` passed for touched adapter/audit/test modules; a focused package-export unittest verified manifest entries and flat JSONL row shape, and existing explainability regressions still passed under `unittest`. |

## Decision Notes

- 2026-03-17: The first durable-storage implementation slice should stay export-only and must not backdoor online durable readback or ledger-coupled persistence into scope.
- 2026-03-17: `SupportArtifact` should be exported under `support_digest`, while `RuleTraceArtifact` should be exported under opaque `rule_run_id` without introducing a trace digest in this slice.
- 2026-03-17: The first round should export full artifact registries rather than attempting reference-subset filtering.
- 2026-03-17: Artifact JSONL rows should use the existing flat audit-row style rather than nesting payloads under an `artifact` field.
- 2026-03-17: Direct reads of `store._support_artifacts` and `store._rule_trace_artifacts` from `package.py` are acceptable in the first slice; introducing public dump accessors is deferred unless registry-boundary pressure appears later.
- 2026-03-17: Because `rule_trace_artifact_to_dict(...)` already carries `rule_run_id`, rule-trace export rows should reuse that field directly, while support-artifact rows should explicitly inject `support_digest`.
