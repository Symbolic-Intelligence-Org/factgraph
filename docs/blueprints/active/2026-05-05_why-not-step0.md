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

Step 0.A found three candidate shapes. Step 0.B chooses Shape A-prime as the crisp application-capability shape and rejects Shape B for this blueprint.

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

`WhyNotUniverseRequest(plan, candidate_universe, engine) -> WhyNotUniverseResult`

The caller still supplies an explicit finite candidate universe. Runtime evaluates the plan to compute green bindings, computes red bindings by set difference, then runs `diagnose_derivation_binding(...)` for each red binding and inlines the bounded `DiagnoseResult` on the row.

Possible result sketch:

```text
WhyNotUniverseResult(
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

The cost is composition discipline. Step 0.B decided to copy Diagnose's status payload into a Why-not-owned row DTO rather than inline `DiagnoseResult`. This avoids nested capability DTO coupling while keeping the bounded runtime composition. This shape does not require a new evaluator hook.

Engine support can inherit Diagnose's current semantics: native red rows may carry atom-localized payloads; non-native red rows may return coarse failed / unsupported classifications according to Diagnose's representability and evidence-lookup rules. That keeps §6.6 local-gate discipline readable unless Step 0.B discovers nested-result coupling creates consumer-discovery pressure.

### 5.3 Shape B: True near-miss / exclusion-reason Why-not

Possible request sketch, not currently crisp:

`WhyNotRequest(plan, binding_or_universe, engine, mode?) -> WhyNotResult`

This asks for structured reasons a candidate or candidate family almost matched but failed. The useful payload would need named exclusion reasons, rejected atom locations, attempted bindings, and possibly branch-level near-miss ranking.

Step 0.A preliminary judgment: this shape is not DTO-crisp against the current runtime surface. It depends on information current evaluators do not return. A correct implementation likely requires a new evaluator trace hook or adapter-specific failed-candidate instrumentation, which makes it evaluator architecture work, not a narrow application capability.

### 5.4 Crispness Gate

Step 0.B evaluated these outcomes:

| Criterion | Shape A carrier board | Shape A-prime carrier + Diagnose | Shape B near-miss Why-not |
|---|---|---|---|
| Request DTO enumerable without `Any` / `**kwargs` escape | Pass if candidate universe is explicit finite bindings | Pass if candidate universe is explicit finite bindings | Fails unless a concrete bounded algorithm is chosen |
| Result DTO status/payload enumerable | Pass for green/red carrier summary; weak for "why" | Pass if `WhyNotRedRow` either nests `DiagnoseResult` or freezes a Why-not-owned diagnostic row shape | Fails until exclusion payload taxonomy is real |
| Runtime `(request, store) -> result` without new evaluator hook | Pass | Pass: evaluate for green set, run bounded Diagnose for each red binding | Fails on current source surface |
| Engine support gate fits one paragraph/table | Probably pass, but low signal | Probably pass by inheriting Diagnose semantics per red row | Fails; native and non-native require different trace/adapter changes |

Decision: choose Shape A-prime. Do not scope Shape B implementation from this blueprint because Step 0.B did not find a bounded no-new-hook algorithm for evaluator near-miss / exclusion reasons. Pure Shape A remains a lower-signal fallback, not the selected shape.

### 5.5 Step 0.B Frozen Capability Shape

The selected capability is **Why-not Universe Diagnose**:

`WhyNotUniverseRequest(plan, candidate_universe, engine) -> WhyNotUniverseResult`

It answers: "For this explicit finite universe of possible head bindings, which bindings are derived, which are not, and what bounded Diagnose result is available for each red binding?"

This is intentionally not full evaluator near-miss Why-not. It is a bounded red/green universe board with row-level diagnostics.

### 5.6 Request DTO

Frozen request fields:

| Field | Meaning |
|---|---|
| `plan: CompiledDerivationPlan` | Single derivation plan; exactly one head |
| `candidate_universe: tuple[BindingItems, ...]` | Explicit finite universe of complete head bindings |
| `engine: Literal["native", "souffle", "problog", "pyreason"]` | Required engine; no default |

Request invariants:

- `candidate_universe` is a tuple of normalized `BindingItems`.
- Each universe binding must use exactly the plan head variable names. Body-only variables are invalid in the universe.
- Duplicate universe bindings are invalid; the board is set-like.
- Empty universe is allowed and returns a completed empty board.
- No `store`, `registry`, `search_budget`, `limit`, `mode`, `diagnostic_mode`, `engine_options`, `run_id`, query handle, precomputed candidates, or precomputed green set appears on the request DTO.
- Runtime dependencies remain side-channel kwargs: `check_why_not_universe(request, *, store, registry=None)`.

### 5.7 Result DTO

Frozen result fields:

| Field | Meaning |
|---|---|
| `status: Literal["completed", "unsupported", "invalid_request"]` | Batch-level status |
| `requested_universe: tuple[BindingItems, ...]` | Normalized universe echo |
| `green: tuple[BindingItems, ...]` | Universe bindings derived by evaluate |
| `red: tuple[WhyNotRedRow, ...]` | Universe bindings not derived, with row-level diagnostic summaries |
| `errors: tuple[ErrorDTO, ...]` | Batch-level errors |
| `warnings: tuple[WarningDTO, ...]` | Batch-level warnings |

Top-level nullable / population matrix:

| status | green | red | errors |
|---|---|---|---|
| `completed` | populated or empty | populated or empty | empty |
| `unsupported` | empty | empty | required |
| `invalid_request` | empty | empty | required |

Row-level unsupported or invalid diagnostics do not make the top-level result `unsupported` / `invalid_request`; they live on the corresponding red row. Top-level non-completed statuses are reserved for request-wide failures before the board can be assembled.

### 5.8 Red Row DTO

Frozen row shape:

| Field | Meaning |
|---|---|
| `binding: BindingItems` | Red universe binding |
| `diagnostic: WhyNotRowDiagnostic` | Why-not-owned copy of the bounded Diagnose outcome for this binding |

`WhyNotRowDiagnostic` is a capability-owned DTO. It copies Diagnose's stable row semantics but does **not** nest `DiagnoseResult`.

| Field | Meaning |
|---|---|
| `status: Literal["passed", "failed", "unsupported", "invalid_request"]` | Per-row diagnostic status copied from Diagnose vocabulary |
| `matched_count: int | None` | Diagnose-compatible matched count |
| `matched_binding: BindingItems | None` | Diagnose-compatible matched binding |
| `failure_kind: Literal["no_candidate", "atom_localized"] | None` | Diagnose-compatible failure kind |
| `diagnostic_payload: WhyNotAtomLocator | None` | Why-not-owned locator copy for native atom-localized rows |
| `errors: tuple[ErrorDTO, ...]` | Per-row diagnostic errors |
| `warnings: tuple[WarningDTO, ...]` | Per-row diagnostic warnings |

`WhyNotAtomLocator(branch_index, failed_atom_index, attempted_binding)` copies `DiagnoseAtomLocator` semantics into the Why-not protocol. This keeps the result contract capability-owned while allowing runtime implementation to call Diagnose and map its result.

### 5.9 Runtime Composition

Chosen composition: **Sibling-with-Diagnose mapping**.

Why-not may call `diagnose_derivation_binding(...)` for each red binding, because Shape A-prime's value is precisely bounded row-level diagnosis. However, the Why-not protocol must not expose nested `DiagnoseResult`. The runtime maps `DiagnoseResult` into `WhyNotRowDiagnostic` and maps `DiagnoseAtomLocator` into `WhyNotAtomLocator`.

Why-not does not call Check. It does not import Check runtime or Check protocol DTOs. It does not add a new evaluator hook.

### 5.10 Engine Support Gate

The selected shape keeps §6.6 local-gate discipline:

- The green/red board can be computed for engines that can evaluate the plan and expose candidate bindings compatible with the explicit universe.
- Red-row diagnostics inherit Diagnose semantics through mapping:
  - native can return `failed.atom_localized`;
  - souffle / problog / pyreason can return coarse `failed.no_candidate`, `unsupported`, or `invalid_request` according to Diagnose's current representability and evidence lookup rules.
- A row-level `unsupported` result does not invalidate the whole board.
- If a plan / engine pair cannot produce comparable candidate bindings for the supplied universe, the top-level result is `unsupported` with a batch-level error.

This remains short enough to describe locally. §6.7 is not opened by Step 0.B.

## 6. Boundaries And Invariants

- **Application-first:** any scoped capability must begin with protocol DTOs and application runtime.
- **No hidden universe:** red/green completeness requires an explicit finite candidate universe in the request or a separate source-backed universe provider.
- **No algorithmic paper-over:** `search_budget`, `limit`, or `max_candidates` cannot make an unbounded search crisp unless Step 0 defines the natural bounded search space.
- **No evaluator architecture by accident:** if near-miss reasons require modifying `evaluate_native_where(...)`, `where_eval`, or adapters to expose failed traces, this blueprint must stop before implementation and open a different architecture-facing task.
- **Capability gates stay local only while readable:** if Why-not requires a cross-engine support matrix with adapter-internal details, engine-extension §6.7 is triggered.
- **Capability-owned protocol:** Why-not may use Diagnose at runtime, but it must expose Why-not-owned result and locator DTOs rather than nested `DiagnoseResult`.
- **No SDK substrate:** SDK may only become a future thin shell after an application runtime exists.

## 7. Acceptance

### 7.1 Step 0 closure

- [x] Step 0.A source pass records the current evaluator / adapter surface.
- [x] Step 0.B decides whether the DTO is crisp, not crisp, or crisp only after reframing to carrier board / carrier plus Diagnose.
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
2. **Step 0.B — DTO crispness decision** (complete): choose Shape A-prime as Why-not Universe Diagnose; freeze request/result/red-row DTO shape; reject nested `DiagnoseResult` in favor of Why-not-owned row DTOs; leave Shape B as evaluator-architecture work.
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
