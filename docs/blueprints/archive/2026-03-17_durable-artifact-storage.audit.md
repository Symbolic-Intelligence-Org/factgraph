# Task Blueprint Audit: Durable Artifact Storage

- Blueprint: [2026-03-17_durable-artifact-storage.md](./2026-03-17_durable-artifact-storage.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-17 | draft | Blueprint created | Opened a dedicated post-explainability child blueprint after core/service explain readback had been stabilized, to compare durable storage options before any implementation work. |
| 2026-03-17 | draft | Comparison axes clarified | Added explicit discussion of why `RuleTraceArtifact` is not yet naturally content-addressable and noted the coupling between storage location and write timing. |
| 2026-03-17 | scoped | First durable direction selected | Resolved the five open questions in favor of an audit/export-first first slice: `SupportArtifact` remains content-addressed, `RuleTraceArtifact` stays package-scoped under opaque `rule_run_id`, audit export remains full-registry for the first round, and online continuity / sidecar storage are deferred. |
| 2026-03-17 | scoped | Implementation child blueprint chosen | Promoted `audit-package-artifact-export` from a candidate to the selected first implementation slice, while leaving sidecar storage and candidate-support backrefs as later topics. |
| 2026-03-17 | scoped | Sidecar child blueprint restored to active | Gap audit showed the archived `artifact-sidecar-store` child blueprint had no supporting code/docs evidence for its claimed `implemented` state; it was moved back to `active/`, reset to `scoped`, and prepared for real implementation planning. |
| 2026-03-17 | implementing | Sidecar child helper layer shipped | The restored `artifact-sidecar-store` child blueprint entered real implementation with artifact `from_dict(...)` round-trip helpers and focused/full test verification, while online durable readback wiring remains outstanding. |
| 2026-03-17 | implementing | Sidecar child carrier layer shipped | The child blueprint now has the file-backed carrier itself plus collision/path-safety tests; remaining work is limited to Store/runtime/SDK integration and docs. |
| 2026-03-17 | implementing | Sidecar child Store layer shipped | The sidecar child blueprint now includes Store constructor injection, first-write durable persistence, lookup fallback, and cross-store readback tests; the remaining work is narrowed to runtime/SDK configuration surfaces and module-doc sync. |
| 2026-03-17 | implemented | Sidecar child blueprint completed | The `artifact-sidecar-store` child blueprint is now fully implemented and archived after runtime/SDK surfaces, docs sync, and end-to-end readback tests were completed. |
| 2026-03-17 | implemented | Retention/GC follow-up child completed | The follow-up `sidecar-retention-gc` child blueprint shipped sidecar-adjacent metadata, age-only `RuleTraceArtifact` GC, focused tests, and core-doc sync, and is now archived alongside the original durable-storage slices. |

## Decision Notes

- 2026-03-17: Durable artifact storage should be decomposed as its own problem, rather than being folded prematurely into generic `explain_ref` or candidate back-reference design.
- 2026-03-17: The first durable-storage discussion should compare at least three landing zones: ledger-coupled storage, audit-package-only materialization, and a separate sidecar artifact store.
- 2026-03-17: `support_digest` and `rule_run_id` should not be assumed to have identical durable-key semantics; the blueprint should treat `SupportArtifact` and `RuleTraceArtifact` separately where needed.
- 2026-03-17: Existing audit package export is the most obvious durable consumer already present in the codebase, so export-time artifact materialization should be compared explicitly even if it is not the final online durability solution.
- 2026-03-17: The first implementation slice should target audit/export completeness only; online durable readback continuity is deferred until a dedicated sidecar-store discussion exists.
- 2026-03-17: In the first slice, audit package export should dump the full in-memory artifact registries rather than attempting reference-subset filtering.
- 2026-03-17: `SupportArtifact` should continue to use `support_digest` as its durable key, while `RuleTraceArtifact` should remain keyed by opaque `rule_run_id` inside exported packages until a canonical trace-key design is explicitly scoped.
- 2026-03-17: Archived `implemented` status must only be used when corresponding code, tests, and module-doc evidence is verifiably present; when that evidence is missing, the child blueprint must be restored to `active/` rather than left as a false historical record.
- 2026-03-20: All 4 child slices verified as implemented and archived. Mother blueprint status updated to `implemented` and archived. Full test suite (173 tests) passes.
