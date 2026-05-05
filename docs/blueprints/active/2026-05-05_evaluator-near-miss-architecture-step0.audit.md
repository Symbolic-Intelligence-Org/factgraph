# Task Blueprint Audit: Evaluator Near-miss Architecture Step 0

- Blueprint: [2026-05-05_evaluator-near-miss-architecture-step0.md](./2026-05-05_evaluator-near-miss-architecture-step0.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-05 | draft | Blueprint created | Opened evaluator architecture Step 0 as the natural follow-up fork from Why-not Shape B deferral. |
| 2026-05-05 | draft | Step 0.A source pass drafted | Read native evaluator, RuleRef wrapper, Store evaluation surface, Diagnose localizer, Souffle / ProbLog / PyReason adapters, and Why-not reference anchors. |
| 2026-05-05 | draft | Step 0.B crispness decision recorded | Selected native-only aggregate frontier trace as crisp enough for Step 0.C; rejected cross-engine trace and repeated probe shapes. |
| 2026-05-05 | draft | Step 0.C contract frozen | Froze separate native entrypoint, aggregate row DTO, no sample binding, native-only gate, and 10 drift gates. |

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

Carry this pre-freeze sketch into Step 0.C:

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

Step 0.C supersedes this sketch. In particular, `sample_binding` is rejected in the frozen row DTO.

### 2026-05-05 — Step 0.C Entrypoint Freeze

The implementation entrypoint is frozen as a separate native function:

```text
evaluate_native_where_frontier(
  view_facts,
  where,
  *,
  registry=None,
  witness_facts=None,
  remember_support_artifact=None,
) -> NativeWhereFrontierEvaluation
```

It mirrors `evaluate_native_where(...)` rather than extending it with a trace flag. This preserves all existing application callers and keeps the Why-not no-trace-kwarg gate intact.

### 2026-05-05 — Step 0.C Row DTO Freeze

The row DTO is aggregate-only:

```text
NativeWhereFrontierRow(
  branch_index,
  failed_atom_index,
  atoms_satisfied,
  frontier_count,
  failure_kind,
)
```

`failure_kind` is frozen to `Literal["empty_input", "atom_filter_empty"]`.

`atoms_satisfied` is intentionally redundant with `failed_atom_index` in the initial contract. Keeping both names is worth it: `failed_atom_index` is locator semantics, while `atoms_satisfied` is product / diagnostic semantics. The invariant `atoms_satisfied == failed_atom_index` is a drift gate.

### 2026-05-05 — Step 0.C Sample Binding Decision

`sample_binding` is rejected. The value is attractive for debugging, but it would stabilize internal env dictionaries as part of the public evaluator contract and reopen the rejected per-partial-env dump path.

The stable MVP should expose counts and locators only. If implementation or UX later needs samples, that should be a separate debug-only helper or a new scoped blueprint with its own boundedness rules.

### 2026-05-05 — Step 0.C Frontier Count Semantics

`frontier_count` means the number of environments entering the failed atom, before the atom evaluator runs. It is never the number of failed output envs. For normal branches this count is positive. `empty_input` is reserved for defensive completeness if a future helper can enter a branch with no envs; the normal algorithm starts each branch with `[{}]`.

### 2026-05-05 — Step 0.C RuleRef Boundary

RuleRef behavior mirrors `evaluate_native_where(...)`: preflight, rewrite, overlay, and success-side support resolution remain unchanged. Frontier rows are computed after RuleRef rewrite against the resolved native body. The contract does not expose failed child-rule internals or rejected RuleRef rows.

This keeps the initial native frontier contract small. If nested RuleRef failed-frontier explanation is needed later, it should be a separate expansion.

### 2026-05-05 — Step 0.C Native-only Gate

The engine gate is intentionally one line: this is native-only evaluator architecture. Souffle, ProbLog, and PyReason adapter traces are explicitly out of scope.

Therefore Step 0.C does not open §6.7. A future cross-engine trace abstraction would be a separate blueprint.

### 2026-05-05 — Step 0.C Drift Gate Inventory

The scoped implementation must lock these gates:

1. **§7-EvaluatorFrontier-1** separate entrypoint: normal `evaluate_native_where(...)` signature and `NativeWhereEvaluation` fields stay unchanged.
2. **§7-EvaluatorFrontier-2** no trace kwargs on normal evaluation.
3. **§7-EvaluatorFrontier-3** layer separation: no application / SDK / adapter / candidate / evidence payload imports in core rules frontier DTOs.
4. **§7-EvaluatorFrontier-4** bounded rows: at most one frontier row per normalized OR branch.
5. **§7-EvaluatorFrontier-5** no env dump or opaque details field.
6. **§7-EvaluatorFrontier-6** deterministic count invariant: `atoms_satisfied == failed_atom_index`, `frontier_count` is pre-atom input env count.
7. **§7-EvaluatorFrontier-7** success parity with `evaluate_native_where(...)`.
8. **§7-EvaluatorFrontier-8** native-only scope: no adapter API or engine evaluator contract changes.
9. **§7-EvaluatorFrontier-9** no new persistence beyond existing success-side support artifact behavior.
10. **§7-EvaluatorFrontier-10** no application behavior change unless a later scoped blueprint opts in.
