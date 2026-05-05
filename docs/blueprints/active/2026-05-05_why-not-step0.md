# Task Blueprint: Why-not Step 0 Spike

- Status: draft
- Created: 2026-05-05
- Last Updated: 2026-05-05
- Related Modules:
  - `src/kernel/application/protocol/`
  - `src/kernel/application/`
  - `src/kernel/core/rules/`
  - `src/kernel/core/store/`
  - `src/kernel/adapters/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/references/working/rule-replay-line-redesign-input/README.md](../../references/working/rule-replay-line-redesign-input/README.md)
  - [docs/references/working/rule-replay-line-redesign-input/20_capability-layering-l0-l11.md](../../references/working/rule-replay-line-redesign-input/20_capability-layering-l0-l11.md)
  - [docs/references/working/rule-replay-line-redesign-input/40_design-discussion-A-with-decision-1.md](../../references/working/rule-replay-line-redesign-input/40_design-discussion-A-with-decision-1.md)
  - [docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md](../../references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md)
  - [docs/blueprints/archive/2026-05-03_check-operation.md](../archive/2026-05-03_check-operation.md)
  - [docs/blueprints/archive/2026-05-04_diagnose-operation.md](../archive/2026-05-04_diagnose-operation.md)
  - [docs/blueprints/archive/2026-05-04_fact-overlay-capability.md](../archive/2026-05-04_fact-overlay-capability.md)
- Audit Log:
  - [2026-05-05_why-not-step0.audit.md](./2026-05-05_why-not-step0.audit.md)

## 1. Problem

Check, Diagnose, and Fact Overlay have shipped as application-first capabilities. They validate the DTO + runtime pattern and keep engine-extension §6.6's locally hardcoded capability gate working hypothesis standing.

The next high-signal pressure point is Why-not: users eventually want to ask what almost matched, what was excluded, and why. Unlike Check / Diagnose / Fact Overlay, true Why-not appears to require either an explicit candidate universe or evaluator/adapter near-miss traces. This blueprint exists only to run Step 0 and decide whether a crisp application DTO exists. If it does not, the valid output is abandonment or reclassification as evaluator architecture work.

## 2. Goals

- Run a source-backed Step 0 for Why-not before any code implementation.
- Decide whether the capability has a crisp application DTO shape.
- Separate three possible shapes that old references often conflate:
  - lazy candidate-universe red/green carriers;
  - lazy candidate-universe carriers with inline bounded Diagnose;
  - true evaluator near-miss / exclusion-reason Why-not.
- Determine whether Why-not keeps §6.6 local gates readable or triggers §6.7 declarative capability work.
- Record a valid abandonment path if the DTO shape depends on a new evaluator hook.

## 3. Non-goals

- No implementation before Step 0 moves this blueprint to `scoped`.
- No evaluator hook, trace callback, adapter change, carrier persistence, audit package write, SDK shell, UI, or release-base action in this blueprint's current `draft` state.
- No broad Explain renderer.
- No red/green completeness claim without an explicit finite candidate universe.
- No `search_budget` / `limit` field as a substitute for a bounded algorithm.
- No new substrate in `kernel.sdk`.
- No changes to `v0.1-oss-prep` or `master`.

## 4. Current Context

### Shipped capability pattern

The three shipped application capabilities share these properties:

- Request DTOs are intent-only and live under `kernel.application.protocol`.
- Runtime functions take `store` and optional `registry` through side-channel kwargs.
- Status vocabularies and payloads are capability-owned.
- Local engine gates are acceptable when they can be described clearly and tested locally.
- Sibling composition is preferred when delegation would launder another capability's behavior.

### Source-backed Why-not anchors

- L6 is documented as "Lazy why-not / candidate-universe board" and explicitly deferred because it needs a new evaluator hook to capture near-misses.
- B'' material says lazy red traces require an explicit, finite candidate universe aligned with the rule head/select identity.
- Existing `evaluate_native_where(...)` returns `NativeWhereEvaluation(bindings, rule_refs, rule_ref_resolutions)`; it does not expose failed branches, rejected environments, exclusion reasons, or near-miss state.
- Diagnose's native atom localization is a bounded post-failure localizer for one requested binding. It is not a candidate-universe or near-miss trace API.
- Souffle, ProbLog, and PyReason adapters return derived candidates plus success support/provenance. They do not expose failed candidate traces through the current application contract.

## 5. Proposed Shape

This section is intentionally not a frozen contract. Step 0.A found three candidate shapes:

### 5.1 Shape A: Lazy candidate-universe carrier board

Possible request sketch:

`WhyNotUniverseRequest(plan, candidate_universe, engine) -> WhyNotUniverseResult`

The user supplies an explicit finite candidate universe. Runtime evaluates the plan, computes:

```text
green = derived candidates intersect candidate_universe
red = candidate_universe - green
```

The red rows are lazy carriers, not materialized failed evidence. Opening a red carrier later would call an existing bounded capability such as Diagnose or Check for that concrete binding.

This shape is DTO-crisp if `candidate_universe` is an explicit tuple of normalized head bindings. It does not require `search_budget`, and it can be written with current evaluate output. Pure Shape A is lower signal than Shape A-prime because the "why" is deferred to caller-side per-binding calls; Shape A-prime composes Diagnose into the same call to inline bounded diagnostics for red rows.

### 5.2 Shape A-prime: Universe carrier plus inline Diagnose

Possible request sketch:

`WhyNotUniverseDiagnoseRequest(plan, candidate_universe, engine) -> WhyNotUniverseDiagnoseResult`

The caller still supplies an explicit finite candidate universe. Runtime evaluates the plan to compute green bindings, computes red bindings by set difference, then runs `diagnose_derivation_binding(...)` for each red binding and inlines the bounded `DiagnoseResult` on the row.

Possible result sketch:

```text
WhyNotUniverseDiagnoseResult(
    status,
    requested_universe,
    green,
    red,
    errors,
    warnings,
)

