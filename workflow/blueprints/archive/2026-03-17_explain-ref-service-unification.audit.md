# Task Blueprint Audit: Explain Ref Service Unification

- Blueprint: [2026-03-17_explain-ref-service-unification.md](./2026-03-17_explain-ref-service-unification.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-17 | draft | Blueprint created | Opened the post-durability service-level explain unification slice after support artifacts, rule traces, sidecar durability, and retention/GC had already landed. |
| 2026-03-17 | scoped | Scope frozen | Locked the first-round `explain_ref` kinds, the unified `/queries/explain` endpoint, envelope shape, assertion narrowing, candidate first-hop session scope, and compatibility constraints for legacy explain endpoints. |
| 2026-03-17 | implementing | Implementation started | Began the service/runtime implementation pass for the unified explain endpoint, compatibility wrappers, focused contract tests, and service docs updates. |
| 2026-03-17 | implemented | Slice completed | Landed `explain_runtime_ref(...)`, registered the unified route, preserved legacy explain endpoint schemas, added focused contract tests, and updated runtime service docs. |

## Decision Notes

- 2026-03-17: `explain_ref` should be treated as a service-layer contract problem, not as a reason to add new proof-entry identifiers to core candidate schemas.
- 2026-03-17: The new slice starts only after durable explain handle semantics became stable enough through sidecar readback and retention/GC work.
- 2026-03-17: `candidate`, `assertion`, and `rule_run` are the minimum kinds worth discussing in the first service-level unification round.
- 2026-03-17: The blueprint should compare “new unified explain endpoint” against “keep separate endpoints but unify the handle DTO” before freezing the service shape.
- 2026-03-17: `candidate` should remain a session-scoped weak-durable convenience kind; only the second hop (`support_digest` deref) is sidecar-durable, while `candidate_id -> support_digest` stays in-memory.
- 2026-03-17: `assertion` should use narrow single-`asrt_id` deref semantics rather than widening to the existing pair-level `explain_fact(pred_id, e_ref, ...)` query contract.
- 2026-03-17: `explain-fact` should remain outside `explain_ref`; it is a predicate/entity query surface, not an identity/artifact deref surface.
- 2026-03-17: `Ledger.get_claim(asrt_id)` is sufficient as the first lookup step for `assertion` kind; this slice does not need new ledger storage primitives, only a service/core bridge.
- 2026-03-17: The first unified service shape should add a new `POST /queries/explain` endpoint while keeping `explain-support` and `explain-rule-trace` as compatibility wrappers.
- 2026-03-17: Unified explain responses should use an envelope with top-level `kind` plus `explain`, not raw payload passthrough or a separate summary/detail contract.
- 2026-03-17: Service v1 keeps its existing `HTTP 200` + `ok/errors` envelope rule; invalid or unsupported `kind` values must surface as `shape` errors, not `HTTP 4xx/5xx`.
- 2026-03-17: Legacy `explain-support` and `explain-rule-trace` endpoints may reuse the new unified resolution path internally, but they must preserve their pre-unification response schemas and must not gain a top-level `kind` field.
- 2026-03-17: `explain-fact` remains semantically separate from `explain_ref`; the unified endpoint should not accept `kind="fact"`.
- 2026-03-17: The first implementation round keeps `assertion` payload intentionally narrow and does not expand it with claim-arg or meta rows.
- 2026-03-17: The legacy support/trace endpoints were kept on their existing facade code paths; the accepted contract is behavioral compatibility, not mandatory wrapper indirection.
