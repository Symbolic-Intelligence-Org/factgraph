# L Direction G4 — Why-not + Frontier SDK Shell

- **Status:** draft
- **Created:** 2026-05-08
- **Last Updated:** 2026-05-08
- **Parent:** L Direction (post-A+B+G1 v1-ready roadmap target)
- **Related Bundle:** [post-routemap-direction-selection-input](../../references/working/post-routemap-direction-selection-input/) — Round 8 SDK conventions audit (G4 verdict: clean, with `universe -> why_not` naming correction)
- **Predecessors (shipped):**
  - [2026-05-08_l-direction-g1-check-diagnose (archived)](../archive/2026-05-08_l-direction-g1-check-diagnose.md)
  - [2026-05-07_application-ergonomic-helpers-extension (archived)](../archive/2026-05-07_application-ergonomic-helpers-extension.md)
  - [2026-05-07_walker-mechanism (archived)](../archive/2026-05-07_walker-mechanism.md)
- **Audit Log:** [2026-05-08_l-direction-g4-why-not-frontier.audit.md](./2026-05-08_l-direction-g4-why-not-frontier.audit.md)

## 1. Problem

G1 shipped the first Tier 1 SDK shell pair for Q1 Check and Q2 Diagnose. SDK consumers can now run Check / Diagnose through `SDKStore.check(...)` and `SDKStore.diagnose(...)` without importing `kernel.application`.

The next L group is G4: Why-not + Frontier. Round 8 classified G4 as **clean**, but with an important distinction:

- Why-not can become an SDK shell because it is a result-bearing application capability (`check_why_not_universe(...) -> WhyNotUniverseResult`) with an existing Tier 2 helper for candidate-universe normalization.
- Frontier should remain advanced importable / substrate-facing unless Step 0 finds a narrow SDK projection that does not violate the evaluator frontier drift gates.

This blueprint starts G4 Step 0 only. It does not implement SDK methods until the questions in §5 are source-grounded and scope-frozen.

## 2. Goals

- Decide the G4 SDK outward shape for Why-not and Frontier with the same per-family Step 0 discipline used by G1.
- Reuse G1's SDK shell infrastructure where appropriate, especially `kernel.sdk._validation.validate_derivation(...)` and SDKStore method delegation.
- Preserve the Round 8 naming correction: if Why-not enters SDK, it uses `why_not` vocabulary, not `universe`.
- Determine whether Frontier remains advanced importable or gets a narrow SDK surface.
- Establish a scoped implementation plan only after §5 falsifiers are resolved.

## 3. Non-Goals

- **No implementation in draft.** No `SDKStore.why_not(...)`, `SDKStore.frontier(...)`, module files, docs updates, or tests ship until §5 is locked and status moves to `scoped`.
- **No README quickstart change.** Per `#6`, new SDK shell promotion does not automatically enter README quickstart.
- **No `kernel.sdk.__all__` expansion by default.** G1 set the pattern: SDKStore instance methods first; top-level exports need their own falsifier.
- **No `kernel.sdk` walker or B dependency.** G4 is not evidence traversal. B walker types stay out unless a later Step 0 explicitly activates them.
- **No `factpy` rebrand.** The import root remains `kernel.sdk`; OpenAI-style ergonomics are recorded as post-L redesign preference, not G4 scope.
- **No G2/G3/G5 decisions.** Fact Overlay / ProofFrame, rule overlays, round events, and ProofFrame diff remain separate future blueprints.
- **No evaluator frontier contract changes.** G4 cannot modify `evaluate_native_where_frontier(...)`, normal `evaluate_native_where(...)`, `NativeWhereFrontierEvaluation`, or frontier drift gates unless a separate core blueprint is opened.

## 4. Current Context

### 4.1 L ordering and baseline

Q1 split is locked: **G1 -> G4 -> G2 -> G3 -> G5**, one blueprint per group. G1 is implemented and published; this G4 draft is based on `v0.1-public-surface-helpers-walker-l-g1-2026-05-08` @ `d6716a0`.

Current branch for this draft: `codex/v0.1-l-g4-why-not-frontier-2026-05-08`.

### 4.2 Round 8 G4 verdict

Round 8 SDK conventions audit recorded:

> **G4 Why-not + Frontier: clean** (with naming correction `sdk.universe()` -> `sdk.why_not()`); frontier should remain advanced importable rather than enter SDK facade.

