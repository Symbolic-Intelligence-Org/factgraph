# Audit — Rule Replay With Evidence Diff

Companion to `2026-05-01_rule-replay-with-evidence-diff.md`.

## Event Log

| Date | Phase | Event | Notes |
|---|---|---|---|
| 2026-05-01 | draft | Blueprint created from rule-replay reference bundle | Created from `docs/references/working/rule-replay/README.md`, starting with the bundled synthesis document. Scope intentionally remains blocked on Step 0 source-backed feasibility questions. |
| 2026-05-01 | draft | Round-1 review corrections applied | Tightened draft boundaries: compiled plans are not patch inputs, red/green review UI is not a first-preview product claim, evidence read-only must be structural at the public API, and audit export requires an engine-neutral materialization owner if persistence enters scope. |
| 2026-05-01 | scoped | Step 0 completed and preview scope locked | Source-backed scope is top-level derivation authoring variant replay only. Referenced registry rule variants, compiled-plan patch targets, persistent replay export, Parameter Handle, fact what-if, lazy why-not carrier, candidate universe, rich statuses, shared condition identity, and local proof-path recheck are design-reserved. |
| 2026-05-01 | implementing | Step 1 patch substrate added | Added internal `kernel.sdk.replay` helpers for parsing `b{branch}.a{atom}` locators, looking up atoms by deep copy, and producing deep-copied authoring payload variants. No public SDK export, runtime, engine, or audit package behavior changed. Verification: replay substrate unit test, kernel full unittest, ruff, and `git diff --check` passed. |
| 2026-05-01 | implementing | Step 2 SDK replay wrapper added | Added public `SDKStore.replay_with_patch(...)` and exported `ReplayResult`. Both original and variant are evaluated through the dict-input `SDKStore.evaluate(...)` path for symmetry. Native-only, engine_ext, non-native mode, and RuleRef dependency_rules boundaries are enforced. Verification: replay runtime tests, replay patch tests, kernel full unittest, ruff, and `git diff --check` passed. |
| 2026-05-01 | implementing | Step 3 candidate diff added | Added public `compare_candidates(...)`, `CandidateDiff`, and `ReplayResult.diff()`. Diff identity uses cross-run stable `candidate_key`, not `candidate_id` because `candidate_id` includes `run_id`. Scope is candidate-level `added` / `removed` / `retained` only; evidence diff remains Step 4. |
| 2026-05-01 | implementing | Step 4 evidence comparison hook added | Added public `compare_evidence(...)`, `EvidenceComparison`, and `CandidateDiff.evidence_comparisons()`. Comparison uses retained candidate pairs and shallow CandidateSet metadata: `support_kind`, `support_digest`, `confidence`, and `confidence_kind`. It does not read audit packages or expand proof trees. |
| 2026-05-01 | implementing -> implemented | Step 5 close-out completed | Added the end-to-end v0.1.1 journey test, synchronized Chinese and English SDK user guides, filled the blueprint outcome, and deferred notebook work. Final verification: 777 OK / 1 skip, ruff clean, and `git diff --check` clean. |

## Decision Notes

- Initial file name locked as `2026-05-01_rule-replay-with-evidence-diff` to match the synthesis primary framing and avoid implying mutable evidence trees.
- Initial branch context recorded as `evidence-tree-operational-overlay`.
- Step 0 resolved the draft-stage gate: feature implementation may begin against the scoped derivation-variant preview only.
- Patch target decision: operate on top-level SDK/authoring derivations, produce temporary authoring variants, then recompile. Do not patch `CompiledDerivationPlan.body_ir` in place.
- Locator decision: reuse `b{branch}.a{atom}` prefix locators for v0.1.1 and normalize suffixed support/evidence keys back to that prefix for comparison.
- Audit/export decision: no replay JSONL persistence in v0.1.1 unless an engine-neutral export owner is introduced before audit reader work.
- Step 1 implementation note: locator detection uses positive atom-shape checks so tuple-form atoms and JSON list-form atoms both work in flat and branched payloads. `where` and `body` are patched together only when both fields are present and equal, mirroring the compiler's equality requirement.
- Step 2 implementation note: `replay_with_patch(...)` does not compute candidate diff or evidence diff; it only returns original and variant candidates/payloads. Diff helpers remain Step 3 scope.
- Step 3 implementation note: two evaluations of the same derivation produce different `candidate_id` values but the same `candidate_key`; tests lock this invariant to prevent future candidate diff from using the wrong identity.
- Step 4 implementation note: native `support_digest` is cross-run stable for the same support path. `EvidenceComparison.status` separates available metadata comparison from degraded missing-support cases and unsupported cross-kind comparisons.
