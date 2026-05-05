# Task Blueprint Audit: Evaluator Near-miss Architecture Step 0

- Blueprint: [2026-05-05_evaluator-near-miss-architecture-step0.md](./2026-05-05_evaluator-near-miss-architecture-step0.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-05 | draft | Blueprint created | Opened evaluator architecture Step 0 as the natural follow-up fork from Why-not Shape B deferral. |
| 2026-05-05 | draft | Step 0.A source pass drafted | Read native evaluator, RuleRef wrapper, Store evaluation surface, Diagnose localizer, Souffle / ProbLog / PyReason adapters, and Why-not reference anchors. |

## Decision Notes

### 2026-05-05 — Direction Selection

The next high-signal direction is evaluator architecture, not a fifth application capability and not preview-line consolidation. The reason is source-backed continuity: Why-not Universe Diagnose Step 0 explicitly deferred true near-miss / exclusion-reason Why-not as evaluator architecture territory. This spike tests that deferred fork directly.

Step 0 is intentionally allowed to abandon. A crisp evaluator trace DTO is not assumed. If the source pass shows the only useful shape requires open-ended search, opaque adapter payloads, or unstable evaluator internals, the correct output is a blocker note rather than implementation.

### 2026-05-05 — Step 0.A Native Evaluator Finding

`src/kernel/core/rules/where_eval.py` has transient failure information only as control flow. `_eval_body(...)` starts with one empty env, applies each atom evaluator, and replaces the env list with surviving envs. If no env survives, it returns `[]`. Each atom evaluator returns only surviving envs; rejected facts, rejected envs, and failed atom details are not retained as typed rows.

`src/kernel/core/rules/ruleref_substrate.py` confirms the public native wrapper shape: `NativeWhereEvaluation(bindings, rule_refs, rule_ref_resolutions)`. RuleRef metadata is success-side resolution / support state. It does not expose failed branches, rejected RuleRef rows, or near-miss candidates.

Conclusion: E1 is not "already available". It would require a new native return shape or a separate native trace entrypoint. A callback or free-form trace kwarg is not acceptable for this spike because it hides the contract boundary.

### 2026-05-05 — Step 0.A Diagnose Is Not General Near-miss

`src/kernel/application/diagnose_runtime.py` already imports native private atom evaluators and uses `_localize_failed_atom(...)` to replay a single requested binding. This is a bounded and useful localizer, but it is seeded by a concrete binding. It does not discover a missing candidate universe or an evaluator-global failed frontier.

Conclusion: a future E1 must prove it adds value beyond "Diagnose but lower in the stack". If the only crisp shape is seeded binding -> failed atom, the work is likely redundant with shipped Diagnose / Why-not Universe Diagnose.

### 2026-05-05 — Step 0.A Store Evaluation Boundary

`src/kernel/core/store/_evaluate.py` builds support artifacts only for successful native `evaluation.bindings`, and the Store engine adapter contract returns `list[CandidateSet]`. There is no slot for failed candidates or failed branch rows. Existing `_remember_*` indexes are success support / provenance indexes.

Conclusion: evaluator near-miss cannot be smuggled through current `CandidateSet` without corrupting candidate semantics. A scoped implementation would need an explicit evaluator-layer DTO boundary.

### 2026-05-05 — Step 0.A Souffle Finding

`src/kernel/adapters/souffle/engine_eval.py` compiles a query relation, runs Souffle, reads query output facts, and optionally reads witness columns. Witness rows require a satisfying branch and build support artifacts for successful bindings. Missing output means no candidates, not a typed failed row set.

Conclusion: Souffle offers success witnesses, not failed query instrumentation. E2 cannot claim Souffle near-miss support without adapter architecture work.

### 2026-05-05 — Step 0.A ProbLog Finding

`src/kernel/adapters/problog/engine_eval.py` runs ProbLog with `trace=True`, parses query answers into candidates, and attaches a `proof_trace` provenance envelope to successful candidates. `src/kernel/adapters/problog/provenance.py` parses call/result/complete/fail events, but these are adapter-local textual proof events. They are not typed candidate-exclusion rows and are not aligned to a caller-supplied candidate universe.

Conclusion: ProbLog's trace is useful success-side provenance. Treating it as cross-engine near-miss would require a new mapping from textual failed goals to candidate identities and exclusion reasons.

### 2026-05-05 — Step 0.A PyReason Finding

`src/kernel/adapters/pyreason/engine_eval.py` runs with `atom_trace=True`, extracts derived facts from the interpretation, and attaches a `event_log` provenance envelope to successful candidates. `src/kernel/adapters/pyreason/provenance.py` explicitly describes the carrier as adapter-local V0 event log of bound changes, not a core contract or proof tree.

Conclusion: PyReason provides a success/provenance event log, not failed-candidate semantics. E2 would need engine-specific interpretation work rather than a simple shared DTO.

### 2026-05-05 — Step 0.A Shape Read

E1 is the only non-redundant candidate worth carrying into Step 0.B, but only as native-only architecture and only if Step 0.B can name a bounded frontier DTO. E2 is not crisp today: Souffle, ProbLog, and PyReason expose different success/provenance carriers, not shared failed-frontier contracts. E3 is presumed redundant with shipped Why-not Universe Diagnose unless it proves genuine evaluator-layer batching or cost-model value.

If E1 cannot avoid opaque env dumps, callbacks, trace mode flags, or Diagnose duplication, valid abandonment is the correct Step 0 result.