This "clean" verdict means no obvious SDK naming mismatch like G3 and no raw protocol DTO mismatch like G2. It does **not** mean both Why-not and Frontier automatically ship as SDK methods. Frontier has stricter substrate boundaries.

### 4.3 Existing Tier 2 / substrate surfaces

| Area | Existing surface | Layer |
|---|---|---|
| Why-not request helper | `build_why_not_candidate_universe(plan, candidates) -> tuple[BindingItems, ...]` | `kernel.application.capability_helpers` |
| Why-not runtime | `check_why_not_universe(request, *, store, registry=None) -> WhyNotUniverseResult` | `kernel.application` |
| Why-not DTOs | `WhyNotUniverseRequest`, `WhyNotUniverseResult`, `WhyNotRedRow`, `WhyNotRowDiagnostic`, `WhyNotAtomLocator` | `kernel.application.protocol` |
| Frontier projection helper | `build_frontier_view_facts(store) -> dict[str, list[tuple[Any, ...]]]` | `kernel.application.capability_helpers` |
| Frontier evaluator | `evaluate_native_where_frontier(view_facts, where, *, registry=None, ...) -> NativeWhereFrontierEvaluation` | `kernel.core.rules.frontier` |

### 4.4 G1 infrastructure available to reuse

- `SDKStore.check(...)` / `SDKStore.diagnose(...)` established instance-method placement.
- `kernel.sdk._validation.validate_derivation(...)` accepts SDK `Derivation` only and attaches capability-specific `SDKStoreError.path`.
- `kernel.sdk._validation.validate_binding(...)` validates `$`-prefixed binding mappings.
- G1 error mapping uses `SDKStoreError(...) from exc`, including wrapping `RuleCompileError` from dependency registry resolution and `ValueError` from `_compiled_derivation_plan_to_application(...)`.
- G1 did not expand `kernel.sdk.__all__`.

### 4.5 Frontier boundary reminders

The evaluator frontier blueprint deliberately kept Frontier below application capabilities:

- Frontier rows are sparse aggregate rows, not env dumps.
- Frontier is native-only.
- Application layer did not opt into importing `kernel.core.rules.frontier` during Batch 2; `build_frontier_view_facts(...)` is projection-only.
- Future application consumers were required to open a new scoped blueprint before depending on `evaluate_native_where_frontier(...)`.

G4 is such a potential consumer decision point, but it must still respect `#1`, `#5`, `#6`, `#P0`, and the existing frontier drift gates.

## 5. Design — Step 0 Questions

This blueprint is at `draft` status. The questions below must be resolved before status advances to `scoped`.

### 5.1 Why-not SDK input shape

**Question:** Does `SDKStore.why_not(...)` accept:

1. SDK `Derivation` + explicit finite candidate universe,
2. a lower-level application `CompiledDerivationPlan`,
3. a `Store`/query-like shape that discovers the universe internally,
4. or no SDK method at all?

**Conservative default:** SDK `Derivation` + explicit finite candidate universe.

**Decision (2026-05-08):** Lock option 1 — `SDKStore.why_not(derivation, candidates, *, engine="native", registry=None) -> WhyNotUniverseResult`. The SDK accepts an SDK `Derivation` and an explicit candidate-universe argument; it lowers the derivation through G1's existing chain, builds a `WhyNotUniverseRequest` via the Tier 2 helper, and delegates to `check_why_not_universe(...)`. SDK never accepts a `CompiledDerivationPlan` and never auto-discovers the universe from the store.

