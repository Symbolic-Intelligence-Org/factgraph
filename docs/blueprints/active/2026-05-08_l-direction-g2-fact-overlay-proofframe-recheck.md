# L Direction G2 — Fact Overlay + ProofFrame Recheck SDK Shell

- **Status:** draft
- **Created:** 2026-05-08
- **Last Updated:** 2026-05-08
- **Parent:** L Direction (post-A+B+G1+G4 v1-ready roadmap target)
- **Related Bundle:** [post-routemap-direction-selection-input](../../references/working/post-routemap-direction-selection-input/) — Round 8 SDK conventions audit (G2 verdict: **pending Step 0 shape decision** — protocol DTOs `SupportArtifact` + `EvaluationOverlay` are raw types and the SDK shell must decide whether to wrap them or accept them at the boundary)
- **Predecessors (shipped):**
  - [2026-05-08_l-direction-g4-why-not-frontier (archived)](../archive/2026-05-08_l-direction-g4-why-not-frontier.md)
  - [2026-05-08_l-direction-g1-check-diagnose (archived)](../archive/2026-05-08_l-direction-g1-check-diagnose.md)
  - [2026-05-07_application-ergonomic-helpers-extension (archived)](../archive/2026-05-07_application-ergonomic-helpers-extension.md)
  - [2026-05-07_walker-mechanism (archived)](../archive/2026-05-07_walker-mechanism.md)
- **Audit Log:** [2026-05-08_l-direction-g2-fact-overlay-proofframe-recheck.audit.md](./2026-05-08_l-direction-g2-fact-overlay-proofframe-recheck.audit.md)

## 1. Problem

G1 shipped `SDKStore.check(...)` / `SDKStore.diagnose(...)` and G4 shipped `SDKStore.why_not(...)`. SDK consumers can run Check / Diagnose / Why-not without importing `kernel.application`.

The next L group is G2: **Fact Overlay Check + ProofFrame Recheck**. Round 8 classified G2 as **pending Step 0 shape decision** — both capabilities currently surface raw application protocol DTOs (`SupportArtifact`, `EvaluationOverlay`) at their input boundary, which forces an SDK boundary question that G1 / G4 did not face.

Beyond the input-shape decision, G2 lands the **3rd and 4th SDK shell files** (after `check.py`, `diagnose.py`, `why_not.py`). The G1+G4 §5.5 forward trigger requires G2 Step 0 to evaluate `kernel/sdk/shells/` subpackage migration as G2 Phase 0 hygiene **before** any G2 implementation lands.

This blueprint starts G2 Step 0 only. It does not implement SDK methods until §5 questions are source-grounded and scope-frozen.

## 2. Goals

- Decide G2 SDK outward shape for Fact Overlay Check and ProofFrame Recheck with the same per-family Step 0 falsifier discipline used by G1 / G4.
- Reuse G1+G4 SDK shell infrastructure: `kernel.sdk._validation.validate_derivation`, SDKStore method delegation, error remap pattern.
- Resolve the inherited `kernel/sdk/shells/` migration trigger as either a G2 Phase 0 hygiene step (with `#P1` carve-out for the G1 invariant test) or an explicit defer.
- Establish a scoped implementation plan only after §5 falsifiers are resolved.

## 3. Non-Goals

- **No implementation in draft.** No `SDKStore.check_fact_overlay(...)`, `SDKStore.recheck_proof_frame(...)`, module files, docs updates, or tests ship until §5 is locked and status moves to `scoped`.
- **No README quickstart change.** Per `#6`, new SDK shell promotion does not automatically enter README quickstart.
- **No `kernel.sdk.__all__` expansion by default.** G1 + G4 set the pattern: SDKStore instance methods first; top-level exports need their own falsifier.
- **No B walker dependency.** G2 returns raw protocol DTOs; advanced traversal stays application-side.
- **No `factpy` rebrand.** Import root remains `kernel.sdk`; OpenAI-style ergonomics are recorded as post-L redesign preference.
- **No G3 / G5 decisions.** Rule overlays and round events / ProofFrame diff remain separate future blueprints.
- **No new application capability.** G2 wraps existing application capabilities; it does not modify `check_fact_overlay_binding(...)`, `recheck_proof_frame(...)`, or any of their DTOs.
- **No SDK-side `SupportArtifact` construction.** If §5 decides to wrap `SupportArtifact`, the wrapper is a thin reference object only; SDK does not own the construction path (SupportArtifact comes from prior Check runs at the application or SDK layer).

## 4. Current Context

### 4.1 L ordering and baseline

Q1 split locked: **G1 -> G4 -> G2 -> G3 -> G5**. G1 + G4 are implemented, archived, and published. This G2 draft is based on `v0.1-public-surface-helpers-walker-l-g1-l-g4-2026-05-08` @ `acb5a6e` (Path B combined snapshot post-G4).

Current branch for this draft: `codex/v0.1-l-g2-fact-overlay-proofframe-recheck-2026-05-08`.

### 4.2 Round 8 G2 verdict

Round 8 SDK conventions audit recorded:

