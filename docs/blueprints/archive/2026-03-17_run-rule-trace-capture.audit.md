# Task Blueprint Audit: Run Rule Trace Capture

- Blueprint: [2026-03-17_run-rule-trace-capture.md](./2026-03-17_run-rule-trace-capture.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-17 | draft | Blueprint created | Opened a dedicated child blueprint for `run_rule(...)` trace capture after derivation support capture/readback had already been completed. |
| 2026-03-17 | scoped | Blueprint tightened for implementation | Locked the first-slice carrier and control-flow decisions: keep `SupportArtifact` separate, store both `original_where` and `rewritten_where`, use explicit `trace_ctx` parameter passing, and use a mutable accumulator context under a shared `_run_rule_core(...)` path. |
| 2026-03-17 | implemented | Trace carrier and runtime path landed | Added `RuleTraceArtifact` carrier, `run_rule_with_trace(...)`, store-level trace registry/readback, and explicit memo-hit capture for repeated `RuleRef` call sites. |
| 2026-03-17 | validated | Static compile + runtime smoke passed | `compileall` passed; a `run_rule_with_trace(...)` smoke produced a `rule_run_id`, `Store.explain_rule_trace(...)` returned non-`None`, repeated `RuleRef` produced one primary invocation plus one `memo_hit=True` invocation, and an existing `sdk.run(...)` rule test still passed under `unittest`. |
| 2026-03-17 | validated | Formal regression test added | Added a focused `Phase3ContractsV1Tests.test_run_rule_with_trace_captures_readback_and_memo_hits` case in `src/factpy_kernel/tests/test_phase3_contracts_v1.py` and re-ran it together with the existing RuleRef syntax-matrix test under `unittest`. |

## Decision Notes

- 2026-03-17: `run_rule(...)` is treated as an execution root distinct from `Store.evaluate(...)`; `RuleRef` expansion is captured under this root rather than being forced into the derivation candidate model.
- 2026-03-17: The current rule runtime has almost no reusable tracing infrastructure beyond `_evaluate_rule(...)`, `memo_rows`, and `stack`; the first slice therefore needs to introduce both trace hooks and trace carrier shape.
- 2026-03-17: `RuleTraceArtifact` should remain separate from `SupportArtifact`; short-term carrier separation is preferred, with possible future alignment only at the explain/readback protocol layer.
- 2026-03-17: Existing SDK/service/preflight callers should not be forced off `run_rule(...) -> list[tuple]` in the first slice; a traced sibling helper is the current preferred compatibility strategy.
- 2026-03-17: `RuleTraceInvocation` should retain both `original_where` and `rewritten_where`; authoring intent and executed body are both useful and both are cheaply available in the current code path.
- 2026-03-17: Trace state should be threaded explicitly via `trace_ctx: RuleTraceCaptureContext | None = None`; thread-local or other implicit state is not justified for the first slice.
- 2026-03-17: `RuleTraceCaptureContext` should use a mutable accumulator (`invocations.append(...)`) rather than forcing recursive `(rows, invocations)` merges through every `_evaluate_rule(...)` return path.
- 2026-03-17: A shared `_run_rule_core(...)` path is preferred so that `run_rule(...)` and `run_rule_with_trace(...)` do not fork the rule runtime implementation.
- 2026-03-17: Because `memo_rows` caches by `(rule_id, version)`, `RuleRef` relationships are not always a strict tree; the first slice should model memo reuse explicitly via per-call-site invocations plus `memo_hit` / `memo_source_invocation_id`.
- 2026-03-17: The first slice should close the loop in-process with `Store.explain_rule_trace(rule_run_id)` rather than stopping at capture-only; otherwise there is no practical way to validate or consume the carrier.