**Falsifier outcomes:**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | Why-not application contract requires an explicit candidate universe and does not search broadly | `WhyNotUniverseRequest.candidate_universe: tuple[BindingItems, ...]` is a required positional field (`derivation_why_not.py:182`) validated by `_validate_complete_head_universe(...)` in `__post_init__` (`derivation_why_not.py:192-200`). The runtime `check_why_not_universe(request, *, store, registry=None)` only reads `request.candidate_universe` (`why_not_runtime.py:60-76`); module docstring is explicit: "Why-not evaluates one explicit finite candidate universe into a green/red board" (`why_not_runtime.py:1-6`). No auto-discovery code path exists. | PASS — explicit universe required. |
| F2 | SDK `Derivation` lowering can reuse G1's `_compile_derivation_input(...)` / `_compiled_derivation_plan_to_application(...)` path | `WhyNotUniverseRequest.plan` is `CompiledDerivationPlan`, identical to `CheckRequest.plan` and `DiagnoseRequest.plan` already produced by the G1 chain. G1's flow (`check.py:60-95` post-Round 4 Q1) lowers `SDK Derivation -> compiled plans (sdk._compile_derivation_input) -> CompiledDerivationPlan (_compiled_derivation_plan_to_application)`, then passes the plan into the A helper. G4 reuses the same chain verbatim and feeds the result into `build_why_not_candidate_universe(plan, candidates)`. | PASS — chain reusable, no new lowering work in G4. |
| F3 | Reject `CompiledDerivationPlan` unless a source-grounded SDK precedent exists for accepting application protocol inputs | G1 §5.7 lock (archived blueprint) rejects `CompiledDerivationPlan` at the SDK boundary as already-lowered application-layer entry. No SDK method shipped to date accepts `CompiledDerivationPlan` as input. `kernel.sdk._validation.validate_derivation(obj, *, path)` rejects everything that is not `kernel.sdk.dsl.Derivation`, and G4 will reuse it verbatim with `path="$.why_not.derivation"`. | PASS — reject confirmed; no precedent for accepting `CompiledDerivationPlan`. |
| F4 | Reject store-wide universe discovery unless user signal justifies a new outward compatibility commitment | No A helper, no runtime function, and no SDK precedent currently performs store-wide universe discovery for Why-not. Adding it would (a) introduce a new outward shape under `#6` (no outward compat without signal), and (b) cross substrate boundaries beyond G4's scope. Round 8 G4 verdict cited only the explicit-universe shape. | PASS — reject confirmed; future store-discovery, if ever needed, requires its own scoped blueprint. |

**Forward implications:**

- §5.2 (candidate universe input shape) is the next falsifier and is sharpened by this lock: the SDK input is a `candidates` argument carrying an explicit finite universe; A's `build_why_not_candidate_universe(plan, candidates)` will normalize it. The remaining §5.2 question is which row forms (mappings / sequences / SDK refs / `BindingItems`) the SDK accepts.
- G4 reuses `kernel.sdk._validation.validate_derivation(...)` (Round 4 Q1 extraction). No additional Derivation-shape validator is needed.
- G4's SDK signature pattern parallels G1: `(derivation, <capability-specific second arg>, *, engine="native", registry=None)`. This consistency is a side-effect of the lock, not a separate constraint.

### 5.2 Candidate universe input shape

**Question:** What does the SDK caller pass as candidates?

Options:

- `Sequence[Mapping[str, Any] | Sequence[Any]]`, directly mirroring A's `build_why_not_candidate_universe(...)`.
- SDK entity snapshots / refs / DSL objects.
- `BindingItems` tuple form.
- A named SDK-owned candidate-universe DTO.

**Conservative default:** mirror A's row forms: mappings or sequences normalized against the plan head variable order.

**Falsifiers required:**

- Confirm this does not require importing A private normalization helpers.
- Confirm SDK entity snapshots are not needed for first slice.
- Confirm tuple-form `BindingItems` does not leak application canonical shape into SDK inputs without benefit.

### 5.3 Why-not return shape

**Question:** Does `SDKStore.why_not(...)` return `WhyNotUniverseResult` directly, wrap it in SDK-owned DTO, or expose a simplified board?

**Conservative default:** documented passthrough of `WhyNotUniverseResult`, mirroring G1.

**Falsifiers required:**

- Confirm existing SDK raw-passthrough precedent still applies.
- Confirm `WhyNotUniverseResult` is not added to `kernel.sdk.__all__`.
- If a wrapper is proposed, source-ground why its shape is durable and necessary now.

### 5.4 Frontier placement

**Question:** Does G4 ship any SDK-facing Frontier method?

Options:

- No Frontier SDK method; document advanced importable path only.
- `SDKStore.frontier(...)` that accepts SDK `Derivation` and returns `NativeWhereFrontierEvaluation`.
- A projection-only helper on `SDKStore` that returns `view_facts`.
- A combined Why-not+Frontier method.

**Conservative default:** no Frontier SDK method in first G4 slice; keep advanced importable.

**Falsifiers required:**

- Confirm whether Frontier still violates or satisfies the "SDK complete round story" signal if kept advanced importable.
- Confirm any SDK Frontier method does not import application-only helpers incorrectly or pierce evaluator drift gates.
- Reject combined Why-not+Frontier if it false-merges result-bearing board output with substrate aggregate rows (`#3`).

### 5.5 Module and method placement