> **G2 Fact Overlay + ProofFrame Recheck: pending Step 0 shape decision** — protocol DTOs (`SupportArtifact`, `EvaluationOverlay`) are currently surfaced as raw types; SDK shell must decide whether to wrap them in SDK DSL or leave them advanced-importable.

This "pending Step 0" verdict means there is at least one substantive shape decision G2 must resolve (not just a clean lift like G4). The SDK boundary precedent from G1 (§5.7 SDK `Derivation` only at input) is challenged because:

- Fact Overlay Check needs an `EvaluationOverlay` (containing `fact_actions` + `rule_actions`) at input — a structure whose canonical home is `kernel.application.protocol`.
- ProofFrame Recheck needs a `SupportArtifact` at input — produced by a prior `check_derivation_binding(...)` call's `evidence_envelope.engine_payload`. There is no obvious SDK-level alternative.

### 4.3 Existing Tier 2 / substrate surfaces

| Area | Existing surface | Layer |
|---|---|---|
| Fact Overlay request DTO | `FactOverlayCheckRequest(plan, binding, overlay, engine)` (`kernel.application.protocol.derivation_fact_overlay:282`) | `kernel.application.protocol` |
| Fact Overlay overlay DTOs | `EvaluationOverlay`, `FactOverlayAction`, `FactValueOverride`, `RuleOverlayAction` | `kernel.application.protocol.derivation_fact_overlay` |
| Fact Overlay request helper | `build_fact_value_override(...)` (Batch 2 shipped) | `kernel.application.capability_helpers` |
| Fact Overlay runtime | `check_fact_overlay_binding(request, *, store, registry=None) -> FactOverlayCheckResult` | `kernel.application.fact_overlay_runtime` |
| Fact Overlay result DTO | `FactOverlayCheckResult` | `kernel.application.protocol.derivation_fact_overlay:367` |
| ProofFrame Recheck request DTO | `ProofFrameRecheckRequest(support_artifact, overlay)` (`kernel.application.protocol.proofframe:85`) | `kernel.application.protocol` |
| ProofFrame Recheck runtime | `recheck_proof_frame(request, *, store) -> ProofFrameRecheckResult` | `kernel.application.proofframe_runtime` |
| ProofFrame Recheck result DTO | `ProofFrameRecheckResult` (with `atom_verdicts: tuple[ProofFrameAtomVerdict, ...]`) | `kernel.application.protocol.proofframe:120` |
| `SupportArtifact` (input to Recheck) | produced by `check_derivation_binding(...)` evidence envelope | `kernel.core.store._support` |

### 4.4 G1 + G4 infrastructure available to reuse

- `SDKStore.check(...)` / `SDKStore.diagnose(...)` / `SDKStore.why_not(...)` established instance-method placement.
- `kernel.sdk._validation.validate_derivation(...)` accepts SDK `Derivation` only and attaches capability-specific `SDKStoreError.path` (Round 4 Q1 extraction; reused by G4).
- G1 + G4 error mapping uses `SDKStoreError(...) from exc`, including:
  - `RuleCompileError` from registry resolution → `path="$.<cap>.dependencies"`
  - `ValueError` from `_compiled_derivation_plan_to_application(...)` engine_ext conflict → `path="$.<cap>.derivation"`
  - `CapabilityHelperError` from A helpers → `path="$.<cap>.<arg-name>"`
  - `ProtocolShapeError` from request DTO `__post_init__` → `path="$.<cap>.request"` (G4)
  - Capability-specific runtime errors (e.g., `WhyNotRuntimeError`) → `path="$.<cap>"` (G4)
- G1 + G4 invariant test pattern: 6-class single-file mirroring (`__all__` unchanged + result types not exported / instance-method placement / flat-module-no-shells / no-internal-walker-audit-imports / thin-delegate / docstring-boundary-contract).
- G4 added explicit Frontier-defer assertions (no `kernel.core.rules.frontier` import). G2 may need similar capability-specific defer assertions.

### 4.5 G1+G4 forward trigger inherited by G2

Per G1 §5.5 (forward trigger to G2) and G4 §5.5 (re-recorded ownership), **G2 Step 0 MUST evaluate `kernel/sdk/shells/` subpackage migration before adding any G2 shell file**. The trigger is at the file-count signal: post-G1 = 2 files, post-G4 = 3 files, post-G2 (without migration) = 5 files. G2 is the natural migration point.

If migration happens, it becomes G2 Phase 0 hygiene **before any G2 implementation**, includes an explicit `#P1` carve-out for the G1 archived invariant test `test_g1_modules_are_flat_and_no_shells_package_exists`, and the G4 sibling test `test_g4_modules_are_flat_and_no_shells_package_exists`.

If migration is again deferred, G2 §5.5 must record a positive justification for keeping flat layout at 5 files (not just "convenient defer") and re-record ownership to G3 or to a dedicated hygiene blueprint.

## 5. Design — Step 0 Questions

This blueprint is at `draft` status. The questions below must be resolved before status advances to `scoped`.

