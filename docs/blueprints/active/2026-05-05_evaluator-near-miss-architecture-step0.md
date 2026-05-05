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

## 5. Proposed Shape

This blueprint has no frozen implementation shape yet. Step 0 must decide among at least these possibilities:

### 5.1 Shape E1: Native Evaluator Trace

Expose failed branch / failed atom / partial environment state from the native evaluator only. This may be crisp if the native evaluator already has a natural bounded branch frontier. It may be invalid if it requires a trace callback that changes evaluator control flow or emits unstable internal state.

### 5.2 Shape E2: Cross-engine Trace Abstraction

Define a common trace abstraction across native, Souffle, ProbLog, and PyReason. This is higher signal but much riskier: if each adapter has materially different failure semantics, the abstraction may become a lossy `Any` payload or a premature §6.7 trigger.

### 5.3 Shape E3: Repeated Bounded Probe

Avoid evaluator traces by enumerating explicit candidates and running bounded probes. This is likely already covered by Why-not Universe Diagnose plus Diagnose. Step 0 should only keep this shape if it adds real evaluator-level value without reintroducing `search_budget`.

### 5.4 Valid Abandonment

If all useful shapes require open-ended search, unstable internal evaluator state, adapter-specific opaque payloads, or application-layer coupling, the correct output is an abandonment note, not implementation.

## 6. Boundaries And Invariants

- Evaluator architecture sits below application capabilities; it must not import application protocol DTOs or depend on application runtime behavior.
- A trace contract must be bounded by rule/plan structure, explicit candidates, or a finite evaluator frontier. It must not rely on `search_budget` as the primary semantic boundary.
- A result DTO must have enumerable statuses and typed payloads. Opaque `Any` payloads or adapter-specific escape hatches are a failure signal.
- Existing shipped capabilities must continue to work without adopting trace mode.
- If cross-engine support cannot be described locally and tested without schema drift, Step 0 must record whether §6.7 is the real next blueprint.
- Release base and `master` remain untouched.

## 7. Acceptance

- [ ] Step 0.A source pass cites the native evaluator and each current adapter surface.
- [ ] Step 0.B records a DTO crispness decision for E1 / E2 / E3 / abandon.
- [ ] If crisp, Step 0.C freezes the evaluator boundary, status vocabulary, payload shape, and drift gates before implementation.
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
