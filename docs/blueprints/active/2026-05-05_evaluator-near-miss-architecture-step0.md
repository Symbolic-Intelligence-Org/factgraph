# Task Blueprint: Evaluator Near-miss Architecture Step 0

- Status: draft
- Created: 2026-05-05
- Last Updated: 2026-05-05
- Related Modules:
  - `src/kernel/core/rules/`
  - `src/kernel/adapters/`
  - `src/kernel/application/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/references/working/rule-replay-line-redesign-input/README.md](../../references/working/rule-replay-line-redesign-input/README.md)
  - [docs/references/working/rule-replay-line-redesign-input/20_capability-layering-l0-l11.md](../../references/working/rule-replay-line-redesign-input/20_capability-layering-l0-l11.md)
  - [docs/references/working/rule-replay-line-redesign-input/40_design-discussion-A-with-decision-1.md](../../references/working/rule-replay-line-redesign-input/40_design-discussion-A-with-decision-1.md)
  - [docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md](../../references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md)
  - [docs/blueprints/archive/2026-05-05_why-not-universe-diagnose-capability.md](../archive/2026-05-05_why-not-universe-diagnose-capability.md)
  - [docs/blueprints/archive/2026-05-05_why-not-universe-diagnose-capability.audit.md](../archive/2026-05-05_why-not-universe-diagnose-capability.audit.md)
- Audit Log:
  - [2026-05-05_evaluator-near-miss-architecture-step0.audit.md](./2026-05-05_evaluator-near-miss-architecture-step0.audit.md)

## 1. Problem

Why-not Universe Diagnose shipped a bounded candidate-universe board by choosing Shape A-prime: explicit finite universe plus row-level Diagnose mapping. During that Step 0, true Why-not was deliberately rejected as a capability because current evaluators and engine adapters do not expose failed-frontier, near-miss, or exclusion-reason traces.

That rejection created a natural fork: decide whether an evaluator-level near-miss trace contract has a crisp shape. This blueprint is only a Step 0 spike for that fork. If the source pass shows a crisp bounded evaluator DTO and integration boundary, a later blueprint can scope implementation. If not, valid output is abandonment with a precise architecture blocker.

## 2. Goals

- Run a source-backed Step 0 for evaluator near-miss architecture before any implementation.
- Inspect native where evaluation and non-native adapters for existing failed-state, branch-state, or candidate-exclusion data.
- Decide whether a trace DTO shape is crisp enough to scope without `Any`, `**kwargs`, `search_budget`, mode flags, or accidental application-layer coupling.
- Determine whether this work can remain a local evaluator extension or requires §6.7-style declarative capability / engine support schema.
- Record the blocker precisely if true Why-not still cannot be bounded or typed.

## 3. Non-goals

- No evaluator hook, trace callback, adapter change, runtime implementation, protocol DTO, SDK shell, UI, or release-base action in Step 0.
- No fifth application capability in this blueprint.
- No rewrite of Why-not Universe Diagnose; it remains the shipped bounded application capability.
- No broad Explain renderer.
- No carrier persistence, ledger write, or cache semantics.
- No `search_budget`, `limit`, `mode`, `diagnostic_mode`, or open-ended options field as a substitute for a bounded trace contract.
- No changes to `v0.1-oss-prep` or `master`.

## 4. Current Context

### 4.1 Shipped fork point

Why-not Universe Diagnose explicitly split three shapes:

- pure finite-universe carrier board;
- finite-universe carrier board with inline bounded Diagnose;
- true evaluator near-miss / exclusion-reason Why-not.

The shipped capability selected the second shape. The third shape was deferred because it appears to require evaluator or adapter trace state that current public contracts do not expose.

### 4.2 Current evaluator surface

Known starting points for Step 0.A:

- `evaluate_native_where(...)` currently returns final successful bindings plus RuleRef resolution metadata. It is not a failed-branch trace API.
- Diagnose native atom localization can identify a failed atom for one requested binding, but it is a bounded post-failure localizer, not a general near-miss frontier.
- Souffle, ProbLog, and PyReason adapters currently expose derived candidates and success-side evidence/provenance. They do not expose failed candidate traces through the application contract.

These statements must be revalidated against source during Step 0.A before any scope decision.

### 4.3 Step 0.A Source Pass Findings

Step 0.A revalidated the fork against current source. The result is sharper than the initial framing:

| Surface | Current returned state | Failed / near-miss state found? | Step 0.A conclusion |
|---|---|---|---|
| Native `where_eval.evaluate_where(...)` | successful final bindings only | transient `envs` are pruned atom by atom, but rejected environments are not retained or typed | failed-frontier data exists only as control-flow state, not as a return contract |
| Native `ruleref_substrate.evaluate_native_where(...)` | `NativeWhereEvaluation(bindings, rule_refs, rule_ref_resolutions)` | RuleRef support rows are success-side child output / support metadata | wrapper preserves success support, not failures |
| Native store evaluation | `list[CandidateSet]` plus success support artifacts | support is built only after successful bindings | no failed support carrier |
| Diagnose native localization | one requested binding -> optional failed atom locator | yes, but only after seeding a concrete requested binding | bounded post-failure localizer, not general evaluator near-miss |
| Souffle adapter | query output facts, optional witness columns, `CandidateSet` list | no failed rows; witness columns identify satisfying branches only | success/witness adapter, not failed query instrumentation |
| ProbLog adapter | query answers, probabilities, and adapter-local proof trace attached to successful candidates | trace may contain `fail` events, but they are global textual proof events, not candidate-exclusion rows | tempting but not crisp for cross-engine near-miss |
| PyReason adapter | derived node/edge facts, candidate list, adapter-local event log | event log records bound changes, not absence of candidate derivation | success/provenance event log, not failed-candidate universe |
| Store engine contract | engine evaluators return `list[CandidateSet]` | no trace slot or failed-candidate carrier | cross-engine E2 would require contract expansion |

Source anchors:

- `src/kernel/core/rules/where_eval.py`: `_eval_body(...)` starts from `envs = [{}]`, replaces `envs` after each atom, and returns `[]` immediately when a body is exhausted. Atom evaluators return only surviving envs.
- `src/kernel/core/rules/ruleref_substrate.py`: `NativeWhereEvaluation` has only `bindings`, `rule_refs`, and `rule_ref_resolutions`.
- `src/kernel/core/store/_evaluate.py`: native support artifacts are built only for successful `evaluation.bindings`.
- `src/kernel/application/diagnose_runtime.py`: `_localize_failed_atom(...)` replays one requested binding through private atom evaluators and picks a single best failed atom.
- `src/kernel/adapters/souffle/engine_eval.py`: query facts and witness rows are read from output files; witness rows require a satisfying branch.
- `src/kernel/adapters/problog/engine_eval.py` and `src/kernel/adapters/problog/provenance.py`: ProbLog runs with `trace=True` and stores an adapter-local proof trace on successful candidates.
- `src/kernel/adapters/pyreason/engine_eval.py` and `src/kernel/adapters/pyreason/provenance.py`: PyReason runs with `atom_trace=True` and stores an adapter-local event log on successful candidates.

### 4.4 Step 0.A Preliminary Shape Read

- **E1 native evaluator trace remains the only non-redundant candidate.** It is plausible only as a native return-shape extension or a separate native trace entrypoint. A callback or open-ended `trace=True` kwarg is not acceptable because it creates a hidden second contract and conflicts with the Why-not drift gate that forbids evaluator trace hooks by accident.
- **E2 cross-engine trace is not crisp on current evidence.** Souffle has no failed query rows, ProbLog has adapter-local textual proof events, and PyReason has adapter-local bound-change events. A shared abstraction would either become opaque adapter payloads or immediately require a declarative engine-support/schema round.
- **E3 repeated bounded probe is presumed redundant unless Step 0.B proves new evaluator-layer value.** The shipped Why-not Universe Diagnose already covers explicit finite universe plus bounded per-red-row Diagnose. E3 should not survive merely as a renamed application capability.
- **Valid abandonment remains live.** If Step 0.B cannot name a bounded native frontier DTO that is useful beyond Diagnose's seeded atom localization, implementation should stop here and record the architecture blocker.

## 5. Proposed Shape

This blueprint has no frozen implementation shape yet. Step 0 must decide among at least these possibilities:

### 5.1 Shape E1: Native Evaluator Trace

Expose failed branch / failed atom / partial environment state from the native evaluator only. This may be crisp if the native evaluator already has a natural bounded branch frontier. It may be invalid if it requires a trace callback that changes evaluator control flow or emits unstable internal state.

Step 0.A narrows E1:

- acceptable direction: a typed native return-shape extension or a separate native trace entrypoint;
- warning sign: a callback, free-form trace kwarg, mode flag, or opaque internal env dump;
- open Step 0.B question: whether "frontier" means per-branch aggregate failure, per-partial-env failure, or seeded candidate failure. The seeded candidate variant may collapse into Diagnose unless it provides new evaluator-level value.

Step 0.B selects E1 with a narrower contract:

- **Granularity:** per-branch aggregate frontier rows, not per-partial-env dumps and not seeded candidate failure.
- **Entrypoint:** separate native trace entrypoint, not an added kwarg on `evaluate_native_where(...)` and not a field that normal callers are expected to consume.
- **Non-redundant value:** the trace summarizes why the unseeded native evaluation produced no rows, or fewer rows than expected, by reporting each branch's furthest satisfied atom and frontier count. Diagnose answers "why did this requested binding fail?" E1 answers "where did this rule body frontier collapse during native evaluation?"
- **Boundedness:** rows are bounded by OR branches and atom positions. Step 0.C must decide whether any per-row sample is allowed; if allowed, it must be a fixed small representative sample, not `search_budget`.

### 5.2 Shape E2: Cross-engine Trace Abstraction

Define a common trace abstraction across native, Souffle, ProbLog, and PyReason. This is higher signal but much riskier: if each adapter has materially different failure semantics, the abstraction may become a lossy `Any` payload or a premature §6.7 trigger.

Step 0.A marks E2 as currently not crisp. Existing adapter traces are success/provenance carriers, not shared failed-candidate contracts.

Step 0.B rejects E2 for this blueprint. ProbLog adapter-specific failure parsing may become a separate adapter-specific blueprint later, but it is not a cross-engine evaluator trace contract today.

### 5.3 Shape E3: Repeated Bounded Probe

Avoid evaluator traces by enumerating explicit candidates and running bounded probes. This is likely already covered by Why-not Universe Diagnose plus Diagnose. Step 0 should only keep this shape if it adds real evaluator-level value without reintroducing `search_budget`.

Step 0.A adds a redundancy exit: if E3 cannot name genuine new value over shipped Why-not Universe Diagnose, Step 0.B should classify it as abandonment / supersession rather than scope a duplicate capability.

Step 0.B rejects E3 as redundant. Any explicit-universe repeated probe belongs to shipped Why-not Universe Diagnose unless a future performance blueprint proves a batching optimization without changing semantics.

### 5.4 Valid Abandonment

If all useful shapes require open-ended search, unstable internal evaluator state, adapter-specific opaque payloads, or application-layer coupling, the correct output is an abandonment note, not implementation.

Step 0.B does not abandon. E1 is crisp enough to proceed to Step 0.C because the selected contract is native-only, branch/atom bounded, and separated from the existing evaluation entrypoint.

### 5.5 Step 0.B Crispness Decision

Decision: **continue with E1 native aggregate frontier trace**.

Rejected E1 variants:

| Variant | Decision | Reason |
|---|---|---|
| Per-partial-env dump | reject | Captures unstable internal dictionaries and can explode with join cardinality |
| Seeded candidate failure | reject as primary shape | Collapses into Diagnose unless a later runtime needs a lower-level helper |
| Callback / trace kwarg | reject | Hides a second contract behind normal evaluation and conflicts with drift gates |
| `NativeWhereEvaluation` field consumed by normal callers | reject | Invites accidental dependency from shipped application capabilities |

Pre-freeze E1 sketch carried into Step 0.C:

```text
evaluate_native_where_frontier(view_facts, where, *, registry=None, witness_facts=None)
  -> NativeWhereFrontierEvaluation