**Question:** Does G4 follow G1's flat module pattern or trigger the `kernel/sdk/shells/` migration mentioned in G1 §5.5?

Options:

- Continue flat modules: `kernel/sdk/why_not.py` and maybe `kernel/sdk/frontier.py`.
- Migrate G1 + G4 shell files into `kernel/sdk/shells/`.
- Put Why-not logic directly in `store.py`.

**Conservative default:** continue flat modules unless the number of shell files or import structure becomes visibly noisy during the scoping pass.

**Falsifiers required:**

- Count shell files after G4 and compare with G1's trigger.
- Verify migration cost / churn if moving G1 files now.
- Keep `SDKStore` methods as thin delegates either way.

### 5.6 Error mapping

**Question:** Which non-A helper/runtime exceptions must be remapped to `SDKStoreError`?

Known candidates:

- `CapabilityHelperError` from `build_why_not_candidate_universe(...)`.
- `WhyNotRuntimeError` from `check_why_not_universe(...)`.
- `RuleCompileError` from registry resolution.
- `ValueError` from derivation lowering / engine extension conversion.
- Frontier `WhereValidationError` / `ValueError` if Frontier enters SDK.

**Conservative default:** follow G1: every non-SDK exception crossing SDK shell boundary is remapped to `SDKStoreError(...) from exc` with a capability-specific path.

### 5.7 Test layout and invariants

**Question:** What focused test files and cross-cutting invariants are required?

**Conservative default:**

- `src/kernel/tests/test_sdk_why_not.py`
- `src/kernel/tests/test_sdk_g4_invariants.py`
- `test_sdk_frontier.py` only if a Frontier SDK method ships.

Tests stay flat under `src/kernel/tests/`; no nested SDK test directory.

## 6. Boundaries And Invariants

| Principle | G4 interpretation |
|---|---|
| `#1` Application-first authority | SDK shell lowers and delegates; it does not own Why-not or Frontier semantics. |
| `#3` Heterogeneity | Why-not board and Frontier aggregate rows must not be false-merged. |
| `#4a` Intent-minimal canonical input | SDK accepts SDK-layer intent and lowers; application accepts canonical DTOs. |
| `#5` Layer isolation | `kernel.sdk` may import public `kernel.application` surfaces; application/core must not import SDK. |
| `#6` No outward compat without signal | New SDK methods and return shapes are outward commitments; keep narrow. |
| `#19` Testing | Flat unittest files and flat fixtures only. |
| `#P0` Conflict resolution | Authority > layer isolation > read-only > ergonomics > outward commitment. |
| `#P1` Revision flow | Any deviation from G1/L locks gets a named carve-out with reason/scope/impact. |

Forbidden until scoped:

- No `kernel.sdk.__all__` addition.
- No README quickstart update.
- No `factpy` alias / rename.
- No `kernel.application` import of `kernel.sdk`.
- No application-layer import of `kernel.core.rules.frontier` unless Step 0 explicitly scopes a new application opt-in and updates frontier drift gates.
- No direct A private helper import from SDK.
- No broad candidate universe search unless scoped by falsifier.

## 7. Acceptance

Draft-stage acceptance:

- [x] G4 draft opened on the latest G1 combined baseline.
- [x] Round 8 G4 clean verdict and `universe -> why_not` correction captured.
- [x] G1 infrastructure and Q1 validation extraction captured as available prior art.
- [x] Why-not / Frontier boundary split documented.
- [ ] §5.1-§5.7 falsifier passes complete.
- [ ] Status moves to `scoped` only after all Step 0 questions are resolved.

Scoped-stage acceptance will be filled once §5 is locked.

## 8. Implementation Plan

Deferred until status `scoped`.

Expected shape if Step 0 follows conservative defaults:

1. Phase 0: module skeleton / SDKStore method stubs / tests.
2. Phase 1: `SDKStore.why_not(...)` real implementation.
3. Phase 2: cross-cutting invariants and docs.
4. Phase 3: close-out, archive, snapshot publish.

Frontier phases are added only if §5.4 scopes a Frontier SDK method.

## 9. Docs To Update

If implementation is scoped:

- `src/kernel/sdk/docs/04_api_surface.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/application/docs/01_overview.md`
- `src/kernel/application/docs/01_overview_en.md`
- `docs/blueprints/archive/README.md` on archive

README quickstart remains untouched unless a separate blueprint scopes it.

## 10. Outcome / Deviations

To be filled after implementation.

