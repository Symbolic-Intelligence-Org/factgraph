# Task Blueprint: Evaluator Frontier Trace Capability

- Status: implemented
- Created: 2026-05-05
- Last Updated: 2026-05-05
- Related Modules:
  - `src/kernel/core/rules/`
  - `src/kernel/core/store/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/references/working/rule-replay-line-redesign-input/20_capability-layering-l0-l11.md](../../references/working/rule-replay-line-redesign-input/20_capability-layering-l0-l11.md)
  - [docs/references/working/rule-replay-line-redesign-input/40_design-discussion-A-with-decision-1.md](../../references/working/rule-replay-line-redesign-input/40_design-discussion-A-with-decision-1.md)
  - [docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md](../../references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md)
  - [docs/blueprints/archive/2026-05-05_why-not-universe-diagnose-capability.md](./2026-05-05_why-not-universe-diagnose-capability.md)
- Audit Log:
  - [2026-05-05_evaluator-frontier-trace-capability.audit.md](./2026-05-05_evaluator-frontier-trace-capability.audit.md)

## 1. Problem

Why-not Universe Diagnose shipped a bounded application-layer Why-not by requiring an explicit finite candidate universe and mapping red rows through Diagnose. That intentionally left true evaluator near-miss / failed-frontier tracing outside application capability scope.

Step 0 found one crisp lower-layer continuation: a native-only evaluator frontier trace. The native evaluator already walks branch envs atom by atom, but it discards failed-frontier state as control flow. This blueprint scopes a typed, aggregate, separate native entrypoint that reports where each failed native branch collapsed without exposing env dumps, adapter payloads, callbacks, or application DTOs.

## 2. Goals

- Add a native evaluator frontier trace entrypoint below application capabilities.
- Preserve the existing `evaluate_native_where(...)` signature and `NativeWhereEvaluation` contract.
- Return success bindings plus typed aggregate frontier rows through a separate DTO.
- Keep the trace bounded by native OR branches and atom positions.
- Lock drift gates that prevent trace kwargs, env dumps, cross-engine leakage, application back-dependencies, and persistence side effects.

## 3. Non-goals

- No changes to Check, Diagnose, Fact Overlay, or Why-not behavior in this blueprint.
- No application protocol DTOs, SDK shell, UI, or public application capability.
- No Souffle, ProbLog, or PyReason adapter trace support.
- No cross-engine capability declaration or §6.7 schema.
- No callback, `trace` kwarg, `mode`, `options`, `search_budget`, `sample_limit`, or opaque `details`.
- No candidate universe, repeated probe, ledger write, carrier persistence, or debug env dump.
- No changes to `v0.1-oss-prep` or `master`.

## 4. Current Context

Step 0.A source pass found:

- `src/kernel/core/rules/where_eval.py` keeps rejected envs only as transient control flow. `_eval_body(...)` starts from `envs = [{}]`, applies atom evaluators, replaces `envs` with survivors, and returns `[]` when a branch collapses.
- `src/kernel/core/rules/ruleref_substrate.py` exposes `NativeWhereEvaluation(bindings, rule_refs, rule_ref_resolutions)` only.
- Native store support artifacts are built only for successful bindings.
- Diagnose native localization is seeded by one requested binding. It does not discover evaluator-global branch frontiers.
- Souffle emits success query rows / witness rows only.
- ProbLog and PyReason have adapter-local success/provenance traces, not a shared failed-candidate contract.

Step 0.B selected native-only per-branch aggregate frontier rows. Step 0.C froze the DTO and drift gates below.

## 5. Proposed Shape

### 5.1 Entrypoint

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

### 5.2 Result DTO

```text
NativeWhereFrontierEvaluation(
  bindings: list[dict[str, Any]],
  rule_refs: tuple[str, ...] = (),
  rule_ref_resolutions: tuple[NativeRuleRefResolution, ...] = (),
  frontier_rows: tuple[NativeWhereFrontierRow, ...] = (),
)
```

`bindings`, `rule_refs`, and `rule_ref_resolutions` keep the same semantics as `NativeWhereEvaluation`. Existing callers do not receive this DTO unless they explicitly call the new entrypoint.

### 5.3 Frontier Row DTO

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

No `sample_binding` field is allowed. A sample would stabilize internal env dictionaries as contract and reopen the rejected per-partial-env dump path.

### 5.4 Algorithm

For each normalized branch:

1. Start with `envs = [{}]`.
2. For each planned atom at `atom_index`, record `frontier_count = len(envs)` before evaluating the atom.
3. Evaluate the atom with the same atom evaluator semantics as normal `evaluate_where(...)`.
4. If no env survives, emit one `NativeWhereFrontierRow` for that branch and stop evaluating that branch.
5. If the branch completes, emit no frontier row and append surviving envs to `bindings`.
6. Dedupe and sort `bindings` exactly as normal `evaluate_where(...)` does.

Normal successful branches have no frontier row. A body with multiple OR branches can return both successful bindings and frontier rows for failed branches.

### 5.5 RuleRef Boundary

RuleRef behavior mirrors `evaluate_native_where(...)`: preflight, rewrite, overlay, and success-side support resolution remain unchanged. Frontier rows are computed after RuleRef rewrite against the resolved native body.

The contract does not expose failed child-rule internals or rejected RuleRef rows. If nested RuleRef failed-frontier explanation is needed later, it must be a separate expansion.

### 5.6 Engine Gate

This is native-only evaluator architecture. Souffle, ProbLog, and PyReason are out of scope. This blueprint does not open §6.7.

## 6. Boundaries And Invariants

- Evaluator architecture sits below application capabilities; it must not import application protocol DTOs or depend on application runtime behavior.
- Frontier DTOs live in core rules and must not import SDK, adapter, candidate, evidence payload, or application modules.
- The existing `evaluate_native_where(...)` call surface remains unchanged.
- The trace contract is aggregate-only. It exposes counts and locators, not env dictionaries or arbitrary payloads.
- Existing shipped capabilities keep their current behavior unless a later scoped blueprint explicitly opts them into frontier tracing.
- Release base and `master` remain untouched.

## 7. Acceptance

- [x] **§7-EvaluatorFrontier-1** separate entrypoint: `evaluate_native_where(...)` signature and `NativeWhereEvaluation` fields remain unchanged.
- [x] **§7-EvaluatorFrontier-2** no trace kwargs: no `trace`, `callback`, `near_miss`, `failed_frontier`, `exclusion_reason`, `mode`, `options`, `search_budget`, or `sample_limit` parameter is added to normal evaluation.
- [x] **§7-EvaluatorFrontier-3** layer separation: core rules frontier DTOs do not import application, SDK, adapter, evidence payload, or candidate DTOs.
- [x] **§7-EvaluatorFrontier-4** bounded rows: at most one frontier row is emitted per normalized OR branch.
- [x] **§7-EvaluatorFrontier-5** no env dump: frontier rows do not expose env dictionaries, candidate payloads, support artifacts, provenance envelopes, or arbitrary `details`.
- [x] **§7-EvaluatorFrontier-6** deterministic counts: `atoms_satisfied == failed_atom_index`, and `frontier_count` is the pre-atom input env count.
- [x] **§7-EvaluatorFrontier-7** success parity: calling the frontier entrypoint returns the same `bindings`, `rule_refs`, and `rule_ref_resolutions` as `evaluate_native_where(...)` for the same inputs.
- [x] **§7-EvaluatorFrontier-8** native-only scope: no Souffle / ProbLog / PyReason adapter API or engine evaluator contract changes land in this blueprint.
- [x] **§7-EvaluatorFrontier-9** no persistence: frontier evaluation does not append, accept, write ledger state, or persist trace artifacts beyond existing success-side support artifact behavior.
- [x] **§7-EvaluatorFrontier-10** no application back-dependency: implementation does not modify Check, Diagnose, Fact Overlay, or Why-not behavior.
- [x] Core rules docs are updated if the new entrypoint ships.
- [x] Blueprint Outcome / Deviations is completed before archive.

## 8. Implementation Plan

1. **Step 1 — DTO + Entry Scaffold**
   - Add `NativeWhereFrontierEvaluation`, `NativeWhereFrontierRow`, and `evaluate_native_where_frontier(...)` in the core rules native evaluator surface.
   - Keep `evaluate_native_where(...)` unchanged.
   - Add focused tests for DTO shape, signature boundaries, and import/layer separation.
2. **Step 2 — Frontier Algorithm**
   - Share native atom-walk semantics with normal `evaluate_where(...)`.
   - Emit sparse per-branch frontier rows only for failed branches.
   - Prove success parity with `evaluate_native_where(...)` across AND, OR, predicate, filter, arithmetic, `not`, and RuleRef paths.
3. **Step 3 — Drift Gates**
   - Add named anti-regression tests for §7-EvaluatorFrontier-1 through §7-EvaluatorFrontier-10.
   - Include AST checks for banned kwargs/imports and runtime checks for no persistence or application behavior changes.
4. **Step 4 — Close-out + Archive**
   - Update affected core rules docs.
   - Fill §10 Outcome / Deviations.
   - Archive blueprint and audit.

## 9. Docs To Update

- `src/kernel/core/docs/01_architecture.md`
- `src/kernel/core/docs/01_architecture.en.md`
- `docs/blueprints/archive/README.md` when archived

## 10. Outcome / Deviations

Final landed behavior:

- `src/kernel/core/rules/frontier.py` now exposes `NativeWhereFrontierEvaluation`, `NativeWhereFrontierRow`, and `evaluate_native_where_frontier(...)`.
- The frontier entrypoint mirrors `evaluate_native_where(...)`, keeps `bindings` / `rule_refs` / `rule_ref_resolutions` success parity, and returns sparse aggregate `frontier_rows`.
- Failed normalized OR branches emit at most one row with `branch_index`, `failed_atom_index`, `atoms_satisfied`, `frontier_count`, and `failure_kind`.
- RuleRef behavior mirrors native substrate preflight/rewrite/overlay; frontier is computed on the rewritten parent native body, without exposing child-rule failed internals.
- `evaluate_native_where(...)`, shipped application capabilities, adapters, and engine evaluator contracts are unchanged.

Verification:

- `python -m unittest src.kernel.tests.test_core_rules_frontier src.kernel.tests.test_core_rules_frontier_drift_gates` — 36 tests passed.
- `python -m unittest discover -s src/kernel/tests -p 'test_*.py'` — 1079 tests passed, 1 skipped.
- `python -m ruff check src/kernel` — clean.
- `git diff --check` — clean.

Implementation chain:

- `52e84d1 feat(rules): scaffold evaluator frontier trace`
- `3440d54 feat(rules): add evaluator frontier algorithm`
- `d8b51f8 test(rules): add evaluator frontier drift gates`
- Step 4 close-out updates docs and archives this blueprint.

Deviations from scoped contract:

- The final algorithm uses an isolated frontier walker in `kernel.core.rules.frontier` that reuses `where_eval` private atom evaluators, rather than adding a collector parameter to `where_eval._eval_body(...)`.
- Rationale: keeping DTO ownership in `frontier.py` avoids a `where_eval -> frontier` dependency cycle and preserves the normal evaluator surface with zero behavior change for existing callers.
- Tradeoff: the branch walker is parallel implementation code. This is mitigated by success-parity tests across AND, OR, predicate, filter, arithmetic, `not`, and RuleRef paths, plus named §7 drift gates.

Archive notes:

- This shipped as native-only evaluator substrate, not an application capability.
- It resolves the Why-not Shape B fork as a lower-layer frontier trace primitive without opening cross-engine §6.7 schema work.
- Future application consumers must open a new scoped blueprint before importing or depending on `evaluate_native_where_frontier(...)`.
