# L Direction G4 — Why-not + Frontier SDK Shell

- **Status:** implementing
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

This blueprint has completed G4 Step 0 and is scoped for implementation of `SDKStore.why_not(...)`.

## 2. Goals

- Decide the G4 SDK outward shape for Why-not and Frontier with the same per-family Step 0 discipline used by G1.
- Reuse G1's SDK shell infrastructure where appropriate, especially `kernel.sdk._validation.validate_derivation(...)` and SDKStore method delegation.
- Preserve the Round 8 naming correction: if Why-not enters SDK, it uses `why_not` vocabulary, not `universe`.
- Determine whether Frontier remains advanced importable or gets a narrow SDK surface.
- Establish and execute a scoped implementation plan after §5 falsifiers are resolved.

## 3. Non-Goals

- **No implementation outside this scope.** `SDKStore.why_not(...)` is the only SDK method scoped; `SDKStore.frontier(...)` remains out of scope.
- **No README quickstart change.** Per `#6`, new SDK shell promotion does not automatically enter README quickstart.
- **No `kernel.sdk.__all__` expansion by default.** G1 set the pattern: SDKStore instance methods first; top-level exports need their own falsifier.
- **No `kernel.sdk` walker or B dependency.** G4 is not evidence traversal. B walker types stay out unless a later Step 0 explicitly activates them.
- **No `factpy` rebrand.** The import root remains `kernel.sdk`; OpenAI-style ergonomics are recorded as post-L redesign preference, not G4 scope.
- **No G2/G3/G5 decisions.** Fact Overlay / ProofFrame, rule overlays, round events, and ProofFrame diff remain separate future blueprints.
- **No evaluator frontier contract changes.** G4 cannot modify `evaluate_native_where_frontier(...)`, normal `evaluate_native_where(...)`, `NativeWhereFrontierEvaluation`, or frontier drift gates unless a separate core blueprint is opened.

## 4. Current Context

### 4.1 L ordering and baseline

Q1 split is locked: **G1 -> G4 -> G2 -> G3 -> G5**, one blueprint per group. G1 is implemented and published; this G4 blueprint is based on `v0.1-public-surface-helpers-walker-l-g1-2026-05-08` @ `d6716a0`.

Current branch: `codex/v0.1-l-g4-why-not-frontier-2026-05-08`.

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

All seven questions below are source-grounded and locked; implementation must stay inside these answers unless the audit log records a `#P1` carve-out first.

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

**Decision (2026-05-08):** Lock option 1 — `candidates: Sequence[Mapping[str, Any] | Sequence[Any]]`, passed to A's public `build_why_not_candidate_universe(plan, candidates)` helper after SDK derivation lowering. G4 mirrors A's row forms exactly: mapping rows are indexed by plan head variable names; sequence rows are interpreted in plan head variable order. SDK entity snapshots / refs / DSL objects, direct `BindingItems`, and SDK-owned candidate-universe DTOs are out of scope for the first slice.

