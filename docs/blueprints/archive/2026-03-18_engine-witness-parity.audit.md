# Task Blueprint Audit: Engine Witness Parity

- Blueprint: [2026-03-18_engine-witness-parity.md](./2026-03-18_engine-witness-parity.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-18 | draft | Blueprint created | Opened the remaining explainability slice around engine witness parity after native support capture, explain-ref unification, and rule-run trace schema freeze had already landed. |
| 2026-03-18 | scoped | Scope frozen | Locked the first-round degraded marker, `candidate_id -> support_kind` Store index, and `candidate` degraded explain semantics for engine no-witness paths. |
| 2026-03-18 | implementing | Implementation started | Began the support-kind constant, Store index, candidate explain, focused test, and docs update pass for explicit engine degraded explain semantics. |
| 2026-03-18 | implemented | Slice delivered | Landed explicit `engine_no_witness_v1` writer semantics, `Store` support-kind indexing, engine-mode backref registration, degraded `candidate` explain payloads, focused contract tests, and core/service/adapter docs sync. |

## Decision Notes

- 2026-03-18: The first-round engine witness parity problem should be framed around explicit degraded explain semantics, not around immediately forcing true witness parity with native mode.
- 2026-03-18: `_coerce_binding_rows(bindings=...)` is the current architecture choke point where engine rows become `support_kind="none"` plus a zero digest; this must be treated as a first-class design fact, not hidden compatibility behavior.
- 2026-03-18: `souffle` and `problog` should be discussed separately at the evidence-production layer, but together at the `CandidateSet` / service degradation-contract layer.
- 2026-03-18: New writer behavior should stop emitting `support_kind="none"` and instead use an explicit degraded marker `engine_no_witness_v1`; the zero digest may remain as a compatibility placeholder, but it must not be the semantic discriminator.
- 2026-03-18: The first-round service solution should add a `candidate_id -> support_kind` index in `Store`; relying on zero-digest pattern matching inside `explain_ref` would make degraded semantics depend on a magic constant.
- 2026-03-18: Engine-no-witness candidates should surface as `ok=true` degraded explains, not as `not_found`; missing artifact readback remains a separate problem from structurally absent witness data.
- 2026-03-18: Acceptance should verify writer behavior, Store indexing, degraded explain semantics, and docs sync explicitly; this slice is no longer just an exploratory framing draft.
- 2026-03-18: Implementation uncovered one additional required bridge: `evaluate_store(...)` had to register candidate support backrefs after `souffle` / `problog` evaluator returns, because the pre-existing engine branches bypassed `_remember_candidate_support_backrefs(...)` entirely.
