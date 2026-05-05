# Task Blueprint Audit: Evaluator Frontier Trace Capability

- Blueprint: [2026-05-05_evaluator-frontier-trace-capability.md](./2026-05-05_evaluator-frontier-trace-capability.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-05 | draft | Blueprint created | Opened evaluator architecture Step 0 as the natural follow-up fork from Why-not Shape B deferral. |
| 2026-05-05 | draft | Step 0.A source pass drafted | Read native evaluator, RuleRef wrapper, Store evaluation surface, Diagnose localizer, Souffle / ProbLog / PyReason adapters, and Why-not reference anchors. |
| 2026-05-05 | draft | Step 0.B crispness decision recorded | Selected native-only aggregate frontier trace as crisp enough for Step 0.C; rejected cross-engine trace and repeated probe shapes. |
| 2026-05-05 | draft | Step 0.C contract frozen | Froze separate native entrypoint, aggregate row DTO, no sample binding, native-only gate, and 10 drift gates. |
| 2026-05-05 | draft -> scoped | Step 0.D lift complete | Renamed blueprint to Evaluator Frontier Trace Capability, lifted Step 0 decisions into authoritative §5 / §7 / §8, and authorized implementation only through the scoped plan. |

## Decision Notes

### 2026-05-05 — Direction Selection

The next high-signal direction is evaluator architecture, not a fifth application capability and not preview-line consolidation. The reason is source-backed continuity: Why-not Universe Diagnose Step 0 explicitly deferred true near-miss / exclusion-reason Why-not as evaluator architecture territory. This spike tests that deferred fork directly.

Step 0 was intentionally allowed to abandon. A crisp evaluator trace DTO was not assumed.

### 2026-05-05 — Step 0.A Native Evaluator Finding

`src/kernel/core/rules/where_eval.py` has transient failure information only as control flow. `_eval_body(...)` starts with one empty env, applies each atom evaluator, and replaces the env list with surviving envs. If no env survives, it returns `[]`. Each atom evaluator returns only surviving envs; rejected facts, rejected envs, and failed atom details are not retained as typed rows.

`src/kernel/core/rules/ruleref_substrate.py` confirms the public native wrapper shape: `NativeWhereEvaluation(bindings, rule_refs, rule_ref_resolutions)`. RuleRef metadata is success-side resolution / support state. It does not expose failed branches, rejected RuleRef rows, or near-miss candidates.

Conclusion: E1 was not "already available". It requires a new native return shape or a separate native trace entrypoint. Callback / free-form trace kwargs were rejected because they hide the contract boundary.

### 2026-05-05 — Step 0.A Diagnose Is Not General Near-miss

`src/kernel/application/diagnose_runtime.py` already imports native private atom evaluators and uses `_localize_failed_atom(...)` to replay a single requested binding. This is a bounded and useful localizer, but it is seeded by a concrete binding. It does not discover a missing candidate universe or an evaluator-global failed frontier.

Conclusion: the selected evaluator frontier trace must answer an unseeded branch-frontier question rather than repackage Diagnose.

### 2026-05-05 — Step 0.A Store Evaluation Boundary

`src/kernel/core/store/_evaluate.py` builds support artifacts only for successful native `evaluation.bindings`, and the Store engine adapter contract returns `list[CandidateSet]`. There is no slot for failed candidates or failed branch rows. Existing `_remember_*` indexes are success support / provenance indexes.

Conclusion: evaluator near-miss cannot be smuggled through current `CandidateSet` without corrupting candidate semantics.

### 2026-05-05 — Step 0.A Adapter Findings

Souffle compiles a query relation, runs Souffle, and reads query output facts / witness columns. Witness rows require a satisfying branch; missing output means no candidates, not a typed failed row set.

ProbLog runs with `trace=True`, parses query answers into candidates, and attaches a `proof_trace` provenance envelope to successful candidates. `fail` events are adapter-local textual proof events, not typed candidate-exclusion rows aligned to a universe.

PyReason runs with `atom_trace=True`, extracts derived facts from the interpretation, and attaches an adapter-local `event_log` provenance envelope to successful candidates. The event log records bound changes, not failed-candidate semantics.

Conclusion: cross-engine E2 is not crisp for this blueprint.

### 2026-05-05 — Step 0.B Frontier Granularity

Three E1 granularities were considered:

1. **Per-partial-env dump** — rejected because it exposes internal dictionaries, join cardinality, and unstable atom evaluator details.
2. **Seeded candidate failure** — rejected as primary shape because it mostly collapses into Diagnose.
3. **Per-branch aggregate frontier** — selected because it is bounded by OR branches and atom positions, while reporting where each native branch collapsed.

Decision: carry per-branch aggregate frontier into implementation.

### 2026-05-05 — Step 0.B Entrypoint Decision

Two options were considered:

- Extend `NativeWhereEvaluation` with an optional frontier field.
- Add a separate native trace entrypoint.

Decision: use a separate native trace entrypoint. Normal `evaluate_native_where(...)` callers keep the existing result shape and cannot accidentally depend on frontier fields. This also preserves the Why-not no-trace-kwarg drift gate.

### 2026-05-05 — Step 0.B Non-redundancy With Diagnose

Diagnose answers a seeded question: "Does this requested binding pass, and if not, which atom blocks it?" The selected E1 shape answers an unseeded evaluator question: "During this native body evaluation, where did each branch frontier collapse, and how much partial work reached that frontier?"

This is enough new value to scope implementation.

### 2026-05-05 — Step 0.B Rejected Shapes

E2 cross-engine trace is rejected for this blueprint. Souffle lacks failed rows, ProbLog has adapter-local textual `fail` events, and PyReason has adapter-local bound-change events. Future adapter-specific work, especially ProbLog failure parsing, may be useful but does not form a shared evaluator trace DTO today.

E3 repeated bounded probe is rejected as redundant with shipped Why-not Universe Diagnose. If a future performance topic wants to batch repeated probes, it should be framed as an optimization of existing semantics.

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

`atoms_satisfied` is intentionally redundant with `failed_atom_index`: `failed_atom_index` is locator semantics, while `atoms_satisfied` is product / diagnostic semantics. The invariant `atoms_satisfied == failed_atom_index` is a drift gate.

### 2026-05-05 — Step 0.C Sample Binding Decision

`sample_binding` is rejected. The value is attractive for debugging, but it would stabilize internal env dictionaries as part of the public evaluator contract and reopen the rejected per-partial-env dump path.

The stable MVP should expose counts and locators only. If implementation or UX later needs samples, that should be a separate debug-only helper or a new scoped blueprint with its own boundedness rules.

### 2026-05-05 — Step 0.C Frontier Count Semantics

`frontier_count` means the number of environments entering the failed atom, before the atom evaluator runs. It is never the number of failed output envs. For normal branches this count is positive. `empty_input` is reserved for defensive completeness if a future helper can enter a branch with no envs; the normal algorithm starts each branch with `[{}]`.

### 2026-05-05 — Step 0.C RuleRef Boundary

RuleRef behavior mirrors `evaluate_native_where(...)`: preflight, rewrite, overlay, and success-side support resolution remain unchanged. Frontier rows are computed after RuleRef rewrite against the resolved native body. The contract does not expose failed child-rule internals or rejected RuleRef rows.

If nested RuleRef failed-frontier explanation is needed later, it should be a separate expansion.

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

### 2026-05-05 — Step 0.D Scope Lift

Step 0.A through 0.C produced a crisp, bounded, native-only evaluator trace contract. Step 0.D lifted the task from spike to scoped implementation by:

- renaming the active blueprint from `evaluator-near-miss-architecture-step0` to `evaluator-frontier-trace-capability`;
- setting status to `scoped`;
- replacing Step 0 scaffolding with authoritative contract / acceptance / implementation plan sections;
- keeping cross-engine trace, adapter-specific failure parsing, and application capability consumers out of scope.