WhyNotRedRow(
    binding,
    diagnose,
)
```

This shape is a bounded composition, not evaluator near-miss tracing. It does not need a search budget because the finite universe bounds the outer loop, and Diagnose already bounds each per-binding explanation. It is higher signal than pure Shape A because one call can return both the red carrier and the available row-level diagnostic payload.

The cost is composition discipline. Step 0.B must decide whether inlining `DiagnoseResult` is acceptable Sibling-with-Diagnose composition, or whether it should copy Diagnose's status payload into a Why-not-owned row DTO to avoid nested capability DTO coupling. Either way, this shape does not require a new evaluator hook.

Engine support can inherit Diagnose's current semantics: native red rows may carry atom-localized payloads; non-native red rows may return coarse failed / unsupported classifications according to Diagnose's representability and evidence-lookup rules. That keeps §6.6 local-gate discipline readable unless Step 0.B discovers nested-result coupling creates consumer-discovery pressure.

### 5.3 Shape B: True near-miss / exclusion-reason Why-not

Possible request sketch, not currently crisp:

`WhyNotRequest(plan, binding_or_universe, engine, mode?) -> WhyNotResult`

This asks for structured reasons a candidate or candidate family almost matched but failed. The useful payload would need named exclusion reasons, rejected atom locations, attempted bindings, and possibly branch-level near-miss ranking.

Step 0.A preliminary judgment: this shape is not DTO-crisp against the current runtime surface. It depends on information current evaluators do not return. A correct implementation likely requires a new evaluator trace hook or adapter-specific failed-candidate instrumentation, which makes it evaluator architecture work, not a narrow application capability.

### 5.4 Crispness Gate

Step 0.B must choose one outcome:

| Criterion | Shape A carrier board | Shape A-prime carrier + Diagnose | Shape B near-miss Why-not |
|---|---|---|---|
| Request DTO enumerable without `Any` / `**kwargs` escape | Pass if candidate universe is explicit finite bindings | Pass if candidate universe is explicit finite bindings | Fails unless a concrete bounded algorithm is chosen |
| Result DTO status/payload enumerable | Pass for green/red carrier summary; weak for "why" | Pass if `WhyNotRedRow` either nests `DiagnoseResult` or freezes a Why-not-owned diagnostic row shape | Fails until exclusion payload taxonomy is real |
| Runtime `(request, store) -> result` without new evaluator hook | Pass | Pass: evaluate for green set, run bounded Diagnose for each red binding | Fails on current source surface |
| Engine support gate fits one paragraph/table | Probably pass, but low signal | Probably pass by inheriting Diagnose semantics per red row | Fails; native and non-native require different trace/adapter changes |

Preliminary recommendation: do not scope Shape B implementation from this blueprint unless Step 0.B can prove a bounded no-new-hook algorithm. Step 0.B should choose between pure Shape A, Shape A-prime, abandonment, or supersession. If the desired product is pure Shape A only, this blueprint should be renamed or superseded as a candidate-universe carrier capability rather than called full Why-not.

## 6. Boundaries And Invariants

- **Application-first:** any scoped capability must begin with protocol DTOs and application runtime.
- **No hidden universe:** red/green completeness requires an explicit finite candidate universe in the request or a separate source-backed universe provider.
- **No algorithmic paper-over:** `search_budget`, `limit`, or `max_candidates` cannot make an unbounded search crisp unless Step 0 defines the natural bounded search space.
- **No evaluator architecture by accident:** if near-miss reasons require modifying `evaluate_native_where(...)`, `where_eval`, or adapters to expose failed traces, this blueprint must stop before implementation and open a different architecture-facing task.
- **Capability gates stay local only while readable:** if Why-not requires a cross-engine support matrix with adapter-internal details, engine-extension §6.7 is triggered.
- **No SDK substrate:** SDK may only become a future thin shell after an application runtime exists.

## 7. Acceptance

### 7.1 Step 0 closure

- [x] Step 0.A source pass records the current evaluator / adapter surface.
- [ ] Step 0.B decides whether the DTO is crisp, not crisp, or crisp only after reframing to carrier board / carrier plus Diagnose.
- [ ] Step 0.C freezes either a scoped algorithm and drift gates, or records why no algorithm can be frozen.
- [ ] Step 0.D either moves the blueprint to `scoped` for implementation, marks it `abandoned`, or supersedes it with a more accurately named blueprint.

### 7.2 Scope guard

- [ ] No code implementation starts while status remains `draft`.
- [ ] Any move to `scoped` contains an exact request DTO field list and exact result DTO field list.
- [ ] Any move to `scoped` explains engine support in a short local paragraph/table.
- [ ] Any abandonment records whether the blocker is candidate-universe absence, result payload taxonomy, evaluator hook requirement, or engine support unreadability.

## 8. Implementation Plan

This blueprint currently authorizes Step 0 only.

1. **Step 0.A — Source pass + shape split** (drafted): read shipped capability archives, L6 / lazy why-not references, current native evaluator surface, current adapter output surfaces, and engine-extension §6.6. Record whether the old "Why-not" label hides multiple shapes.
2. **Step 0.B — DTO crispness decision:** choose one of Shape A carrier board, Shape A-prime carrier plus Diagnose, Shape B near-miss Why-not, abandonment, or supersession.
3. **Step 0.C — Algorithm / gate freeze or blocker:** if Step 0.B chooses a scoped shape, freeze algorithm, status matrix, payload taxonomy, and engine support gate. If not, record the blocker precisely.
4. **Step 0.D — Lift / abandon / supersede:** update §5 / §7 / §8, then move status according to the Step 0 decision.

## 9. Docs To Update

- No module docs update is required while this blueprint remains Step 0 draft only.
- If Step 0 scopes implementation, update affected module docs under `src/kernel/application/docs/` after implementation.
- If Step 0 triggers evaluator architecture work, update or create the relevant architecture-facing blueprint before code edits.

## 10. Outcome / Deviations

Task completion pending.

- Final Step 0 result:
- Deviations:
- Archive / abandonment / supersession notes:
