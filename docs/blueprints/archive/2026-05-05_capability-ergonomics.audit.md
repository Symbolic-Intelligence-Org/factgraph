# Capability Ergonomics — Audit Log

- Blueprint: [2026-05-05_capability-ergonomics.md](./2026-05-05_capability-ergonomics.md)
- Parent plan: [2026-05-05_round-story-completion-plan.md](../active/2026-05-05_round-story-completion-plan.md) §5.2

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-05 | draft | Blueprint created | Batch 2 entry from Batch 1 final `49dfc9a`;scope limited to application-layer helper / normalizer work |
| 2026-05-05 | scoped | Scope frozen | Three helpers selected:Fact Overlay override builder, Why-not candidate universe builder, Frontier store-projection wrapper;SDK/protocol/runtime algorithm changes excluded |
| 2026-05-05 | scoped | Frontier helper narrowed | Existing frontier drift gate forbids application importing `kernel.core.rules.frontier`;Q5 helper is projection-only (`build_frontier_view_facts`) and callers still invoke evaluator-layer frontier directly |
| 2026-05-05 | implemented | Helpers implemented and verified | Added helper module/exports/tests, updated demo and application docs;full kernel `1088 OK / 1 skipped`;no SDK/protocol/runtime algorithm changes |

## Decision Notes

### 2026-05-05 — Batch Origin

Batch 1 closed with canonical Q1-Q5 wording and a clean repo except `memory/current.md`. Master plan §5.2 authorizes only ergonomic helpers in `kernel.application/`, so this blueprint starts from the three named helper classes of work and does not reopen capability semantics.

### 2026-05-05 — Helper Module Shape

Use one `kernel.application.capability_helpers` module instead of placing helpers in protocol DTO modules. The helpers are application conveniences over existing DTOs/functions; keeping them outside protocol files avoids confusing ergonomic construction with protocol contract.

### 2026-05-05 — Fact Override Narrowing

The Fact Overlay helper is intentionally scoped to current active single-value field facts. Multi-action overlay, add/remove facts, and generic `EvaluationOverlay` are Batch 3 concerns. If a field has no current active fact or has an unsupported arity, the helper raises `CapabilityHelperError` rather than inventing future semantics.

### 2026-05-05 — Why-not Builder Input

The Why-not helper accepts rows as mappings or sequences and normalizes them against `plan.heads[0].head_var_names`. It does not infer values from hydrated entities or schema fields; doing that would couple the helper to domain-specific object shapes and exceed Batch 2.

### 2026-05-05 — Frontier Layer Boundary Preserved

Initial implementation shaped the frontier helper as an application wrapper that delegated to `evaluate_native_where_frontier(...)`. The existing `test_10_application_layer_does_not_opt_into_frontier_trace` drift gate correctly rejected that import. Decision:Batch 2's frontier ergonomics means Store projection only. `kernel.application` may build `view_facts`; callers that need frontier rows still import and call the evaluator-layer function explicitly.