### 5.1 Fact Overlay SDK input shape

**Question:** Does `SDKStore.check_fact_overlay(...)` accept:

1. SDK `Derivation` + binding mapping + SDK-friendly overlay shape (mappings / sequences),
2. SDK `Derivation` + binding mapping + raw `EvaluationOverlay` protocol DTO,
3. some other shape that hides `EvaluationOverlay` entirely (e.g., per-action-kind kwargs),
4. or no SDK method at all?

**Conservative default:** option 2 (raw `EvaluationOverlay` accepted at SDK boundary), provided it does not contradict the G1 §5.7 lock spirit.

**Falsifiers required:**

- Confirm or refute that SDK precedent permits accepting `kernel.application.protocol` DTOs as input. G1 §5.7 rejected `CompiledDerivationPlan` because it was "already-lowered application-layer entry"; `EvaluationOverlay` is **author-time intent** rather than a lowered representation, so the rejection rationale may not apply.
- Confirm whether existing application-layer Fact Overlay tests construct `EvaluationOverlay` directly, indicating it is the ergonomic intent shape.
- Reject any shape that requires SDK-side `EvaluationOverlay` reconstruction without source signal.

**Decision (2026-05-08):** Lock option 2 — `SDKStore.check_fact_overlay(derivation, binding, overlay, *, engine="native", registry=None) -> FactOverlayCheckResult`, where `derivation` is SDK `Derivation`, `binding` is a `$`-prefixed mapping validated through the shared SDK validators, and `overlay` is a raw `EvaluationOverlay` protocol DTO. G2 treats `EvaluationOverlay` as author-time intent, not a lowered application plan. It is therefore not covered by G1's rejection of `CompiledDerivationPlan`, which was rejected because it is already-lowered application-layer representation.

**Falsifier outcomes:**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | `EvaluationOverlay` is author-time intent, not lowered plan state | `EvaluationOverlay` is a frozen protocol DTO over `fact_actions` / `rule_actions` with validation only for action tuple shape (`derivation_fact_overlay.py:263-278`). `FactOverlayCheckRequest` accepts either legacy tuple-of-`FactValueOverride` or `EvaluationOverlay` directly (`derivation_fact_overlay.py:281-307`). It is not a compiled plan and does not contain runtime store/registry/projection/cache state. | PASS — G1 §5.7 `CompiledDerivationPlan` rejection does not apply. |
| F2 | Application tests already treat `EvaluationOverlay` as the ergonomic intent shape | Protocol tests construct `EvaluationOverlay(fact_actions=...)`, preserve legacy positional fact actions, allow empty overlay for runtime invalid-request behavior, and accept rule-action lane values (`test_application_fact_overlay_protocol.py:274-313`). Runtime tests pass `EvaluationOverlay(...)` directly to `FactOverlayCheckRequest` for rule-action rejection and other preflight paths (`test_application_fact_overlay_runtime_native.py:236-258`). | PASS — raw overlay is already the user-facing application intent object. |
| F3 | A helper surface already builds the action pieces, not a separate SDK overlay DTO | Batch 2 helpers build `FactValueOverride`, `FactRemoveAction`, and `EvaluationOverlay` from existing store/schema context (`capability_helpers/fact_overlay.py:28-178`). Creating a parallel SDK overlay wrapper would duplicate that construction path and add a new outward SDK type under `#6` without source signal. | PASS — no new SDK overlay wrapper in first slice. |
| F4 | Direct protocol validation constrains bad overlay shapes | `EvaluationOverlay.__post_init__` rejects non-tuple actions and unknown action types (`derivation_fact_overlay.py:268-278`; tests at `test_application_fact_overlay_protocol.py:300-312`). G2 will still remap request DTO `ProtocolShapeError` and runtime failures to `SDKStoreError` in §5.8. | PASS — raw DTO does not bypass validation. |

**Forward implications:**

- `SDKStore.check_fact_overlay(...)` does not accept application `CompiledDerivationPlan`, raw `FactOverlayCheckRequest`, SDK-owned overlay DTOs, or per-action keyword shapes in this slice.
- Implementation validates `derivation` and `binding` with the same shared SDK validators used by G1/G4, then constructs `FactOverlayCheckRequest(plan, binding, overlay, engine)`.
- `overlay` wrong-type / malformed-shape failures are handled through request DTO construction and remapped per §5.8, not through a new SDK overlay normalizer.

### 5.2 ProofFrame Recheck SDK input shape

**Question:** Does `SDKStore.recheck_proof_frame(...)` accept:

1. raw `SupportArtifact` + raw `EvaluationOverlay`,
2. an SDK wrapper around `SupportArtifact`,
3. composition: take the result of a prior `sdk.check(...)` call (a `CheckResult` whose `evidence_envelope` carries the `SupportArtifact`) plus an overlay,
4. some hybrid?

**Conservative default:** option 1 — raw `SupportArtifact` + raw `EvaluationOverlay`. ProofFrame Recheck is inherently a re-evaluation of an already-existing support, so the support must come from somewhere; SDK does not own its construction.

