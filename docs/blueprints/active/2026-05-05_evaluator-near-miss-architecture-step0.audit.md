# Task Blueprint Audit: Evaluator Near-miss Architecture Step 0

- Blueprint: [2026-05-05_evaluator-near-miss-architecture-step0.md](./2026-05-05_evaluator-near-miss-architecture-step0.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-05 | draft | Blueprint created | Opened evaluator architecture Step 0 as the natural follow-up fork from Why-not Shape B deferral. |
| 2026-05-05 | draft | Step 0.A source pass drafted | Read native evaluator, RuleRef wrapper, Store evaluation surface, Diagnose localizer, Souffle / ProbLog / PyReason adapters, and Why-not reference anchors. |
| 2026-05-05 | draft | Step 0.B crispness decision recorded | Selected native-only aggregate frontier trace as crisp enough for Step 0.C; rejected cross-engine trace and repeated probe shapes. |

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

### 2026-05-05 — Step 0.B Frontier Granularity

Three E1 granularities were considered:

1. **Per-partial-env dump.** This is the closest to the evaluator's live control flow, but it is not a crisp DTO. It would expose internal dictionaries, join cardinality, and atom evaluator details that are not stable. It also risks becoming an unbounded debug stream.
2. **Seeded candidate failure.** This is crisp, but it is mostly Diagnose under another name. Diagnose already seeds one binding and localizes a failed atom. Moving that helper down one layer may be useful later, but it is not enough to justify an evaluator architecture blueprint by itself.
3. **Per-branch aggregate frontier.** This is bounded by the number of OR branches and atom positions. It can report the furthest atom reached, how many environments reached that frontier, and a representative binding sample without exposing every rejected env.

Decision: carry **per-branch aggregate frontier** into Step 0.C.

### 2026-05-05 — Step 0.B Entrypoint Decision

Two implementation-altitude options were considered:

- Extending `NativeWhereEvaluation` with an optional frontier field.
- Adding a separate native trace entrypoint.

Decision: prefer a **separate native trace entrypoint** for Step 0.C. Normal `evaluate_native_where(...)` callers should keep receiving the existing evaluation result shape and should not grow accidental dependencies on frontier fields. A separate entrypoint also resolves the Why-not §7-WhyNot-13 concern: no trace/callback kwarg is added to the existing evaluator call.

The separate entrypoint can still share private implementation with normal native evaluation if Step 0.C finds a clean helper split.

### 2026-05-05 — Step 0.B Non-redundancy With Diagnose

Diagnose answers a seeded question: "Does this requested binding pass, and if not, which atom blocks it?" The selected E1 shape answers an unseeded evaluator question: "During this native body evaluation, where did each branch frontier collapse, and how much partial work reached that frontier?"

This is enough new value to continue Step 0. It is not yet enough to authorize implementation. Step 0.C must freeze exact row fields and decide whether `sample_binding` is stable enough to include.

### 2026-05-05 — Step 0.B Rejected Shapes

E2 cross-engine trace is rejected for this blueprint. Souffle lacks failed rows, ProbLog has adapter-local textual `fail` events, and PyReason has adapter-local bound-change events. These may justify future adapter-specific work, especially ProbLog failure parsing, but they do not form a shared evaluator trace DTO today.

E3 repeated bounded probe is rejected as redundant with shipped Why-not Universe Diagnose. If a future performance topic wants to batch repeated probes, it should be framed as an optimization of existing semantics, not a new evaluator near-miss architecture.

### 2026-05-05 — Step 0.B Crispness Decision

Proceed to Step 0.C with native-only aggregate frontier trace:

```text
evaluate_native_where_frontier(...)
  -> NativeWhereFrontierEvaluation(bindings, rule_refs, rule_ref_resolutions, frontier_rows)

NativeWhereFrontierRow(
  branch_index,
  failed_atom_index,
  atoms_satisfied,
  frontier_count,
  failure_kind,
  sample_binding,
)
```

Exact names and fields remain provisional. Step 0.B freezes only the direction: typed aggregate rows, native-only, separate entrypoint, no application DTO dependency, no callback, no mode flag, no search budget, and no `CandidateSet` pollution.
