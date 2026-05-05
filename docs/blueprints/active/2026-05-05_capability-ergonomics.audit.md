# Capability Ergonomics — Audit Log

- Blueprint: [2026-05-05_capability-ergonomics.md](./2026-05-05_capability-ergonomics.md)
- Parent plan: [2026-05-05_round-story-completion-plan.md](./2026-05-05_round-story-completion-plan.md) §5.2

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-05 | draft | Blueprint created | Batch 2 entry from Batch 1 final `49dfc9a`;scope limited to application-layer helper / normalizer work |
| 2026-05-05 | scoped | Scope frozen | Three helpers selected:Fact Overlay override builder, Why-not candidate universe builder, Frontier store-projection wrapper;SDK/protocol/runtime algorithm changes excluded |

## Decision Notes

### 2026-05-05 — Batch Origin

Batch 1 closed with canonical Q1-Q5 wording and a clean repo except `memory/current.md`. Master plan §5.2 authorizes only ergonomic helpers in `kernel.application/`, so this blueprint starts from the three named helper classes of work and does not reopen capability semantics.

### 2026-05-05 — Helper Module Shape

Use one `kernel.application.capability_helpers` module instead of placing helpers in protocol DTO modules. The helpers are application conveniences over existing DTOs/functions; keeping them outside protocol files avoids confusing ergonomic construction with protocol contract.

### 2026-05-05 — Fact Override Narrowing

The Fact Overlay helper is intentionally scoped to current active single-value field facts. Multi-action overlay, add/remove facts, and generic `EvaluationOverlay` are Batch 3 concerns. If a field has no current active fact or has an unsupported arity, the helper raises `CapabilityHelperError` rather than inventing future semantics.

### 2026-05-05 — Why-not Builder Input

The Why-not helper accepts rows as mappings or sequences and normalizes them against `plan.heads[0].head_var_names`. It does not infer values from hydrated entities or schema fields; doing that would couple the helper to domain-specific object shapes and exceed Batch 2.
