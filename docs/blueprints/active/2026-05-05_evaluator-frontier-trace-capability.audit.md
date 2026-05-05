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
| 2026-05-05 | scoped | Step 1 DTO and entry scaffold complete | Added isolated core rules frontier module with frozen DTOs and a parity-preserving scaffold entrypoint. |
| 2026-05-05 | scoped | Step 2 frontier algorithm complete | Replaced scaffold frontier rows with per-branch aggregate emission, RuleRef post-rewrite frontier evaluation, and success-parity coverage across native path shapes. |
| 2026-05-05 | scoped | Step 3 drift gates complete | Added named §7-EvaluatorFrontier anti-regression tests covering surface, boundedness, parity, native-only scope, persistence, and application back-dependency gates. |

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

### 2026-05-05 — Step 1 Placement And Scaffold

Step 1 uses a new `kernel.core.rules.frontier` module instead of adding the frontier surface to `ruleref_substrate.py`. The physical split keeps the frontier contract easy to scan for layer-boundary drift while still allowing Step 2 to share private evaluator helpers if needed.

The first entrypoint implementation delegates to `evaluate_native_where(...)` and returns identical success-side fields with `frontier_rows=()`. This keeps Step 1 limited to DTO / signature / layer scaffolding while establishing success parity early. Step 2 will replace the empty frontier row behavior for failed branches with the frozen aggregate algorithm.

### 2026-05-05 — Step 2 Helper Sharing Decision

Step 2 rejected adding a frontier collector parameter to `where_eval._eval_body(...)`. Because `kernel.core.rules.frontier` owns the frontier DTOs, making `where_eval.py` import those row types would create the wrong dependency direction (`frontier -> ruleref_substrate -> where_eval -> frontier`) or require moving DTOs back into the normal evaluator surface.

The implementation instead keeps `evaluate_native_where(...)` unchanged and computes frontier rows inside `kernel.core.rules.frontier` by reusing the same private atom evaluator helpers as normal `evaluate_where(...)`. This is an isolated helper-walk, not a new public trace kwarg, callback, or env dump.

### 2026-05-05 — Step 2 RuleRef Frontier Boundary

RuleRef handling mirrors the scoped contract: preflight, rewrite, overlay, and success-side resolution use the existing RuleRef substrate helpers. Frontier rows are then computed on the rewritten parent native body.

This means parent-level RuleRef atoms can contribute to a frontier row after they have been rewritten into internal native predicates, but failed child-rule internals remain out of scope. That preserves the Step 0.C RuleRef boundary while proving success parity for RuleRef callers.

### 2026-05-05 — Step 3 Gate Mapping

Step 3 added `src/kernel/tests/test_core_rules_frontier_drift_gates.py` as the named anti-regression layer. The existing focused behavior tests in `test_core_rules_frontier.py` continue to prove DTO and algorithm behavior; the new file maps the §7 gates explicitly:

| Gate | Test coverage |
| --- | --- |
| §7-EvaluatorFrontier-1 separate entrypoint | `test_1_separate_entrypoint_keeps_normal_native_surface_unchanged` |
| §7-EvaluatorFrontier-2 no trace kwargs | `test_2_no_trace_kwargs_on_normal_or_frontier_entrypoints` |
| §7-EvaluatorFrontier-3 layer separation | `test_3_frontier_module_imports_no_upper_layers_or_payload_dtos` |
| §7-EvaluatorFrontier-4 bounded rows | `test_4_bounded_rows_emit_at_most_one_row_per_normalized_branch` |
| §7-EvaluatorFrontier-5 no env dump | `test_5_frontier_rows_expose_no_env_dump_or_opaque_payload` |
| §7-EvaluatorFrontier-6 deterministic counts | `test_6_deterministic_counts_are_pre_atom_input_counts` |
| §7-EvaluatorFrontier-7 success parity | `test_7_success_parity_covers_native_path_shapes` plus Step 2 focused parity tests |
| §7-EvaluatorFrontier-8 native-only scope | `test_8_frontier_scope_stays_native_only` |
| §7-EvaluatorFrontier-9 no persistence | `test_9_frontier_evaluation_adds_no_new_persistence_callback` and `test_9_frontier_module_does_not_import_or_call_write_substrates` |
| §7-EvaluatorFrontier-10 no application back-dependency | `test_10_application_layer_does_not_opt_into_frontier_trace` |