NativeWhereFrontierEvaluation(
  bindings,
  rule_refs,
  rule_ref_resolutions,
  frontier_rows,
)

NativeWhereFrontierRow(
  branch_index,
  failed_atom_index,
  atoms_satisfied,
  frontier_count,
  failure_kind,
  sample_binding,
)
```

Names and exact fields are provisional until Step 0.C. What is frozen by Step 0.B is the altitude: native-only, aggregate, typed, separate entrypoint, no application protocol dependency, no callback, no open-ended search budget.

Step 0.C supersedes this sketch in §5.6. In particular, `sample_binding` is rejected in the frozen row DTO.

### 5.6 Step 0.C Contract Freeze

Step 0.C freezes the evaluator trace contract enough to authorize a later scoped implementation.

#### 5.6.1 Entrypoint

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

The signature mirrors `evaluate_native_where(...)` except for the function name and return type. It does not add `trace`, `callback`, `mode`, `options`, `search_budget`, or `sample_limit` kwargs.

#### 5.6.2 Result DTO

```text
NativeWhereFrontierEvaluation(
  bindings: list[dict[str, Any]],
  rule_refs: tuple[str, ...] = (),
  rule_ref_resolutions: tuple[NativeRuleRefResolution, ...] = (),
  frontier_rows: tuple[NativeWhereFrontierRow, ...] = (),
)
```

`bindings`, `rule_refs`, and `rule_ref_resolutions` keep the same semantics as `NativeWhereEvaluation`. Existing callers do not receive this DTO unless they explicitly call the new entrypoint.

#### 5.6.3 Frontier Row DTO

```text
NativeWhereFrontierRow(
  branch_index: int,
  failed_atom_index: int,
  atoms_satisfied: int,
  frontier_count: int,
  failure_kind: Literal["empty_input", "atom_filter_empty"],
)
```

Field semantics:

| Field | Meaning |
|---|---|
| `branch_index` | Normalized OR branch index; one-level AND bodies use branch `0` |
| `failed_atom_index` | Atom index where the branch first produced no surviving environments |
| `atoms_satisfied` | Number of atoms satisfied before `failed_atom_index`; frozen equal to `failed_atom_index` |
| `frontier_count` | Number of environments entering the failed atom |
| `failure_kind` | `empty_input` is reserved for defensive completeness if a helper starts a branch with no envs; `atom_filter_empty` when a concrete atom filters all frontier envs |

`sample_binding` is intentionally excluded. Including a sample would make internal env dictionaries part of the evaluator contract and would pull this design back toward rejected per-partial-env dumps. A later debug-only helper may expose samples outside the stable contract, but this blueprint must not.

#### 5.6.4 Algorithm Freeze

For each normalized branch:

1. Start with `envs = [{}]`.
2. For each planned atom at `atom_index`, record `frontier_count = len(envs)` before evaluating the atom.
3. Evaluate the atom with the same atom evaluator semantics as normal `evaluate_where(...)`.
4. If no env survives, emit one `NativeWhereFrontierRow` for that branch and stop evaluating that branch.
5. If the branch completes, emit no frontier row and append surviving envs to `bindings`.
6. Dedupe and sort `bindings` exactly as normal `evaluate_where(...)` does.

Normal successful branches have no frontier row. A body with multiple OR branches can return both successful bindings and frontier rows for failed branches.

#### 5.6.5 RuleRef Freeze

RuleRef rewriting remains success-side and mirrors `evaluate_native_where(...)` preflight and overlay behavior. Frontier rows are computed against the rewritten native body after RuleRef resolution. The frontier contract does not expose failed child-rule internals or rejected RuleRef rows.

If RuleRef resolution itself fails, the entrypoint raises the same `WhereValidationError` shape as `evaluate_native_where(...)`.

#### 5.6.6 Engine Gate

This is **native-only** evaluator architecture. Souffle, ProbLog, and PyReason are explicitly out of scope for this blueprint. No cross-engine support matrix or §6.7 declaration is opened by Step 0.C.

#### 5.6.7 Drift Gates

- [ ] **§7-EvaluatorFrontier-1** separate entrypoint: `evaluate_native_where(...)` signature and `NativeWhereEvaluation` fields remain unchanged.
- [ ] **§7-EvaluatorFrontier-2** no trace kwargs: no `trace`, `callback`, `near_miss`, `failed_frontier`, `exclusion_reason`, `mode`, `options`, `search_budget`, or `sample_limit` parameter is added to normal evaluation.
- [ ] **§7-EvaluatorFrontier-3** layer separation: core rules frontier DTOs do not import application, SDK, adapter, evidence payload, or candidate DTOs.
- [ ] **§7-EvaluatorFrontier-4** bounded rows: at most one frontier row is emitted per normalized OR branch.
- [ ] **§7-EvaluatorFrontier-5** no env dump: frontier rows do not expose env dictionaries, candidate payloads, support artifacts, provenance envelopes, or arbitrary `details`.
- [ ] **§7-EvaluatorFrontier-6** deterministic counts: `atoms_satisfied == failed_atom_index`, and `frontier_count` is the pre-atom input env count.
- [ ] **§7-EvaluatorFrontier-7** success parity: calling the frontier entrypoint returns the same `bindings`, `rule_refs`, and `rule_ref_resolutions` as `evaluate_native_where(...)` for the same inputs.
- [ ] **§7-EvaluatorFrontier-8** native-only scope: no Souffle / ProbLog / PyReason adapter API or engine evaluator contract changes land in this blueprint.
- [ ] **§7-EvaluatorFrontier-9** no persistence: frontier evaluation does not append, accept, write ledger state, or persist trace artifacts beyond existing success-side support artifact behavior.
- [ ] **§7-EvaluatorFrontier-10** no application back-dependency: shipped application capabilities may call the new entrypoint only in a later scoped blueprint; Step implementation must not modify Check, Diagnose, Fact Overlay, or Why-not behavior by accident.

## 6. Boundaries And Invariants

- Evaluator architecture sits below application capabilities; it must not import application protocol DTOs or depend on application runtime behavior.
- A trace contract must be bounded by rule/plan structure, explicit candidates, or a finite evaluator frontier. It must not rely on `search_budget` as the primary semantic boundary.
- A result DTO must have enumerable statuses and typed payloads. Opaque `Any` payloads or adapter-specific escape hatches are a failure signal.
- Existing shipped capabilities must continue to work without adopting trace mode.
- If cross-engine support cannot be described locally and tested without schema drift, Step 0 must record whether §6.7 is the real next blueprint.
- Release base and `master` remain untouched.

## 7. Acceptance

- [x] Step 0.A source pass cites the native evaluator and each current adapter surface.
- [x] Step 0.B records a DTO crispness decision for E1 / E2 / E3 / abandon.
- [x] If crisp, Step 0.C freezes the evaluator boundary, status vocabulary, payload shape, and drift gates before implementation.
- [ ] If not crisp, Step 0.C records the exact blocker and why implementation is abandoned or superseded.
- [ ] Step 0.D either moves this blueprint to `scoped` for a bounded implementation or closes it as abandoned / superseded.
- [ ] No code, adapter, runtime, or module docs change is made while the blueprint remains `draft`.

## 8. Implementation Plan

1. Step 0.A Source pass:
   - Read native where evaluation internals and return shapes.
   - Read Souffle, ProbLog, and PyReason adapter candidate/evidence surfaces.
   - Re-read Why-not Step 0 fork notes and relevant L6 / near-miss reference passages.
2. Step 0.B Shape split and crispness decision:
   - Compare E1 native trace, E2 cross-engine trace, E3 repeated probe, and abandonment.
   - Apply explicit DTO crispness criteria: enumerable fields, enumerable statuses, boundedness, no escape hatches, no application coupling.
3. Step 0.C Boundary freeze or blocker:
   - If a shape is crisp, freeze request/result DTOs, evaluator hook boundary, engine support gate, and drift gates.
   - If no shape is crisp, record the precise blocker and stop.
4. Step 0.D Lift / abandon / supersede:
   - Move to `scoped` only if implementation is bounded.
   - Otherwise close as valid abandonment or supersede with a more accurate architecture blueprint.

## 9. Docs To Update

Step 0 is docs-only. No module docs are updated unless the blueprint moves to `scoped` and implementation changes current behavior.

Potential later docs if implementation is scoped:

- `src/kernel/core/rules/docs/` if evaluator behavior changes.
- `src/kernel/adapters/*/docs/` if adapter contracts change.
- `docs/architecture_principles.md` if a durable evaluator trace boundary is established.

## 10. Outcome / Deviations

Task completion will fill:

- Final Step 0 result:
- Selected shape or abandonment blocker:
- Deviations from initial assumptions:
- Archive / supersession notes:
