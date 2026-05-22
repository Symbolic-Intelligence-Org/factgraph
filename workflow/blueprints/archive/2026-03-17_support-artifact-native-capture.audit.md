# Task Blueprint Audit: Support Artifact Native Capture

- Blueprint: [2026-03-17_support-artifact-native-capture.md](./2026-03-17_support-artifact-native-capture.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-17 | draft | Blueprint created | Opened the first implementation-facing child blueprint to turn the parent explainability discussion into a concrete native-path support capture plan, centered on `SupportArtifact` and witness-capable projection. |
| 2026-03-17 | scoped | Scope confirmed for native path only | Kept the first implementation slice strictly on native derivation support capture, excluding `run_rule` trace, service `explain_ref`, and engine witness output. |
| 2026-03-17 | scoped | Support artifact carrier implemented | Added internal `SupportArtifact` / `BindingSupportCapture` / `ProjectedFact` types and stable digest helpers under `core/store/_support.py`. |
| 2026-03-17 | scoped | Witness-capable projection implemented | Added `project_view_facts_with_witness(...)` in `core/view/projector.py` while preserving the existing pure-value projection path. |
| 2026-03-17 | scoped | Native evaluate support capture wired | Native `Store.evaluate(..., mode="native")` now captures evaluate-time support summaries, computes `support_digest`, and emits `support_kind="native_binding_v1"`. |
| 2026-03-17 | scoped | Candidate builders upgraded | `_builders.py` now consumes `BindingSupportCapture`, writes real `support_digest` / `support_kind` for native rows, and keeps backward-compatible `bindings=` fallback for non-native callers. |
| 2026-03-17 | scoped | Store registry added | `Store` now keeps an internal `_support_artifacts` registry keyed by `support_digest` for in-process support dereference. |
| 2026-03-17 | scoped | Module docs updated | Updated `CANDIDATE_PROTOCOL_V2.md` and `service/docs/03_runtime_queries_views.md` to describe `native_binding_v1` and to refresh runtime examples from deprecated `mode=\"python\"` to `mode=\"native\"`. |
| 2026-03-17 | scoped | Minimal verification run | `python -m compileall` passed for touched store/view modules; targeted pytest execution could not run because `pytest` is not installed in the current environment. |
| 2026-03-17 | implemented | Blueprint close-out completed | Filled Section 10, confirmed that subsequent readback/service work now lives in follow-up child blueprints, and marked the native capture slice implemented/ready-to-archive. |

## Decision Notes

- 2026-03-17: This blueprint deliberately scopes to `Store.evaluate(..., mode="native")` and does not attempt to solve `run_rule` trace, `RuleRef` call-tree explainability, or service `explain_ref` in the same change.
- 2026-03-17: The immediate design goal is not “new proof ids”, but making existing `candidate_id + support_digest/support_kind` meaningful for native derivation results.
- 2026-03-17: The blueprint treats `project_view_facts(...)` dropping `asrt_id` as a first-order blocker and therefore centers a witness-capable projection layer as the enabling change.
- 2026-03-17: The first implementation keeps `evaluate_where(...)` unchanged and instead performs support capture by combining the existing pure-value binding pass with a second witness-capable projection pass; this preserves current evaluator behavior at the cost of duplicate projection work in the short term.
- 2026-03-17: OR-of-AND support capture currently traverses all branches and may emit empty `PredWitness.asrt_ids` for non-winning branches; this was accepted as a deterministic first-step limitation rather than forcing branch-winning logic into the initial slice.
- 2026-03-17: `_builders.py` retains backward-compatible `bindings=` input so that existing `souffle` / `problog` paths continue to emit `support_kind=\"none\"` until dedicated engine witness work is scoped separately.