**Decision (2026-05-08):** Lock option 1 — `SDKStore.recheck_proof_frame(support_artifact, overlay) -> ProofFrameRecheckResult`. The SDK accepts raw `SupportArtifact` + raw `EvaluationOverlay` directly, mirroring the application-layer `recheck_proof_frame(request, *, store)` runtime which itself takes a `ProofFrameRecheckRequest(support_artifact, overlay)`. The SDK shell never wraps `SupportArtifact`, never extracts it from a `CheckResult` argument, and never calls `sdk_check` internally to obtain it.

**Falsifier outcomes:**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | `SupportArtifact` is `@dataclass(frozen=True)` with no SDK-level state | `kernel/core/store/_support.py:96-126` defines `SupportArtifact` as `@dataclass(frozen=True)` with fields `kind` / `root_result_kind` / `binding_items` / `pred_witnesses` / `non_fact_steps` / `rule_refs` / `rule_ref_edges`. `__post_init__` enforces canonical sort order on every collection field. All members are application-canonical types (`BindingItems`, `PredWitness`, `NonFactStep`, `RuleRefEdge`) with their own validation. No SDK-layer state, no mutable internals, no opaque references. | PASS — SupportArtifact qualifies for raw passthrough. |
| F2 | Composition (option 3) would create a Q-Sibling SDK-layer coupling that violates `#3` heterogeneity | `CheckResult.engine_payload: SupportArtifact \| ProvenanceEnvelope` (`kernel/application/protocol/derivation_check.py:68-79`) is a **union** — native engine produces `SupportArtifact`, problog/pyreason produce `ProvenanceEnvelope`. Option 3 would force `sdk_proof_frame_recheck` to (a) accept a `CheckResult`, (b) inspect `engine_payload`, (c) reject non-native results, (d) extract the `SupportArtifact`, OR call `sdk_check` internally to obtain one. Either path breaks Sibling discipline (G1 §5.1 lock + Q1 + Q4 patterns) and creates SDK-layer coupling between two SDK shells. Option 1 also matches application-layer behavior: `recheck_proof_frame(request, ...)` already takes `ProofFrameRecheckRequest(support_artifact, overlay)` directly with no `CheckResult` argument. | PASS — composition rejected; raw `SupportArtifact` keeps Sibling discipline intact. |
| F3 | No source signal warrants an SDK wrapper around `SupportArtifact` | `SupportArtifact` is already frozen, fully canonical, and ergonomic via direct attribute access. Application tests already construct and pass `SupportArtifact` directly as `ProofFrameRecheckRequest.support_artifact`. An SDK wrapper would add a new outward DTO under `#6` without source signal, duplicate field forwarding for zero added value, and potentially drift from the protocol shape. Identical reasoning to G4 §5.3 (no `WhyNotUniverseResult` wrapper). | PASS — no wrapper. |
| F4 | The SDK shell does NOT call `sdk_check` (or any other SDK shell) internally | Locking option 1 means `sdk_proof_frame_recheck` only validates inputs and constructs `ProofFrameRecheckRequest(support_artifact, overlay)`, then dispatches `recheck_proof_frame(request, store=...)`. No `sdk_check` import, no `sdk_diagnose` import, no `sdk_why_not` import. Mirrors G4 Q1 Sibling discipline verbatim. §5.7 invariant slot will static-scan + runtime-patch this. | PASS — Sibling discipline preserved. |

**Forward implications:**

- §5.4 (ProofFrame Recheck return shape) becomes a clean documented-passthrough lock by analogy to G4 §5.3 (`ProofFrameRecheckResult` is already frozen application-canonical).
- §5.8 (error mapping) for ProofFrame Recheck is narrower than Fact Overlay because there is no derivation lowering, no registry resolution, no candidate normalization. Expected paths: `validate_support_artifact` for type rejection (`$.recheck_proof_frame.support_artifact`), `validate_overlay` for type rejection (`$.recheck_proof_frame.overlay`), `ProtocolShapeError` from `ProofFrameRecheckRequest` construction (`$.recheck_proof_frame.request`), and any runtime exception from `recheck_proof_frame(...)` (`$.recheck_proof_frame`). No `RuleCompileError`, no `ValueError` from compiled-plan lowering, no `CapabilityHelperError` (no A-side helper for ProofFrame Recheck).
- The cross-cutting precedent established by §5.1 + §5.2: **raw application protocol DTOs may cross the SDK boundary as input when (a) they are frozen application-canonical, AND (b) there is no SDK-layer alternative that doesn't either invent new outward surface or break Sibling discipline.** §5.1 satisfied this for `EvaluationOverlay` (author-time intent, no SDK alternative). §5.2 satisfies this for `SupportArtifact` (evidence output, no SDK manufacturing path). Future G blueprints may cite this precedent.

### 5.3 Fact Overlay return shape

**Question:** Does `SDKStore.check_fact_overlay(...)` return raw `FactOverlayCheckResult`, wrap, or simplify?

**Conservative default:** documented passthrough of `FactOverlayCheckResult`, mirroring G1 / G4.