**Falsifier outcomes:**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | No A private normalization helper import needed | `build_why_not_candidate_universe` is exported from `kernel.application.capability_helpers.__all__` and re-exported from `kernel.application.__all__`; its implementation owns `_candidate_values(...)` and calls `normalize_binding_items(...)` internally (`capability_helpers/why_not.py:15-33`). G4 only imports this public builder, not `_candidate_values`, `normalize_binding_items`, `_binding`, or any private helper. | PASS — public A helper is sufficient. |
| F2 | First slice does not need SDK entity snapshots / refs / DSL objects | A helper tests already cover mapping rows (`{"$region": "us", "$p": alice.e_ref, "$age": 30}`) and sequence rows (`(alice.e_ref, 30, "us")`) as sufficient inputs (`test_application_capability_helpers.py:398-427`). No shipped Why-not helper, runtime, SDK method, or Round 8 G4 evidence requires hydrated entity snapshots or DSL objects for candidate rows. | PASS — SDK entity objects deferred; row values remain ordinary Python values. |
| F3 | Direct `BindingItems` tuple form would leak application canonical shape without benefit | `BindingItems` is imported from `kernel.core.store._support` by A's helper as its output canonical type, not advertised as SDK input. Passing tuple-of-tuples as a candidate row would be ambiguous at SDK boundary: it is also a `Sequence[Any]` row and would be interpreted positionally, not as "already normalized" application canonical input. G1 §5.7 already rejected application protocol/canonical inputs at SDK boundary when an intent-shaped input exists. | PASS — reject `BindingItems` as explicit SDK input. |
| F4 | A `CapabilityHelperError` paths are remappable at SDK boundary | A helper raises `CapabilityHelperError` for malformed candidate universes: non-sequence `candidates`, incomplete mapping rows, wrong sequence length, and non-row values (`capability_helpers/why_not.py:21-58`). G1 already maps `CapabilityHelperError` to `SDKStoreError(...) from exc` in Check/Diagnose; §5.6 will require G4 to map candidate helper failures to `SDKStoreError(path="$.why_not.candidates")`. | PASS — error boundary fits existing G1 pattern. |
| F5 | SDK-owned candidate-universe DTO is unnecessary now | A's public helper already gives a small, intent-shaped input surface and canonicalizes into `tuple[BindingItems, ...]` accepted by `WhyNotUniverseRequest`; creating a SDK DTO would add a new outward type under `#6` without source-grounded user signal. | PASS — no SDK DTO first slice. |

**Forward implications:**

- `SDKStore.why_not(...)` signature second argument is named `candidates`, not `candidate_universe`; the latter remains the application DTO field name after A normalization.
- Implementation wraps `build_why_not_candidate_universe(plan, candidates)` in `try/except CapabilityHelperError as exc` and remaps to `SDKStoreError(..., path="$.why_not.candidates") from exc`.
- Test coverage must include both mapping-row and sequence-row success, plus missing-key / wrong-length failures crossing the SDK boundary as `SDKStoreError` with `__cause__` set.

### 5.3 Why-not return shape

**Question:** Does `SDKStore.why_not(...)` return `WhyNotUniverseResult` directly, wrap it in SDK-owned DTO, or expose a simplified board?

**Conservative default:** documented passthrough of `WhyNotUniverseResult`, mirroring G1.

**Decision (2026-05-08):** Lock documented passthrough — `SDKStore.why_not(...)` returns the raw application protocol `WhyNotUniverseResult` directly, mirroring G1's §5.2 lock (`SDKStore.check(...) -> CheckResult`, `SDKStore.diagnose(...) -> DiagnoseResult`). The result type is documented in the SDK shell docstring and `kernel.sdk.docs.04_api_surface.md`, but is NOT re-exported from `kernel.sdk.__all__`. SDK callers either import `WhyNotUniverseResult` from `kernel.application.protocol` themselves (advanced importable, per `#6`), or use it via `result.<attr>` access without importing the type.

**Falsifier outcomes:**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | Existing SDK raw-passthrough precedent still applies | G1 archived §5.2 locks documented passthrough; runtime verification: `kernel.sdk.__all__` length is 34, `CheckResult` and `DiagnoseResult` are NOT in `__all__`, G1 invariant `test_sdk_all_is_unchanged_and_result_types_are_not_exported` enforces this. Pattern is unchanged since G1 publish at `d6716a0`. | PASS — precedent in force. |
| F2 | `WhyNotUniverseResult` is not added to `kernel.sdk.__all__` | Current `kernel.sdk.__all__` does not contain `WhyNotUniverseResult`, `WhyNotRedRow`, `WhyNotRowDiagnostic`, `WhyNotAtomLocator`, or any other Why-not DTO (verified at runtime). Lock requires the SDK shell to retain this state — no `__init__.py` `__all__` extension during G4 implementation; G4 invariant test will mirror G1's. | PASS — current state matches lock; G4 must preserve. |
| F3 | If a wrapper is proposed, source-ground why its shape is durable and necessary now | `WhyNotUniverseResult` is a `@dataclass(frozen=True)` with fields `status` (literal), `requested_universe` / `green` (tuples of `BindingItems`), `red` (tuple of `WhyNotRedRow`), `errors` / `warnings` (tuples of `ErrorDTO` / `WarningDTO`) — all application-canonical types, no mutable inner state, no opaque internals to redact (`derivation_why_not.py:294-332`). Direct attribute access already ergonomic. A wrapper would (a) force a new outward compat commitment under `#6` without user signal, (b) duplicate field forwarding for zero added value, (c) couple SDK to a wrapper version that drifts from protocol. No source signal justifies wrapping. | PASS — no wrapper. |

