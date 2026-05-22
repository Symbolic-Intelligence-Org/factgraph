# Task Blueprint Audit: Rule Run Trace Schema Contract

- Blueprint: [2026-03-17_rule-run-trace-schema-contract.md](./2026-03-17_rule-run-trace-schema-contract.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-17 | draft | Blueprint created | Opened a follow-on slice after explain-ref unification to reframe `rule_run` around schema/contract freeze rather than first-time trace capture. |
| 2026-03-17 | scoped | Scope frozen | Locked the first-round `ruleref_links` shape, memo-hit linkage semantics, `non_fact_steps.status` normalization strategy, and `rule_run` service payload contract boundary. |
| 2026-03-17 | implementing | Implementation started | Began the core trace schema, serde, focused tests, and docs update pass for `ruleref_links`, status normalization, and rule-run payload contract cleanup. |
| 2026-03-17 | implemented | Slice completed | Landed `ruleref_links`, legacy status normalization, focused rule-trace tests, and service/core docs updates; phase-3 contracts passed end-to-end. |

## Decision Notes

- 2026-03-17: The current `rule_run` gap is no longer “missing trace capture”; the real work is to freeze trace schema semantics and the service payload contract around an already-existing `RuleTraceArtifact`.
- 2026-03-17: The parent runtime traceability/explainability blueprint contains older wording that treats `rule_run` trace as largely unimplemented; this slice should use code reality as the source of truth and only later reconcile the parent framing.
- 2026-03-17: The first-round open questions are intentionally narrowed to `non_fact_steps.status`, `ruleref` atom linkage, and service response documentation; `original_where` / `rewritten_where` remain intentionally opaque unless a later slice says otherwise.
- 2026-03-17: `ruleref` atom linkage should use a dedicated `ruleref_links` field on `RuleTraceInvocation`, not an overload of `pred_witnesses` or `non_fact_steps`; the link should point to the actual child invocation created for that call-site, including memo-hit invocations.
- 2026-03-17: The current implementation may rely on reading `trace_ctx.invocations[-1]` immediately after `_evaluate_rule(...)` returns inside `rewrite_atom(...)`; this is acceptable only as an explicit, narrowly-scoped implementation constraint, not as an ambient inference rule.
- 2026-03-17: `RuleTraceNonFactStep.status` should move to `negated` / `evaluated` for new writes, while readers keep a legacy normalization path from `no_match` / `satisfied`.
- 2026-03-17: The first-round `rule_run` service contract should document a stable typed subset of the trace payload and explicitly keep `original_where`, `rewritten_where`, and `non_fact_steps.details.atom` opaque.
- 2026-03-17: Acceptance should verify actual `run_rule_with_trace(...)` capture behavior, serde compatibility, and docs boundary updates, rather than only restating design intent.
- 2026-03-17: The implementation kept `RuleTraceRuleRefLink` validation intentionally minimal (non-empty strings only); the stable guarantee is the writer-generated key format and serialized contract, not regex-level rejection of all external inputs.