**Falsifiers required:**

- Confirm G1 + G4 raw-passthrough precedent applies (`__all__` unchanged, no SDK wrapper).
- Confirm `FactOverlayCheckResult` has no mutable internals that warrant wrapping.

**Decision (2026-05-08):** Lock documented passthrough — `SDKStore.check_fact_overlay(...) -> FactOverlayCheckResult`. The method returns the application protocol DTO directly, does not wrap or simplify it, and does not add `FactOverlayCheckResult` to `kernel.sdk.__all__`.

**Falsifier outcomes:**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | G1 + G4 raw-passthrough precedent applies | G1 ships `SDKStore.check(...) -> CheckResult` and `SDKStore.diagnose(...) -> DiagnoseResult`; G4 ships `SDKStore.why_not(...) -> WhyNotUniverseResult`. Those application result DTOs remain documented passthrough values and are not re-exported through `kernel.sdk.__all__`. Runtime check during this pass: `len(kernel.sdk.__all__) == 34`; `FactOverlayCheckResult` is neither in `__all__` nor present as `kernel.sdk.FactOverlayCheckResult`. | PASS — G2 follows the established L-series result boundary. |
| F2 | `FactOverlayCheckResult` has no mutable SDK state that warrants wrapping | `FactOverlayCheckResult` is a frozen application protocol dataclass with canonical fields (`status`, `requested_binding`, `before`, `after`, `diff`, `errors`, `warnings`) and protocol validation in `__post_init__` (`derivation_fact_overlay.py:367-415`). It exposes result data directly and contains no SDK store, registry, walker, cache, or lazy substrate handle. | PASS — raw DTO passthrough is adequate and narrower than inventing an SDK wrapper under `#6`. |

**Forward implications:**

- §5.8 tests must verify `FactOverlayCheckResult` is not added to `kernel.sdk.__all__`.
- SDK docs should document `FactOverlayCheckResult` as an advanced application protocol DTO returned by the SDK method, matching G1 + G4 wording.

### 5.4 ProofFrame Recheck return shape

**Question:** Does `SDKStore.recheck_proof_frame(...)` return raw `ProofFrameRecheckResult`, wrap, or simplify?

**Conservative default:** documented passthrough of `ProofFrameRecheckResult`.

**Falsifiers required:**

- Same as §5.3 with `ProofFrameRecheckResult` shape inspected.

**Decision (2026-05-08):** Lock documented passthrough — `SDKStore.recheck_proof_frame(...) -> ProofFrameRecheckResult`. The method returns the application protocol DTO directly, does not wrap or simplify it, and does not add `ProofFrameRecheckResult` to `kernel.sdk.__all__`.

**Falsifier outcomes:**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | G1 + G4 raw-passthrough precedent applies | Same L-series precedent as §5.3. Runtime check during this pass: `len(kernel.sdk.__all__) == 34`; `ProofFrameRecheckResult` is neither in `__all__` nor present as `kernel.sdk.ProofFrameRecheckResult`. | PASS — no SDK wrapper or re-export. |
| F2 | `ProofFrameRecheckResult` has no mutable SDK state that warrants wrapping | `ProofFrameRecheckResult` is a frozen application protocol dataclass with canonical fields (`status`, `binding_items`, `atom_verdicts`) and protocol validation in `__post_init__` (`proofframe.py:120-139`). It aggregates proof-frame verdict data without SDK store, registry, walker, cache, or lazy substrate state. | PASS — raw DTO passthrough is adequate and narrower than inventing an SDK wrapper under `#6`. |

**Forward implications:**

- §5.8 tests must verify `ProofFrameRecheckResult` is not added to `kernel.sdk.__all__`.
- SDK docs should document `ProofFrameRecheckResult` as an advanced application protocol DTO returned by the SDK method, matching G1 + G4 wording.

### 5.5 Module placement and `kernel/sdk/shells/` migration

**Question:** Does G2 trigger the `kernel/sdk/shells/` subpackage migration (inherited from G1+G4 §5.5), or defer again?

Options:

- Migrate `check.py`, `diagnose.py`, `why_not.py`, plus G2's two new files into `kernel/sdk/shells/`. Includes `#P1` carve-out for `test_g1_modules_are_flat_and_no_shells_package_exists` and the matching G4 invariant.
- Continue flat layout for G2 (post-G2 = 5 flat shell files), re-record trigger to G3.

**Conservative default:** **migrate**. G2 is the natural migration point per the inherited trigger; deferring twice while file count grows runs counter to the trigger's intent.

**Decision (2026-05-08):** Lock **migrate**. G2 Phase 0 hygiene moves all SDK shell modules into a new `kernel/sdk/shells/` subpackage **before** any G2 implementation lands. Migrated layout:

```
src/kernel/sdk/
├── shells/
│   ├── __init__.py        (empty)
│   ├── _validation.py     (moved from kernel/sdk/_validation.py)
│   ├── check.py           (moved)
│   ├── diagnose.py        (moved)
│   ├── why_not.py         (moved)
│   ├── fact_overlay.py    (G2 NEW, Phase 1)
│   └── proof_frame.py     (G2 NEW, Phase 2)
├── store.py               (3 delegate imports updated to `.shells.<module>`)
└── ... (all other flat SDK modules unchanged)
```

`_validation.py` moves with the shells because it is structurally a shell-only helper — shipped specifically as Round 4 Q1 follow-up "shared SDK shell input validation". Keeping it adjacent to its only consumers reads cleanly; if a future non-shell SDK consumer ever needs the validators, that becomes a re-promotion decision at that time.

**Falsifier outcomes:**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | Migration cost is bounded and mostly mechanical | Concrete touch list: (a) 4 source files moved (`check.py` / `diagnose.py` / `why_not.py` / `_validation.py`) into `kernel/sdk/shells/` via `git mv`; (b) new empty `kernel/sdk/shells/__init__.py`; (c) `kernel/sdk/store.py` 3 delegate import lines updated (`from .check` → `from .shells.check` etc.); (d) ~15 test patch paths in `test_sdk_check.py` + `test_sdk_diagnose.py` updated from `kernel.sdk.check.<name>` to `kernel.sdk.shells.check.<name>`; (e) `G1_MODULES` constant in `test_sdk_g1_invariants.py:51` and `G4_MODULES` constant in `test_sdk_g4_invariants.py:27` retargeted; (f) Q1 Sibling static-check assertion at `test_sdk_diagnose.py:318` updated. Total ~30-50 lines across ~7 files; no behavior change; mechanical rename + import path updates. | PASS — bounded cost. |
| F2 | Thin `SDKStore` delegate pattern is preserved under shells/ | Each `SDKStore` method body becomes `from .shells.<name> import sdk_<name>; return sdk_<name>(self, ...)` — same one-line import + delegate-call shape as G1's pre-migration pattern. The `.shells.` prefix is the only diff. G1+G4 invariant slot 5 (`test_store_methods_remain_thin_delegate_methods`) keeps holding under the new layout with one-character changes to the assertion text. | PASS — pattern preserved. |
| F3 | G1+G4 invariant tests can be retrofit with `#P1` carve-out | The two archived invariants (`test_g1_modules_are_flat_and_no_shells_package_exists` and `test_g4_modules_are_flat_and_no_shells_package_exists`) are retrofit (not deprecated): assertions invert from "no shells/ subpackage" to "shell modules live in shells/ subpackage". `#P1` carve-out is fully sanctioned by precedent — G1 §5.5 archived blueprint explicitly recorded the forward trigger to G2 (`G1 archive:309`). The carve-out historical-handling per `#P1` rule 8 = **retrofit**. New G2 invariant `test_g2_shells_package_exists_with_g1_g4_g2_modules_migrated` consolidates the layout assertion across all shells. | PASS — retrofit valid. |
| F4 | Test inventory + import paths after migration verified by direct run | Post-migration verification plan: (a) targeted `python -m unittest src.kernel.tests.test_sdk_check src.kernel.tests.test_sdk_diagnose src.kernel.tests.test_sdk_why_not src.kernel.tests.test_sdk_validation src.kernel.tests.test_sdk_g1_invariants src.kernel.tests.test_sdk_g4_invariants` must pass with new paths; (b) full kernel `python -m unittest discover -s src/kernel/tests` must pass with no regression; (c) `python -m ruff check src/kernel/sdk/shells/ src/kernel/sdk/store.py` must be clean. If any fail, migration is reverted (single commit, no behavioral change). | PASS — testable. |
| F5 | Defer alternative is structurally weaker | If §5.5 defers again to G3: post-G2 = 5 flat shell files; G3 (rule overlays) per Round 8 likely adds 1-3 more (6-8 total); migration cost grows with each defer; the trigger that G1 §5.5 specifically recorded ("when 3rd/4th SDK shell file would land") fired at G4 (3rd) and is overdue at G2 (5th). Continuing to defer would require a positive justification beyond "convenience" — none surfaced during this falsifier pass. | PASS — defer rejected on structural grounds. |

**Forward implications:**

- §5.6 (module file naming) is constrained: G2 new files are `kernel/sdk/shells/fact_overlay.py` (`sdk_fact_overlay_check(...)`) + `kernel/sdk/shells/proof_frame.py` (`sdk_proof_frame_recheck(...)`). G2 §5.6 lock can proceed mechanically.
- §8 implementation plan keeps the 5-phase shape with a sharper Phase 0:
  - **Phase 0 hygiene (the migration):** `git mv` 4 files into `shells/`, add `__init__.py`, update store.py imports + test patch paths, retrofit G1+G4 invariant tests with `#P1` carve-out entries in their archived audit logs, run full kernel suite + ruff. Ships as a single migration commit before any G2 implementation. **No behavioral change.**
  - Phase 1: `sdk_fact_overlay_check(...)` real impl + contract tests.
  - Phase 2: `sdk_proof_frame_recheck(...)` real impl + contract tests + Q3/Batch-4 Sibling tests.
  - Phase 3: `test_sdk_g2_invariants.py` (6-class mirror, plus consolidated shells-layout assertion) + docs updates + cumulative G2 strict audit.
  - Phase 4: close-out, archive, snapshot publish.
- `#P1` carve-out audit-log entries land in `docs/blueprints/archive/2026-05-08_l-direction-g1-check-diagnose.audit.md` and `docs/blueprints/archive/2026-05-08_l-direction-g4-why-not-frontier.audit.md` as part of Phase 0 hygiene, recording: principle id (`#P1`), reason ("G2 §5.5 lock activates the G1 §5.5 forward trigger to G2"), scope ("rename two flat-layout invariant assertions to shells/-layout assertions"), impact ("test paths change; behavioral semantics unchanged"), reviewer ack ("user authorization at G2 §5.5 lock").
- The G1+G4 published snapshot branches (`v0.1-l-g1-check-diagnose-2026-05-08`, `v0.1-l-g4-why-not-frontier-2026-05-08`) are NOT touched. The migration only lands on the G2 topic branch and forward in time.

### 5.6 Module file naming under chosen layout

**Question:** What are the G2 shell file names (under flat or shells/ layout)?

Options for the two G2 capabilities:

- Flat: `kernel/sdk/fact_overlay.py` (`sdk_fact_overlay_check(...)`) + `kernel/sdk/proof_frame.py` (`sdk_proof_frame_recheck(...)`).
- Subpackage: same filenames under `kernel/sdk/shells/`.

`SDKStore` method names are a separate sub-question (§5.7 below).

**Falsifiers required:**

- Confirm naming aligns with existing `check.py` / `diagnose.py` / `why_not.py` convention (single concept per file).
- Confirm no name collision with existing `kernel/sdk/` modules.

### 5.7 SDKStore method names

**Question:** What are the SDKStore method names for the two G2 capabilities?

Candidates:

- `SDKStore.check_fact_overlay(...)` + `SDKStore.recheck_proof_frame(...)` — verb-first, explicit.
- `SDKStore.fact_overlay_check(...)` + `SDKStore.proof_frame_recheck(...)` — noun-verb.
- `SDKStore.fact_overlay(...)` + `SDKStore.proof_frame(...)` — single concept (drops verb).

**Conservative default:** `SDKStore.check_fact_overlay(...)` + `SDKStore.recheck_proof_frame(...)` — preserves verb-first style of G1's `check` / `diagnose` / G4's `why_not`.

**Falsifiers required:**

- Confirm consistency with existing G1 / G4 method names.
- Reject any name that collides with or shadows an existing `SDKStore` attribute (`SDKStore.add`, `.set`, `.ref`, `.evaluate`, `.get`, `.check`, `.diagnose`, `.why_not`, `.batch`, etc.).
- Note that final renaming is out of G2 scope (post-L redesign blueprint).

**Decision (2026-05-08):** Lock `SDKStore.check_fact_overlay(...)` and `SDKStore.recheck_proof_frame(...)`.

**Falsifier outcomes:**

| # | Falsifier | Evidence | Outcome |
|---|---|---|---|
| F1 | Names are consistent with G1 / G4 method style | G1 uses short verb-first methods for Q1/Q2 (`check`, `diagnose`); G4 uses the established capability phrase `why_not`. G2 has two composite capabilities, so the verb-first names preserve action semantics while staying explicit: `check_fact_overlay` checks a derivation under an overlay, and `recheck_proof_frame` rechecks an existing proof frame. | PASS — verb-first, explicit, and consistent enough without inventing a new naming family. |
| F2 | Names do not collide with current `SDKStore` attributes | Runtime check during this pass confirmed `hasattr(SDKStore, "check_fact_overlay") == False` and `hasattr(SDKStore, "recheck_proof_frame") == False` before implementation. The names do not shadow existing facade methods such as `add`, `set`, `ref`, `evaluate`, `get`, `check`, `diagnose`, `why_not`, or `batch`. | PASS — safe to add in Phase 0. |
| F3 | Post-L redesign remains out of scope | User preference for OpenAI-style SDK ergonomics is recorded as a post-L redesign input, not a per-family Step 0 override. G2 keeps the current `SDKStore.<method>` pattern and leaves global renaming / namespace redesign to the dedicated post-L blueprint. | PASS — no premature outward rename. |

**Forward implications:**

- §5.6 file naming should derive from the locked method names and chosen layout.
- §5.8 Sibling discipline must ensure neither method calls the other SDK shell or any G1/G4 sibling shell internally.

### 5.8 Error mapping and Q3 / Batch-4 Sibling discipline

**Question:** Which non-A helper / runtime exceptions remap to `SDKStoreError`, and what is the per-method Sibling discipline at the SDK layer?

Known candidate exceptions:

- `validate_derivation` `SDKStoreError` (already raised, shared with G1/G4).
- `_compiled_derivation_plan_to_application(...)` `ValueError` (G1 B.2 + G4 §5.6 pattern).
- `_resolve_runtime_registry(...)` `RuleCompileError` (G1 B.1 + G4 §5.6 pattern).
- A helper `CapabilityHelperError` (Fact Overlay only — for overlay normalization if `build_fact_value_override(...)` is used).
- Request DTO `ProtocolShapeError` (both methods — Fact Overlay's `FactOverlayCheckRequest.__post_init__` and ProofFrame's `ProofFrameRecheckRequest.__post_init__`).
- Runtime errors: `FactOverlayRuntimeError` (if exists) / generic runtime exceptions.

Sibling discipline:

- Application-layer Fact Overlay vs Check: shares helpers via `_derivation_match_helpers`, **does not call** `check_derivation_binding(...)`.
- Application-layer ProofFrame Recheck: standalone; does not call Check.
- **SDK-layer question:** does `sdk_fact_overlay_check` or `sdk_proof_frame_recheck` call `sdk_check`, `sdk_diagnose`, or `sdk_why_not`? Conservative: **NO** — mirror G1/G4 Q1 Sibling lock.

**Conservative default:** every non-SDK exception crossing SDK shell boundary remaps to `SDKStoreError(...) from exc` with capability-specific path; no SDK shell calls another SDK shell internally.

## 6. Boundaries And Invariants

| Principle | G2 interpretation |
|---|---|
| `#1` Application-first authority | SDK shell lowers/wraps and delegates; does not own Fact Overlay or ProofFrame Recheck semantics. |
| `#3` Heterogeneity | Fact Overlay Check (overlay-bearing Check variant) and ProofFrame Recheck (re-evaluate prior support) are distinct capabilities; no false-merge. |
| `#4a` Intent-minimal canonical input | SDK accepts SDK-layer intent for inputs that have a clear SDK alternative (Derivation, binding mapping); for inputs without SDK alternatives (`SupportArtifact`, possibly `EvaluationOverlay`), §5.1 + §5.2 decide. |
| `#5` Layer isolation | `kernel.sdk` may import public `kernel.application` surfaces; application/core must not import SDK; G2 uses public application protocol DTOs and runtime functions only. |
| `#6` No outward compat without signal | New SDK methods are outward commitments; keep narrow. No new SDK error subclass; no new SDK-owned wrapper unless §5 decides one with source signal. |
| `#19` Testing | Flat unittest files; per-method test + invariant file pattern from G1/G4. |
| `#P0` Conflict resolution | Authority > layer isolation > read-only > ergonomics > outward commitment. |
| `#P1` Revision flow | Any deviation gets a named carve-out with reason/scope/impact. The `kernel/sdk/shells/` migration (if it happens) requires `#P1` carve-out for G1 + G4 invariant tests. |

Forbidden until scoped:

- No `kernel.sdk.__all__` addition.
- No README quickstart update.
- No `factpy` alias / rename.
- No `kernel.application` import of `kernel.sdk`.
- No SDK-side `SupportArtifact` construction.
- No new SDK error subclass.

## 7. Acceptance

Draft-stage acceptance:

- [x] G2 draft opened on the latest G1+G4 combined baseline (`acb5a6e`).
- [x] Round 8 G2 verdict ("pending Step 0 shape decision") + the inherited `kernel/sdk/shells/` migration trigger captured.
- [x] G1 + G4 infrastructure inventoried as available prior art.
- [x] Eight Step 0 questions enumerated covering input shapes (×2), return shapes (×2), shells/ migration, file naming, method naming, error mapping + Sibling discipline.
- [ ] §5.1-§5.8 falsifier passes complete.
- [ ] Status moves to `scoped` only after all Step 0 questions are resolved.

Scoped-stage acceptance will be filled once §5 is locked.

## 8. Implementation Plan

Deferred until status `scoped`.

Expected shape if Step 0 follows conservative defaults:

1. **Phase 0** — module skeleton / `SDKStore` method stubs / placeholder tests / **shells/ migration if §5.5 locks it (Phase 0 hygiene with `#P1` carve-out for G1 + G4 invariant tests)**.
2. **Phase 1** — `sdk_fact_overlay_check(...)` real implementation + contract tests.
3. **Phase 2** — `sdk_proof_frame_recheck(...)` real implementation + contract tests + Q3/Batch-4 Sibling discipline tests.
4. **Phase 3** — `test_sdk_g2_invariants.py` (6-class mirror) + docs updates + cumulative G2 strict audit.
5. **Phase 4** — close-out, archive, snapshot publish (`v0.1-l-g2-fact-overlay-proofframe-recheck-2026-05-09` or `-2026-05-08` if same day).

The 5-phase plan reflects G2's two-method scope (vs G4's single-method) and the potential shells/ migration phase.

## 9. Docs To Update

If implementation is scoped:

- `src/kernel/sdk/docs/04_api_surface.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/application/docs/01_overview.md` (G2 test inventory)
- `src/kernel/application/docs/01_overview_en.md` (G2 test inventory)
- `docs/blueprints/archive/README.md` on archive

README quickstart remains untouched unless a separate blueprint scopes it.

## 10. Outcome / Deviations

To be filled after implementation.