**Forward implications:**

- §5.4 (Frontier placement) is independent of return shape and is the next falsifier.
- §5.6 (error mapping) inherits G1 pattern: `WhyNotRuntimeError` (`why_not_runtime.py:35`) and `CapabilityHelperError` from candidate normalization both must remap to `SDKStoreError(...) from exc` with capability-specific paths.
- G4 acceptance will include an invariant test: `kernel.sdk.__all__` length unchanged at 34 (or whatever the post-G4 baseline is, with G4 confirming no additions); `WhyNotUniverseResult` not exported.

### 5.4 Frontier placement

**Question:** Does G4 ship any SDK-facing Frontier method?

Options:

- No Frontier SDK method; document advanced importable path only.
- `SDKStore.frontier(...)` that accepts SDK `Derivation` and returns `NativeWhereFrontierEvaluation`.
- A projection-only helper on `SDKStore` that returns `view_facts`.
- A combined Why-not+Frontier method.

**Conservative default:** no Frontier SDK method in first G4 slice; keep advanced importable.

**Decision (2026-05-08):** Lock option 1 — **no Frontier SDK method in G4 first slice**. G4 implementation ships `SDKStore.why_not(...)` only. Frontier remains advanced importable through `kernel.core.rules.frontier.evaluate_native_where_frontier(...)` plus the Tier 2 projection helper `kernel.application.capability_helpers.build_frontier_view_facts(...)`. G4 docs may point advanced callers at that path, but `kernel.sdk` does not import `kernel.core.rules.frontier`, does not add `SDKStore.frontier(...)`, and does not add a projection-only `SDKStore.frontier_view_facts(...)`.

**Falsifier outcomes:**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | Frontier-as-advanced-importable still matches the recorded Round 8 G4 verdict | Round 8 Lane 3 explicitly recorded: "G4 Why-not + Frontier: clean (with naming correction `sdk.universe()` -> `sdk.why_not()`); frontier should remain advanced importable rather than enter SDK facade" (`README.md` Round 8; `30_recommendation.md` L607). This is not a silent omission — it is the source-grounded G4 classification. | PASS — keeping Frontier advanced importable is the Round 8 verdict, not a regression. |
| F2 | A SDK Frontier method would pierce existing Frontier drift gates / layer boundaries | Frontier blueprint scoped native evaluator substrate only: "No application protocol DTOs, SDK shell, UI, or public application capability" (`evaluator-frontier-trace-capability.md:34-36`). Its close-out says future application consumers must open a new scoped blueprint before importing or depending on `evaluate_native_where_frontier(...)` (`...md:210-214`). The runtime drift gate `test_10_application_layer_does_not_opt_into_frontier_trace` scans application files and asserts no Frontier imports or symbol use (`test_core_rules_frontier_drift_gates.py:412-419`). SDK directly importing core Frontier would skip that required application opt-in step and create a Tier 1 -> core substrate dependency without a Tier 2 boundary. | PASS — no SDK Frontier method in G4. |
| F3 | Combined Why-not+Frontier method would false-merge heterogeneous outputs | Why-not returns `WhyNotUniverseResult`: explicit finite-universe green/red board with row diagnostics. Frontier returns `NativeWhereFrontierEvaluation`: native aggregate success bindings plus sparse per-branch `frontier_rows`; the Frontier blueprint stresses aggregate-only rows, no env dump, native-only, substrate-level semantics (`evaluator-frontier-trace-capability.md:72-130`). These are different capabilities and layers. `#3` heterogeneity and G1's rejection of scenario merge apply directly. | PASS — no combined method. |
| F4 | Projection-only `SDKStore.frontier_view_facts(...)` adds too little value | A's `build_frontier_view_facts(store)` only projects a `Store` to `view_facts`; callers must still import and call `evaluate_native_where_frontier(...)` themselves (`capability_helpers/frontier.py:13-18`, helper test lines 450-455). A SDK method that only returns `view_facts` would expose an intermediate substrate shape without actually giving SDK callers a complete Frontier capability. | PASS — no projection-only SDK method. |

**Forward implications:**

- `SDKStore.why_not(...)` is the only G4 SDK method scoped by this blueprint.
- No `kernel/sdk/frontier.py`, no `test_sdk_frontier.py`, and no `SDKStore.frontier(...)` phase in §8.
- `src/kernel/sdk/docs/04_api_surface.md` should document Why-not; it may mention Frontier remains advanced importable but must not advertise it as a SDK facade method.
- G5 or a future Frontier-specific blueprint may reopen SDK Frontier only after a Tier 2 application opt-in or an explicit `#P1` carve-out updates the frontier drift gates.

### 5.5 Module and method placement

**Question:** Does G4 follow G1's flat module pattern or trigger the `kernel/sdk/shells/` migration mentioned in G1 §5.5?

Options:

- Continue flat modules: `kernel/sdk/why_not.py` and maybe `kernel/sdk/frontier.py`.
- Migrate G1 + G4 shell files into `kernel/sdk/shells/`.
- Put Why-not logic directly in `store.py`.

**Conservative default:** continue flat modules unless the number of shell files or import structure becomes visibly noisy during the scoping pass.

**Decision (2026-05-08):** Lock continued flat layout — `SDKStore.why_not(...)` lands at `src/kernel/sdk/why_not.py` exporting `sdk_why_not(...)`, mirroring G1's `check.py` / `diagnose.py` pattern verbatim. SDKStore method delegates via `from .why_not import sdk_why_not`. The G1 §5.5 forward trigger (originally named "G2") is **re-recorded as a G2 Step 0 requirement** — see "Forward implications" below. G4 does not migrate G1 files into a `kernel/sdk/shells/` subpackage.

**Falsifier outcomes:**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | Count shell files after G4 and compare with G1's trigger | Current shell files post-G1: `check.py` + `diagnose.py` (2). G4 adds `why_not.py` only (Frontier deferred per §5.4). Post-G4 count: 3. G1 §5.5 forward trigger reads "when G2 would add the third/fourth SDK shell file, its Step 0 MUST re-evaluate" (`docs/blueprints/archive/2026-05-08_l-direction-g1-check-diagnose.md:309`). The threshold is 3-4 files; G4 reaches 3. Q1 ordering changed (G1 -> **G4** -> G2 -> G3 -> G5) so the literal "G2" wording is stale; the **intent** (file-count-driven re-evaluation) transfers to G4 as the next group. | At threshold — re-evaluation owed; not auto-migration. |
| F2 | Verify migration cost / churn if moving G1 files now | G1 ships an explicit invariant test `test_g1_modules_are_flat_and_no_shells_package_exists` (referenced in G1 archived §5.5 lock) that asserts the absence of `kernel/sdk/shells/`. Migrating now requires (a) `#P1` carve-out to update / replace this G1-archived invariant, (b) moving 3 source files (`check.py`, `diagnose.py`, `why_not.py`), (c) updating `_validation.py` import paths from siblings, (d) updating `SDKStore` delegate imports in `store.py`, (e) updating 3+ test files that reference `kernel.sdk.check` / `kernel.sdk.diagnose`, (f) audit-log entry on G1 archived branch. G4 currently adds 1 new file; the migration cost dwarfs the new-file cost. | High — defer. |
| F3 | Keep `SDKStore` methods as thin delegates either way | G1 pattern: `SDKStore.check(self, ...) -> CheckResult` body is `from .check import sdk_check; return sdk_check(self, ...)` with no behavior. G4 `SDKStore.why_not` will mirror this — `from .why_not import sdk_why_not; return sdk_why_not(self, ...)`. Thin delegate preserved under flat layout (Option A) and would also be preserved under shells/ (Option B). Independent of placement. | PASS for either option. |
| F4 | Re-recorded trigger to G2 Step 0 is verifiable | G2 will land the next batch of SDK shells (Fact Overlay + ProofFrame Recheck per Round 8 — at least 2 new files). After G2 lands, shell-file count would be 5. G2 Step 0 falsifier set MUST include "before adding the first new shell file, re-evaluate `kernel/sdk/shells/` migration; if migration happens, do it as G2 Phase 0 hygiene before any G2 implementation." This forward record makes the trigger physically owned by G2's Step 0 design rather than getting lost as a paragraph in G4's audit log. | PASS — recorded below. |

**Forward implications:**

- **G2 Step 0 forward trigger (re-recorded from G1 §5.5):** Before G2's Step 0 lock, G2 MUST evaluate whether `kernel/sdk/shells/` subpackage migration happens as G2 Phase 0 hygiene (before any G2 implementation). At the time G2 starts, shell-file count will already be 3 (`check.py`, `diagnose.py`, `why_not.py`); G2 adds at least 2 more. The trigger is at the file-count signal, not at any specific blueprint name; G4 inherited it from G1 and now passes it forward to G2. The accompanying decision must address the G1 invariant test `test_g1_modules_are_flat_and_no_shells_package_exists` via explicit `#P1` carve-out.
- G4 invariant tests (G4 acceptance) will mirror G1: assert flat layout for `why_not.py`, assert no `kernel/sdk/shells/` exists, assert `kernel.sdk.__all__` length unchanged, assert `WhyNotUniverseResult` not exported.
- §5.6 (error mapping) is independent of placement and is the next falsifier.

### 5.6 Error mapping

**Question:** Which non-A helper/runtime exceptions must be remapped to `SDKStoreError`?

Known candidates:

- `CapabilityHelperError` from `build_why_not_candidate_universe(...)`.
- `WhyNotRuntimeError` from `check_why_not_universe(...)`.
- `RuleCompileError` from registry resolution.
- `ProtocolShapeError` from `WhyNotUniverseRequest(...)` construction.
- `ValueError` from derivation lowering / engine extension conversion.
- Frontier `WhereValidationError` / `ValueError` if Frontier enters SDK (inactive per §5.4).

**Conservative default:** follow G1: every non-SDK exception crossing SDK shell boundary is remapped to `SDKStoreError(...) from exc` with a capability-specific path.

**Decision (2026-05-08):** lock the G1-style boundary remap for
`SDKStore.why_not(...)`. Every lower-layer exception that can cross the SDK
shell boundary becomes `SDKStoreError(...) from exc`; no new SDK error subclass
is introduced.

| Source | Remap |
|---|---|
| `validate_derivation(...)` | Already raises `SDKStoreError(path="$.why_not.derivation")`. |
| `_compiled_derivation_plan_to_application(...)` `ValueError` | `SDKStoreError(path="$.why_not.derivation") from exc`. |
| `_resolve_runtime_registry(...)` `RuleCompileError` | `SDKStoreError(path="$.why_not.dependencies") from exc`. |
| `build_why_not_candidate_universe(...)` `CapabilityHelperError` | `SDKStoreError(path="$.why_not.candidates") from exc`. |
| `WhyNotUniverseRequest(...)` `ProtocolShapeError` | `SDKStoreError(path="$.why_not.request") from exc`. |
| `check_why_not_universe(...)` `WhyNotRuntimeError` | `SDKStoreError(path="$.why_not") from exc`. |

Falsifier outcomes:

1. `WhyNotRuntimeError` must be wrapped. It is an application runtime
   `ValueError` subclass with multiple runtime-only raise sites; allowing it to
   propagate would violate the G1 §5.3 SDK boundary rule.
2. `ProtocolShapeError` must be wrapped. `WhyNotUniverseRequest.__post_init__`
   validates `plan`, single-head shape, complete candidate universe, and
   `engine`; because G4 delegates request-shape validation to that DTO, raw
   `ProtocolShapeError` must not leak across `kernel.sdk`.
3. Derivation lowering and dependency registry failures follow the already
   landed G1 B.2 / B.1 remap pattern.
4. Candidate universe shape errors belong to A's public helper; they remap at
   `$.why_not.candidates`, preserving the `CapabilityHelperError` cause chain.
5. Frontier error mapping is inactive. G4 ships no Frontier SDK method per
   §5.4, so Frontier `WhereValidationError` / substrate `ValueError` handling
   is out of scope.

Forward implication: G4 implementation tests must cover all five remap paths
above plus the direct `validate_derivation(...)` path, and must assert
`__cause__` chaining so application-layer errors stay inspectable without
becoming SDK API errors.

### 5.7 Test layout and invariants

**Question:** What focused test files and cross-cutting invariants are required?

**Conservative default:**

- `src/kernel/tests/test_sdk_why_not.py`
- `src/kernel/tests/test_sdk_g4_invariants.py`
- `test_sdk_frontier.py` only if a Frontier SDK method ships.

Tests stay flat under `src/kernel/tests/`; no nested SDK test directory.

**Decision (2026-05-08):** Lock the conservative default. G4 ships exactly two test files, both flat under `src/kernel/tests/`:

- **`src/kernel/tests/test_sdk_why_not.py`** — Why-not per-method contract tests (mirroring G1's `test_sdk_check.py` / `test_sdk_diagnose.py` 14-17-test cadence). Covers each §5.1-§5.6 lock with at least one assertion; includes Sibling-discipline tests (static + runtime) verifying `sdk_why_not` does not call `sdk_check` or `sdk_diagnose`. Estimated ≈ 16-18 tests.
- **`src/kernel/tests/test_sdk_g4_invariants.py`** — G4 cross-cutting invariants (mirroring G1's `test_sdk_g1_invariants.py` 6-test single-class structure). Six classes mapping 1-to-1 to G1's invariants, scoped to G4's surface.

`test_sdk_frontier.py` is **not** created — §5.4 locked no Frontier SDK method.

**Falsifier outcomes:**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | Test file count and naming follows G1's per-method + invariant pattern | G1 ships `test_sdk_check.py` (16 tests), `test_sdk_diagnose.py` (19 tests including Q1 Sibling), `test_sdk_g1_invariants.py` (6 tests in single `SDKG1InvariantTests` class). G4 mirrors with one capability test file (`test_sdk_why_not.py`) plus one invariant file (`test_sdk_g4_invariants.py`) — same naming convention `test_sdk_{capability}.py` + `test_sdk_g{N}_invariants.py`. No `test_sdk_frontier.py` per §5.4 lock. | PASS — pattern symmetric. |
| F2 | Per-method tests cover all §5.1-§5.6 locks | Each lock maps to at least one test in `test_sdk_why_not.py`: §5.1 (SDK Derivation accepted, `Rule`/`CompiledDerivationPlan` rejected); §5.2 (mapping rows + sequence rows + malformed-row error); §5.3 (raw `WhyNotUniverseResult` returned, not in `__all__`); §5.4 (no Frontier SDK method exists — covered in invariant file by absence assertion); §5.5 (module path verified); §5.6 (each of the 5 remap paths tested with mock-injected exceptions: `ValueError` from compiled-plan, `RuleCompileError` from registry, `CapabilityHelperError` from candidate helper, `ProtocolShapeError` from request DTO, `WhyNotRuntimeError` from runtime). | PASS — coverage plan complete. |
| F3 | Invariant tests cover all §6 principles + §5.5 layout requirements | G4 invariant file mirrors G1 1-to-1: (1) `test_sdk_all_is_unchanged_and_result_types_are_not_exported` — `kernel.sdk.__all__` length unchanged, `WhyNotUniverseResult` not exported; (2) `test_g4_method_is_instance_method_and_no_scenario_method_shipped` — `SDKStore.why_not` is instance method, no top-level `why_not` free function; (3) `test_g4_modules_are_flat_and_no_shells_package_exists` — `kernel/sdk/why_not.py` is flat sibling, no `kernel/sdk/shells/`; (4) `test_g4_modules_do_not_import_internal_or_walker_layers` — `kernel.sdk.why_not` source has no import of `kernel.application.capability_helpers._binding`, `kernel.application.walker.*`, `kernel.audit.*`; (5) `test_store_method_remains_thin_delegate_method` — `SDKStore.why_not` body is just `from .why_not import sdk_why_not; return sdk_why_not(self, ...)`; (6) `test_store_method_docstring_records_boundary_contract` — docstring mentions `WhyNotUniverseResult`, `SDKStoreError`, and `$.why_not.*` paths. | PASS — six invariant classes, one per G1 invariant slot. |
| F4 | Q1-Sibling-style discipline tested in both static + runtime forms | Even though Why-not has no symmetric Check sibling (it's a single capability), the Sibling discipline still applies — `sdk_why_not` MUST NOT internally call `sdk_check` or `sdk_diagnose`. Two tests in `test_sdk_why_not.py`: (a) runtime patch of `sdk_check` + `sdk_diagnose` and assert neither is invoked during a `sdk.why_not(...)` call; (b) static source scan of `kernel/sdk/why_not.py` confirming no `from .check`, `from .diagnose`, `sdk_check(`, or `sdk_diagnose(` references. Mirrors G1 Diagnose pattern verbatim. | PASS — two-form discipline preserved. |
| F5 | Tests stay flat (no nested `tests/sdk/` directory) | G1 §5.6 lock kept tests flat in `src/kernel/tests/`. Current inventory: `test_sdk_check.py`, `test_sdk_diagnose.py`, `test_sdk_g1_invariants.py`, `test_sdk_validation.py` — all flat. G4 adds `test_sdk_why_not.py` + `test_sdk_g4_invariants.py` at the same flat level. No `tests/sdk/` subdirectory. Fixtures (e.g., `Person` Entity, `_seed_person(...)`, `_age_derivation()`) inline per test file — duplication intentional per G1 §5.6 (see Round 4 audit C.7 Minor recorded as accepted). If a future shared fixture file becomes necessary, G2 Phase 0 hygiene (alongside the `kernel/sdk/shells/` migration trigger inherited from G1 §5.5) is the right venue. | PASS — flat layout preserved. |

**Forward implications:**

- All seven §5.1-§5.7 are now locked.
- Scoped-stage acceptance in §7 enumerates the per-phase gates, including §5.6 remap paths and §5.7 invariant coverage.
- Implementation phase plan in §8 follows G1's 4-phase template: Phase 0 skeleton + delegate stubs → Phase 1 real implementation + contract tests → Phase 2 invariants + cross-cutting tests + docs → Phase 3 archive + snapshot publish.

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

Forbidden during implementation unless a later blueprint explicitly scopes a carve-out:

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
- [x] §5.1-§5.7 falsifier passes complete.
- [x] Status moves to `scoped` only after all Step 0 questions are resolved.

Scoped-stage acceptance:

- [ ] Phase 0 ships only `src/kernel/sdk/why_not.py` skeleton, `SDKStore.why_not(...)` thin delegate, and placeholder flat tests; no real runtime dispatch yet.
- [ ] Phase 1 implements `sdk_why_not(...)` with the locked signature and return shape:
  `SDKStore.why_not(derivation, candidates, *, engine="native", registry=None) -> WhyNotUniverseResult`.
- [ ] Phase 1 validates SDK `Derivation` via `validate_derivation(..., path="$.why_not.derivation")`, lowers through the G1 derivation path, normalizes candidates through `build_why_not_candidate_universe(...)`, constructs `WhyNotUniverseRequest`, dispatches `check_why_not_universe(...)`, and returns the raw `WhyNotUniverseResult`.
- [ ] Phase 1 maps all §5.6 lower-layer errors to `SDKStoreError(...) from exc` with the locked paths: `$.why_not.derivation`, `$.why_not.dependencies`, `$.why_not.candidates`, `$.why_not.request`, and `$.why_not`.
- [ ] Phase 1 tests cover mapping rows, sequence rows, malformed candidates, invalid derivation input, multi-plan derivation rejection, dependency registry failure, request DTO `ProtocolShapeError`, runtime `WhyNotRuntimeError`, and no internal call to G1 `sdk_check` / `sdk_diagnose`.
- [ ] Phase 2 adds `test_sdk_g4_invariants.py` with the six locked invariants: `__all__` unchanged and `WhyNotUniverseResult` absent, instance-method placement, flat module/no `shells/`, no internal/walker/audit imports, thin delegate, and boundary docstring.
- [ ] Phase 2 updates SDK/application module docs listed in §9 while leaving README quickstart untouched.
- [ ] Phase 2 runs focused G4 tests plus the relevant SDK/application regression suite and performs a strict audit before close-out.
- [ ] Phase 3 fills Outcome / Deviations, marks this blueprint `implemented`, archives blueprint + audit log, updates `docs/blueprints/archive/README.md`, and publishes a `v0.1-l-g4-why-not-frontier-2026-05-08` snapshot.

## 8. Implementation Plan

### Phase 0 — Skeleton And Delegation Hook

Scope:

- Add `src/kernel/sdk/why_not.py` with `sdk_why_not(...)` placeholder matching the locked signature.
- Add `SDKStore.why_not(...)` as a thin delegate in `src/kernel/sdk/store.py`.
- Add flat placeholder tests in `test_sdk_why_not.py` and `test_sdk_g4_invariants.py`.
- Do not add `kernel.sdk.__all__` entries, `kernel/sdk/frontier.py`, `test_sdk_frontier.py`, or `kernel/sdk/shells/`.

Audit gate: verify flat module placement, delegate shape, locked signature, no `__all__` expansion, and no runtime dispatch.

### Phase 1 — Real `SDKStore.why_not(...)`

Scope:

- Implement `sdk_why_not(...)` using the G1 derivation lowering path and A's `build_why_not_candidate_universe(...)`.
- Construct `WhyNotUniverseRequest(...)` and dispatch `check_why_not_universe(...)`.
- Return raw `WhyNotUniverseResult`.
- Implement all §5.6 remap paths with `SDKStoreError(...) from exc`.
- Fill `test_sdk_why_not.py` contract coverage for §5.1-§5.6.

Audit gate: strict code-quality and design-alignment audit focused on error remaps, layer imports, return shape, and Q1 Sibling independence from Check / Diagnose.

### Phase 2 — Invariants And Docs

Scope:

- Add `test_sdk_g4_invariants.py` with the six §5.7 invariant slots.
- Update SDK/application module docs listed in §9.
- Keep README quickstart unchanged.
- Run focused G4 tests plus relevant SDK/application regression suites.

Audit gate: cumulative G4 strict audit before close-out; all findings either fixed or recorded as explicit deferred minors.

### Phase 3 — Close-Out, Archive, Publish

Scope:

- Fill §10 Outcome / Deviations.
- Mark status `implemented`.
- Archive blueprint + audit log to `docs/blueprints/archive/`.
- Update archive inventory.
- Publish `v0.1-l-g4-why-not-frontier-2026-05-08` and update operational memory.

Frontier remains out of scope in every phase. Any future Frontier SDK method requires a separate blueprint or a `#P1` carve-out with source-grounded justification.

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
